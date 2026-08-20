from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ==================== 请求模型 ====================

# 账户类型（前端顶部开关）
AccountType = Literal["spot", "futures"]
AccountTypeZh = {"spot": "现货", "futures": "合约"}


class AgentRequest(BaseModel):
    """Agent 对话请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    # 用于在参数补全后，把用户填好的字段一起提交给后端
    filled_fields: Optional[dict] = Field(
        default=None,
        description="用户在前端表单中补全的参数，例如 {symbol: BTCUSDT, amount: 100}"
    )
    # 显式确认/拒绝标记：confirm=true 走直接下单（绕过预览）；confirm=false 取消预览
    confirm: Optional[bool] = Field(
        default=None,
        description="仅在响应已带有 preview_id 时生效；true=确认下单, false=取消"
    )
    preview_id: Optional[str] = Field(
        default=None,
        description="与 confirm 一起使用，标识要确认/取消的预览订单"
    )
    # 账户类型切换：spot=现货 / futures=合约。前端顶部开关会随每次请求带过来。
    account_type: Optional[AccountType] = Field(
        default=None,
        description="账户类型：spot=现货, futures=合约；None 表示沿用上次的设置",
    )


class ConfirmRequest(BaseModel):
    """下单确认请求：用户点击「确认下单」后调用"""
    message: str = Field(..., description="原始用户消息（用于上下文）")
    preview_id: str = Field(..., description="预览订单ID")
    parsed_intent: dict = Field(..., description="预览时的下单意图")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    account_type: Optional[AccountType] = Field(
        default=None,
        description="账户类型：spot=现货, futures=合约",
    )


class AccountTypeResponse(BaseModel):
    """账户类型响应（用于前端切换和初始化）"""
    account_type: AccountType = Field(..., description="当前账户类型")
    account_type_zh: str = Field(..., description="中文显示名")
    supported_types: list = Field(
        default_factory=lambda: ["spot", "futures"],
        description="后端支持的账户类型列表",
    )


# ==================== LLM 解析结果 ====================

class ParsedOrder(BaseModel):
    """LLM 解析后的结构化订单"""
    action: Literal["buy", "sell"] = Field(..., description="交易动作：buy=买入, sell=卖出")
    symbol: str = Field(default="BTCUSDT", description="交易对")
    amount: float = Field(..., description="数量或金额")
    amount_type: Literal["base", "quote"] = Field(default="quote", description="amount类型: base=交易货币数量, quote=计价货币金额")
    price: Optional[float] = Field(default=None, description="限价单价格，为None表示市价单")
    order_type: Literal["market", "limit"] = Field(default="market", description="订单类型: market=市价单, limit=限价单")
    stop_price: Optional[float] = Field(default=None, description="触发价格（止盈止损）")
    account_type: AccountType = Field(default="spot", description="账户类型：spot=现货, futures=合约")
    reasoning: str = Field(default="", description="LLM对订单的理解说明")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "buy",
                "symbol": "BTCUSDT",
                "amount": 100,
                "amount_type": "quote",
                "price": None,
                "order_type": "market",
                "stop_price": 50000,
                "reasoning": "用户希望买入100美元的BTC，设置50000美元的止损价格"
            }
        }


# ==================== 响应模型 ====================

class AgentResponse(BaseModel):
    """Agent 响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="Agent 最终回复内容")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    # 当前账户类型（每条消息都带，便于前端在消息流里渲染「现货/合约」标签）
    account_type: AccountType = Field(
        default="spot",
        description="本次响应使用的账户类型：spot=现货, futures=合约",
    )
    account_type_zh: str = Field(
        default="现货",
        description="账户类型中文显示名",
    )
    # 下单意图相关字段
    needs_input: bool = Field(default=False, description="是否需要用户补充参数")
    missing_fields: list = Field(
        default_factory=list,
        description="缺失的字段名列表，例如 ['symbol', 'amount']"
    )
    parsed_intent: Optional[dict] = Field(
        default=None,
        description="已解析出的下单意图（部分字段可能为 None）"
    )
    intermediate_steps: list = Field(
        default_factory=list,
        description="工具调用记录，每项 {tool, input, output}，用于断言/调试",
    )
    error_code: int = Field(
        default=0,
        description=(
            "业务错误码：0=无错误；10101=quoteOrderQty 缺失"
            "（amount_type=quote 但 amount 未提供），需要前端弹表单"
        ),
    )
    requires_confirmation: bool = Field(
        default=False,
        description="是否需要用户确认下单（预览订单）"
    )
    preview_id: Optional[str] = Field(
        default=None,
        description="预览订单ID，前端确认/取消时回传"
    )
    order_preview: Optional[dict] = Field(
        default=None,
        description=(
            "订单预览详情：{action_zh, symbol, amount, amount_type_zh, "
            "order_type_zh, price, stop_price, reasoning}"
        ),
    )
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(default="ok")
    llm_provider: str
    exchange: str
    timestamp: datetime = Field(default_factory=datetime.now)


# ==================== 交易所订单格式 ====================

class ExchangeOrder(BaseModel):
    """标准化交易所订单格式"""
    symbol: str           # 交易对
    side: str              # BUY / SELL
    order_type: str        # MARKET / LIMIT / STOP_LOSS / STOP_LOSS_LIMIT
    quantity: Optional[str] = None   # 交易数量
    quote_order_qty: Optional[str] = None  # 报价金额
    price: Optional[str] = None       # 限价价格
    stop_price: Optional[str] = None   # 触发价格
    account_type: str = "spot"        # spot / futures
