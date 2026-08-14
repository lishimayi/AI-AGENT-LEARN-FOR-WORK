from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ==================== 请求模型 ====================

class OrderRequest(BaseModel):
    """用户下单请求 - 自然语言"""
    natural_language: str = Field(..., description="自然语言下单指令")
    
    class Config:
        json_schema_extra = {
            "example": "帮我买100美元的BTC，价格跌到50000以下再买"
        }


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

class OrderResponse(BaseModel):
    """订单执行结果"""
    success: bool = Field(..., description="是否执行成功")
    message: str = Field(..., description="结果消息")
    order_id: Optional[str] = Field(default=None, description="交易所订单ID")
    parsed_order: Optional[ParsedOrder] = Field(default=None, description="解析后的订单信息")
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
