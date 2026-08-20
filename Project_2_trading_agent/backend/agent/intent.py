"""
下单意图识别模块
用于在 Agent 执行前判断用户是否要下单、参数是否齐全
"""
import json
import logging
from typing import Optional, Dict, Any, List

from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.tracers import LangChainTracer
from langchain import create_agent

from config import settings
from backend.schemas import ParsedOrder

logger = logging.getLogger(__name__)

# 关键参数：缺失任意一个都需要让用户补充
REQUIRED_FIELDS = ["action", "symbol", "amount"]

# 数字字段（用于校验非空）
NUMERIC_FIELDS = ["amount", "price", "stop_price"]


INTENT_SYSTEM_PROMPT = """你是一个加密货币交易意图识别助手。
你的核心任务之一，是判断用户当前交易意图属于「现货（spot）」还是「合约（futures）」。

## 一、账户类型判断规则

1. 如果用户明确提到以下合约相关词汇，则判断为 futures：
   - 合约
   - 永续合约
   - U本位合约
   - 币本位合约
   - 开多
   - 开空
   - 做多
   - 做空
   - 平多
   - 平空
   - 杠杆
   - leverage
   - long
   - short
   - perpetual
   - futures

2. 如果用户明确提到以下现货相关词汇，则判断为 spot：
   - 现货
   - 买入 BTC
   - 卖出 BTC
   - 买币
   - 卖币
   - spot
   - 现货交易

3. 如果用户同时提供了明确的交易动作和账户类型，以用户明确表达的账户类型为最高优先级。

4. 如果用户只说：
   - 「买100 USDT的BTC」
   - 「卖0.1个ETH」
   - 「帮我买BTC」
   
   这类表达没有明确说明现货或合约时：
   - 不要擅自判断为 futures
   - 默认判断为 spot

5. 如果用户明确表达了合约交易语义，即使没有出现“合约”两个字，也应该判断为 futures。
   
   例如：
   - 「BTC开多」
   - 「BTC开空」
   - 「BTC做多10倍」
   - 「平掉我的BTC多单」
   
   都应该判断为 futures。

## 二、判断优先级

账户类型判断优先级：

1. 用户明确指定的账户类型
2. 用户使用的交易术语和交易动作
3. 当前会话上下文
4. 如果仍然无法判断，默认 spot

## 三、上下文规则

如果当前消息没有明确说明账户类型，需要结合历史对话判断。

例如：

用户：我要做合约
Agent：好的，请告诉我交易对和数量。
用户：BTC，100 USDT

第二条消息仍然属于 futures。

但是，如果用户明确切换：

用户：我要做合约
用户：算了，还是现货买BTC

则当前消息按照 spot 处理。

## 四、输出要求

每次分析交易意图时，都必须得到一个 account_type：

- spot：现货
- futures：合约
分析用户输入，判断用户是否要执行"下单"操作（下单/买入/卖出/开仓等）。

如果用户意图是下单，必须严格返回以下 JSON（不要包含其他内容）：
{
    "is_order_intent": true,
    "action": "buy" 或 "sell" 或 null,
    "symbol": "BTCUSDT" 或 "ETHUSDT" 等交易对 或 null,
    "amount": 数字 或 null,
    "amount_type": "base" 或 "quote" 或 null,
    "order_type": "market" 或 "limit" 或 null,
    "price": 数字 或 null,
    "stop_price": 数字 或 null
}

如果用户不是下单意图（如查询余额、问行情、聊天等），返回：
{"is_order_intent": false}

判断规则：
1. "买"、"买入"、"做多"、"开多" => action="buy"
2. "卖"、"卖出"、"做空"、"开空" => action="sell"
3. 默认 amount_type="quote"（按金额，如"100美元"）
4. 默认 order_type="market"（市价单），除非明确提到"限价"或"价格X"
5. 默认 symbol="BTCUSDT"（除非明确提到 ETH/SOL 等）
6. 如果信息不完整，对应字段填 null
"""


