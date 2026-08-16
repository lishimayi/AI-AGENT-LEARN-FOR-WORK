"""
交易 Agent 核心模块
基于 LangChain 的 ReAct Agent，支持多轮对话
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tracers import LangChainTracer
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import settings
from backend.agent.tools import get_all_tools
from backend.agent.intent import (
    intent_recognizer,
    merge_filled_fields,
    build_order_text,
    REQUIRED_FIELDS,
)
from backend.schemas import ParsedOrder
from backend.trading.executor import trading_executor

logger = logging.getLogger(__name__)


# Agent 系统提示词
SYSTEM_PROMPT = """你是一个专业的加密货币交易助手。

你的职责：
1. 回答用户关于账户余额、持仓、行情等问题
2. 执行买卖订单（需要在执行前向用户确认）
3. 提供交易建议和市场分析

交易账户信息：
- 支持现货和合约交易

重要规则：
- 如果用户没有指定具体数量或金额，询问清楚后再执行
- 使用 USDT 作为默认计价货币
- 价格单位是 USDT（如 "BTCUSDT" 的价格）

你可以使用的工具：
{tool_descriptions}

请始终以专业、耐心的态度回答用户问题。"""


class TradingAgent:
    """交易 Agent"""

    def __init__(self):
        self._llm: Optional[ChatOpenAI] = None
        self._tools = get_all_tools()
        self._agent_executor: Optional[AgentExecutor] = None
        self._chat_history: List[Dict] = []

    @property
    def llm(self) -> ChatOpenAI:
        """获取 LLM 实例（懒加载）"""
        if self._llm is None:
            if settings.LLM_PROVIDER == "openai":
                self._llm = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL,
                    streaming=False,
                    temperature=0.7,
                )
            elif settings.LLM_PROVIDER == "anthropic":
                from langchain_anthropic import ChatAnthropic
                self._llm = ChatAnthropic(
                    model=settings.ANTHROPIC_MODEL,
                    api_key=settings.ANTHROPIC_API_KEY,
                )
            else:
                raise ValueError(f"不支持的 LLM 类型: {settings.LLM_PROVIDER}")
        return self._llm

    def _build_prompt(self) -> ChatPromptTemplate:
        """构建 Agent 提示词"""
        tool_descriptions = "\n".join([
            f"- {t.name}: {t.description}"
            for t in self._tools
        ])

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            HumanMessage(content="{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        return prompt

    def _get_agent_executor(self) -> AgentExecutor:
        """获取 Agent 执行器（懒加载）"""
        if self._agent_executor is None:
            prompt = self._build_prompt()
            agent = create_openai_functions_agent(
                llm=self.llm,
                tools=self._tools,
                prompt=prompt,
            )
            tracer = (
                LangChainTracer(project_name=settings.LANGSMITH_PROJECT)
                if settings.LANGSMITH_API_KEY and settings.LANGSMITH_TRACING
                else None
            )
            self._agent_executor = AgentExecutor(
                agent=agent,
                tools=self._tools,
                max_iterations=10,
                verbose=True,
                handle_parsing_errors=True,
                callbacks=[tracer] if tracer else None,
            )
        return self._agent_executor

    async def run(
        self,
        user_input: str,
        filled_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        运行 Agent，返回最终答案

        Args:
            user_input: 用户输入
            filled_fields: 用户在前端表单补全的字段（可选）

        Returns:
            Dict 包含:
            - success: 是否成功
            - message: 最终回复内容
            - intermediate_steps: 中间步骤列表（工具调用记录）
            - needs_input: 是否需要用户补充参数
            - missing_fields: 缺失字段列表
            - parsed_intent: 已识别的下单意图（部分字段可能为 None）
        """
        # Step 1: 意图识别 - 判断是否下单意图，参数是否齐全
        # 如果用户已经提交了表单 filled_fields，把它们合入最终意图后再判断
        if filled_fields:
            # 不必再调一次 LLM：直接把 filled_fields 当作意图，跳过识别
            intent = merge_filled_fields({}, filled_fields)
            missing = [
                f for f in REQUIRED_FIELDS
                if not intent.get(f) or intent.get(f) in (0, "")
            ]
            recognition = {
                "is_order_intent": True,
                "intent": intent,
                "missing_fields": missing,
            }
        else:
            recognition = await intent_recognizer.recognize(user_input)
            intent = recognition.get("intent") or {}
            missing = recognition.get("missing_fields") or []

        # Step 2: 如果是下单意图但参数不全，要求用户补充
        if recognition.get("is_order_intent") and missing:
            self._chat_history.append({"role": "user", "content": user_input})
            return {
                "success": True,
                "message": self._build_missing_message(missing, intent),
                "intermediate_steps": [],
                "needs_input": True,
                "missing_fields": missing,
                "parsed_intent": intent,
            }

        # Step 3: 如果是下单意图且参数齐全，直接调用交易执行器（跳过 LLM 推理）
        if recognition.get("is_order_intent") and intent:
            try:
                parsed = ParsedOrder(
                    action=intent["action"],
                    symbol=intent["symbol"],
                    amount=float(intent["amount"]),
                    amount_type=intent.get("amount_type") or "quote",
                    order_type=intent.get("order_type") or "market",
                    price=intent.get("price"),
                    stop_price=intent.get("stop_price"),
                    reasoning=f"Agent 下单: {user_input}",
                )
                result = await trading_executor.place_order(parsed)
                if result["success"]:
                    msg = (
                        f"✅ 订单已提交\n"
                        f"- 操作: {parsed.action == 'buy' and '买入' or '卖出'}\n"
                        f"- 交易对: {parsed.symbol}\n"
                        f"- 金额: {parsed.amount} "
                        f"{'USDT' if parsed.amount_type == 'quote' else parsed.symbol.replace('USDT', '')}\n"
                        f"- 类型: {'市价单' if parsed.order_type == 'market' else '限价单'}\n"
                        f"- 订单ID: {result.get('order_id', 'N/A')}"
                    )
                else:
                    msg = f"❌ 下单失败: {result.get('message')}"
                self._chat_history.append({"role": "user", "content": user_input})
                self._chat_history.append({"role": "assistant", "content": msg})
                return {
                    "success": result["success"],
                    "message": msg,
                    "intermediate_steps": [],
                    "needs_input": False,
                    "missing_fields": [],
                    "parsed_intent": intent,
                }
            except Exception as e:
                logger.error(f"直接下单失败: {e}")
                # 兜底：交给 Agent 处理
                final_input = build_order_text(intent) + "（参数已由系统补全，请直接下单）"
        else:
            final_input = user_input

        # Step 4: 执行 Agent
        executor = self._get_agent_executor()

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: executor.invoke({
                        "input": final_input,
                        "chat_history": [
                            HumanMessage(content=h["content"])
                            if h["role"] == "user"
                            else AIMessage(content=h["content"])
                            for h in self._chat_history
                        ]
                    })
                ),
                timeout=120
            )

            output = result.get("output", "")

            # 记录历史
            self._chat_history.append({"role": "user", "content": user_input})
            self._chat_history.append({"role": "assistant", "content": output})

            return {
                "success": True,
                "message": output,
                "intermediate_steps": [
                    {
                        "tool": step[0].tool,
                        "input": step[0].tool_input,
                        "output": str(step[1])
                    }
                    for step in result.get("intermediate_steps", [])
                ],
                "needs_input": False,
                "missing_fields": [],
                "parsed_intent": intent if recognition.get("is_order_intent") else None,
            }

        except asyncio.TimeoutError:
            logger.error("Agent 执行超时")
            return {
                "success": False,
                "message": "执行超时，请重试",
                "intermediate_steps": [],
                "needs_input": False,
                "missing_fields": [],
                "parsed_intent": None,
            }
        except Exception as e:
            logger.error(f"Agent 执行错误: {e}")
            return {
                "success": False,
                "message": f"Agent 执行失败: {str(e)}",
                "intermediate_steps": [],
                "needs_input": False,
                "missing_fields": [],
                "parsed_intent": None,
            }

    def _build_missing_message(self, missing: List[str], intent: Dict[str, Any]) -> str:
        """构造参数缺失时的提示消息"""
        field_labels = {
            "action": "买卖方向",
            "symbol": "交易对",
            "amount": "金额/数量",
            "amount_type": "数量类型",
            "order_type": "订单类型",
            "price": "限价价格",
            "stop_price": "止损价格",
        }
        names = [field_labels.get(f, f) for f in missing]
        if len(names) == 1:
            return f"还需要你补充 **{names[0]}**，才能完成下单。"
        return f"还需要你补充以下参数：{'、'.join(names)}，才能完成下单。"

    def reset_history(self):
        """重置对话历史"""
        self._chat_history = []


# 全局 Agent 实例
trading_agent = TradingAgent()
