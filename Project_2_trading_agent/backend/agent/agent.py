"""
交易 Agent 核心模块
基于 LangChain 的 ReAct Agent，支持多轮对话
"""
import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from langchain.agents import AgentExecutor, create_openai_tools_agent, creat_agent
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
from backend.schemas import ParsedOrder, AccountTypeZh, AccountType
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

强制规则（必须严格遵守）：
1. 任何涉及账户余额、持仓、市场价格、订单状态的查询，
   **必须**调用下方工具获取最新数据，**不允许**凭借对话历史中的旧数据回答。
2. 每个查询请求都视作独立请求，不要因为上下文中有类似历史就跳过工具调用。
3. 若工具返回错误或账户无数据，原样告知用户，不要臆测。
4. 回答中如需引用任何数字，必须使用本轮工具的返回值。
5. 即使用户重复同样的问题，也要重新调用工具。

请始终以专业、耐心的态度回答用户问题。"""


class TradingAgent:
    """交易 Agent"""

    def __init__(self):
        self._llm: Optional[ChatOpenAI] = None
        self._tools = get_all_tools()
        self._agent_executor: Optional[AgentExecutor] = None
        self._chat_history: List[Dict] = []
        # 当前账户类型：spot=现货 / futures=合约。前端开关会通过 run() 切换。
        self._account_type: AccountType = "spot"

    @property
    def account_type(self) -> AccountType:
        return self._account_type

    def set_account_type(self, account_type: AccountType) -> None:
        if account_type not in ("spot", "futures"):
            raise ValueError(f"不支持的账户类型: {account_type}")
        self._account_type = account_type

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
                    temperature=0.0,
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

        # 关键：用元组 (role, template) 让 ChatPromptTemplate 把 "{input}" 解析为变量
        # 如果用 HumanMessage(content="{input}")，花括号会被当成字面值
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        return prompt

    def _get_agent_executor(self) -> AgentExecutor:
        """获取 Agent 执行器（懒加载）"""
        if self._agent_executor is None:
            prompt = self._build_prompt()
            # 使用 OpenAI 新的 tools API（原 function_call 字段已废弃）
            # create_openai_tools_agent 解析 message.tool_calls 字段
            # 这是 OpenAI 兼容服务（如 MiniMax-M3、智谱）推荐的协议
            agent = create_openai_tools_agent(
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
                return_intermediate_steps=True,  # 关键：让 invoke() 返回 intermediate_steps
                callbacks=[tracer] if tracer else None,
            )
        return self._agent_executor

    async def run(
        self,
        user_input: str,
        filled_fields: Optional[Dict[str, Any]] = None,
        account_type: Optional[AccountType] = None,
    ) -> Dict[str, Any]:
        """
        运行 Agent，返回最终答案

        Args:
            user_input: 用户输入
            filled_fields: 用户在前端表单补全的字段（可选）
            account_type: 本次请求使用的账户类型；None 表示沿用 self._account_type

        Returns:
            Dict 包含:
            - success: 是否成功
            - message: 最终回复内容
            - intermediate_steps: 中间步骤列表（工具调用记录）
            - needs_input: 是否需要用户补充参数
            - missing_fields: 缺失字段列表
            - parsed_intent: 已识别的下单意图（部分字段可能为 None）
            - account_type: 本次使用的账户类型
        """
        # 先把请求里的账户类型落盘（在 Step 1 之前，便于预览/补全展示）
        if account_type:
            self._account_type = account_type

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

            # 业务错误码 10101：quoteOrderQty 缺失
            # amount_type 默认是 "quote"，卖出时才可能为 "base"。
            # 仅当 amount 缺失且 amount_type=quote 时上报。
            error_code = 0
            if "amount" in missing and (intent.get("amount_type") or "quote") == "quote":
                error_code = 10101

            return {
                "success": True,
                "message": self._build_missing_message(missing, intent),
                "intermediate_steps": [],
                "needs_input": True,
                "missing_fields": missing,
                "parsed_intent": intent,
                "error_code": error_code,
                "account_type": self._account_type,
                "account_type_zh": AccountTypeZh[self._account_type],
            }

        # Step 3: 如果是下单意图且参数齐全，返回订单预览让用户确认
        # （不再跳过确认直接下单，保护用户资金安全）
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
                    account_type=self._account_type,
                    reasoning=f"Agent 下单: {user_input}",
                )
            except Exception as e:
                logger.error(f"构造预览订单失败: {e}")
                final_input = build_order_text(intent) + "（参数已由系统补全，请直接下单）"
            else:
                # 构造预览详情
                preview_id = f"PV-{uuid.uuid4().hex[:10].upper()}"
                amount_zh = (
                    f"{parsed.amount} USDT"
                    if parsed.amount_type == "quote"
                    else f"{parsed.amount} {parsed.symbol.replace('USDT', '')}"
                )
                order_preview = {
                    "action_zh": "买入" if parsed.action == "buy" else "卖出",
                    "symbol": parsed.symbol,
                    "amount": parsed.amount,
                    "amount_type": parsed.amount_type,
                    "amount_display": amount_zh,
                    "order_type_zh": "市价单" if parsed.order_type == "market" else "限价单",
                    "price": parsed.price,
                    "stop_price": parsed.stop_price,
                    "account_type": parsed.account_type,
                    "account_type_zh": AccountTypeZh[parsed.account_type],
                    "reasoning": parsed.reasoning,
                }

                msg = (
                    f"📋 订单预览（请确认是否下单）\n"
                    f"- 账户类型: {AccountTypeZh[parsed.account_type]}\n"
                    f"- 操作: {order_preview['action_zh']}\n"
                    f"- 交易对: {parsed.symbol}\n"
                    f"- 金额: {amount_zh}\n"
                    f"- 类型: {order_preview['order_type_zh']}"
                )
                if parsed.price:
                    msg += f"\n- 限价: {parsed.price} USDT"
                if parsed.stop_price:
                    msg += f"\n- 触发价: {parsed.stop_price} USDT"

                # 把对话写入历史
                self._chat_history.append({"role": "user", "content": user_input})
                self._chat_history.append({"role": "assistant", "content": msg})

                return {
                    "success": True,
                    "message": msg,
                    "intermediate_steps": [],
                    "needs_input": False,
                    "missing_fields": [],
                    "parsed_intent": intent,
                    "error_code": 0,
                    "requires_confirmation": True,
                    "preview_id": preview_id,
                    "order_preview": order_preview,
                    "account_type": self._account_type,
                    "account_type_zh": AccountTypeZh[self._account_type],
                }
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
                "error_code": 0,
                "account_type": self._account_type,
                "account_type_zh": AccountTypeZh[self._account_type],
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
                "error_code": 0,
                "account_type": self._account_type,
                "account_type_zh": AccountTypeZh[self._account_type],
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
                "error_code": 0,
                "account_type": self._account_type,
                "account_type_zh": AccountTypeZh[self._account_type],
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

    async def confirm_order(
        self,
        preview_id: str,
        parsed_intent: Dict[str, Any],
        original_message: str = "",
        account_type: Optional[AccountType] = None,
    ) -> Dict[str, Any]:
        """
        用户点击「确认下单」后真正下单

        Args:
            preview_id: 预览订单ID（用于关联/审计）
            parsed_intent: 预览时的下单意图
            original_message: 用户原始消息（写入历史）
            account_type: 账户类型；None 表示沿用 self._account_type

        Returns:
            与 run() 同结构的结果
        """
        if account_type:
            self._account_type = account_type

        try:
            parsed = ParsedOrder(
                action=parsed_intent["action"],
                symbol=parsed_intent["symbol"],
                amount=float(parsed_intent["amount"]),
                amount_type=parsed_intent.get("amount_type") or "quote",
                order_type=parsed_intent.get("order_type") or "market",
                price=parsed_intent.get("price"),
                stop_price=parsed_intent.get("stop_price"),
                account_type=self._account_type,
                reasoning=f"用户已确认预览 {preview_id}",
            )
        except Exception as e:
            logger.error(f"confirm_order: 构造 ParsedOrder 失败: {e}")
            return {
                "success": False,
                "message": f"订单参数无效: {e}",
                "intermediate_steps": [],
                "needs_input": False,
                "missing_fields": [],
                "parsed_intent": parsed_intent,
                "error_code": 0,
                "account_type": self._account_type,
                "account_type_zh": AccountTypeZh[self._account_type],
            }

        result = await trading_executor.place_order(parsed)
        if result["success"]:
            msg = (
                f"✅ 订单已提交（{AccountTypeZh[parsed.account_type]}）\n"
                f"- 操作: {'买入' if parsed.action == 'buy' else '卖出'}\n"
                f"- 交易对: {parsed.symbol}\n"
                f"- 金额: {parsed.amount} "
                f"{'USDT' if parsed.amount_type == 'quote' else parsed.symbol.replace('USDT', '')}\n"
                f"- 类型: {'市价单' if parsed.order_type == 'market' else '限价单'}\n"
                f"- 订单ID: {result.get('order_id', 'N/A')}"
            )
        else:
            msg = f"❌ 下单失败: {result.get('message')}"

        if original_message:
            self._chat_history.append({"role": "user", "content": original_message})
        self._chat_history.append({"role": "assistant", "content": msg})

        return {
            "success": result["success"],
            "message": msg,
            "intermediate_steps": [],
            "needs_input": False,
            "missing_fields": [],
            "parsed_intent": parsed_intent,
            "error_code": 0,
            "account_type": self._account_type,
            "account_type_zh": AccountTypeZh[self._account_type],
        }


# 全局 Agent 实例
trading_agent = TradingAgent()