def _normalize_intent(data: Dict[str, Any]) -> Dict[str, Any]:
    """规范化意图字段，统一大小写和默认值"""
    intent = {
        "action": (data.get("action") or "").lower() if data.get("action") else None,
        "symbol": (data.get("symbol") or "").upper() if data.get("symbol") else None,
        "amount": data.get("amount"),
        "amount_type": (data.get("amount_type") or "quote").lower(),
        "order_type": (data.get("order_type") or "market").lower(),
        "price": data.get("price"),
        "stop_price": data.get("stop_price"),
    }
    if intent["amount_type"] not in ("base", "quote"):
        intent["amount_type"] = "quote"
    if intent["order_type"] not in ("market", "limit"):
        intent["order_type"] = "market"
    if intent["action"] not in ("buy", "sell"):
        intent["action"] = None
    return intent


def _extract_json(content: str) -> Optional[Dict[str, Any]]:
    """从 LLM 输出中提取 JSON 对象"""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 尝试在大块文本里抓 { ... }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


class IntentRecognizer:
    """下单意图识别器"""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER

    async def recognize(self, text: str) -> Dict[str, Any]:
        """
        识别用户输入的下单意图

        Returns:
            {
                "is_order_intent": bool,
                "intent": {action, symbol, amount, ...},
                "missing_fields": [字段名列表]
            }
        """
        try:
            raw = await self._call_llm(text)
        except Exception as e:
            logger.error(f"意图识别调用 LLM 失败: {e}")
            # 兜底：视为非下单意图，避免误判
            return {
                "is_order_intent": False,
                "intent": {},
                "missing_fields": [],
            }

        if not raw:
            return {
                "is_order_intent": False,
                "intent": {},
                "missing_fields": [],
            }

        if not raw.get("is_order_intent"):
            return {
                "is_order_intent": False,
                "intent": {},
                "missing_fields": [],
            }

        intent = _normalize_intent(raw)

        # 计算缺失字段（仅 REQUIRED_FIELDS）
        missing: List[str] = []
        for field in REQUIRED_FIELDS:
            value = intent.get(field)
            if field in NUMERIC_FIELDS:
                if value is None or value == 0:
                    missing.append(field)
            else:
                if not value:
                    missing.append(field)

        return {
            "is_order_intent": True,
            "intent": intent,
            "missing_fields": missing,
        }

    async def _call_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """调用 LLM 做意图识别"""
        print(f"意图识别调用 LLM 提供商: {self.provider}")
        if self.provider == "openai":
            return await self._call_openai(text)
        elif self.provider == "anthropic":
            return await self._call_anthropic(text)
        else:
            # 其他提供商暂不实现，回退为非下单意图
            return None

    async def _call_openai(self, text: str) -> Optional[Dict[str, Any]]:
        llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.0,
        )
        callbacks = (
            [LangChainTracer(project_name=settings.LANGSMITH_PROJECT)]
            if settings.LANGSMITH_API_KEY and settings.LANGSMITH_TRACING
            else None
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            config={"callbacks": callbacks} if callbacks else None,
        )
        print(f"意图识别调用 LLM OpenAI 结果: {response}")
        content = response.content if isinstance(response.content, str) else str(response.content)
        return _extract_json(content)

    async def _call_anthropic(self, text: str) -> Optional[Dict[str, Any]]:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=512,
            system=INTENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        content = response.content[0].text or ""
        return _extract_json(content)


def merge_filled_fields(intent: Dict[str, Any], filled: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把用户在前端表单补全的字段合并回 intent（用户输入优先）"""
    if not filled:
        return intent
    merged = dict(intent)
    for k, v in filled.items():
        if v in (None, "", []):
            continue
        merged[k] = v
    return merged


def build_order_text(intent: Dict[str, Any]) -> str:
    """把已识别意图合成为自然语言指令，用于交给 Agent 执行下单工具"""
    parts = []
    if intent.get("action") == "buy":
        parts.append("买入")
    elif intent.get("action") == "sell":
        parts.append("卖出")

    if intent.get("amount"):
        if intent.get("amount_type") == "quote":
            parts.append(f"{intent['amount']} 美元")
        else:
            base = (intent.get("symbol") or "").replace("USDT", "")
            parts.append(f"{intent['amount']} 个 {base}".strip())

    if intent.get("symbol"):
        parts.append(intent["symbol"])

    if intent.get("order_type") == "limit" and intent.get("price"):
        parts.append(f"限价 {intent['price']} 美元")

    if intent.get("stop_price"):
        parts.append(f"止损 {intent['stop_price']} 美元")

    return " ".join(parts) or "下单"


# 全局实例
intent_recognizer = IntentRecognizer()