import json
import httpx
from typing import Optional
from config import settings
from backend.schemas import ParsedOrder


class LLMRouter:
    """LLM路由层 - 支持多提供商切换"""

    SYSTEM_PROMPT = """你是一个专业的加密货币交易助手。你的任务是将用户的自然语言指令解析为结构化的交易订单。

必须严格返回以下JSON格式，不要包含任何其他内容：
{
    "action": "buy" 或 "sell",
    "symbol": "交易对，如 BTCUSDT、ETHUSDT",
    "amount": 数量（数字）,
    "amount_type": "base"（交易货币数量）或 "quote"（计价货币金额）,
    "order_type": "market"（市价单）或 "limit"（限价单）,
    "price": 限价单价格（数字，市价单为null）,
    "stop_price": 触发价格（数字，没有则为null）,
    "reasoning": "你对这笔订单的理解说明"
}

常见交易对：
- BTCUSDT - 比特币
- ETHUSDT - 以太坊
- SOLUSDT - Solana

注意事项：
- "买" = action: "buy", side: "BUY"
- "卖" = action: "sell", side: "SELL"
- 金额默认是quote（计价货币，如USDT）
- 数量默认是base（交易货币，如BTC）
- 如果用户说"买100美元"，amount_type应该是quote
"""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER

    async def parse_order(self, natural_language: str) -> ParsedOrder:
        """将自然语言解析为结构化订单"""
        if self.provider == "openai":
            return await self._parse_with_openai(natural_language)
        elif self.provider == "anthropic":
            return await self._parse_with_anthropic(natural_language)
        elif self.provider == "ollama":
            return await self._parse_with_ollama(natural_language)
        else:
            raise ValueError(f"不支持的LLM提供商: {self.provider}")

    async def _parse_with_openai(self, text: str) -> ParsedOrder:
        """使用OpenAI / 智谱AI / MiniMax 兼容接口解析"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        return self._parse_json_response(content)

    async def _parse_with_anthropic(self, text: str) -> ParsedOrder:
        """使用Anthropic Claude解析"""
        from anthropic import AsyncAnthropic
        
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": text}
            ]
        )
        
        content = response.content[0].text
        return self._parse_json_response(content)

    async def _parse_with_ollama(self, text: str) -> ParsedOrder:
        """使用Ollama本地模型解析"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": text}
                    ],
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["message"]["content"]
            return self._parse_json_response(content)

    def _parse_json_response(self, content: str) -> ParsedOrder:
        """解析LLM返回的JSON响应"""
        try:
            # 尝试提取JSON（处理可能的markdown代码块）
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            data = json.loads(content.strip())
            return ParsedOrder(**data)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM返回的JSON格式错误: {e}\n原始内容: {content}")
        except Exception as e:
            raise ValueError(f"解析LLM响应失败: {e}")


# 全局实例
llm_router = LLMRouter()
