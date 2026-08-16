import logging
import uuid
from typing import Optional, Dict, Any, List
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException
from config import settings
from backend.schemas import ParsedOrder, ExchangeOrder

logger = logging.getLogger(__name__)


class SafetyGuardError(Exception):
    """生产网络护栏拦截异常"""


class TradingExecutor:
    """交易执行器 - 封装交易所API"""

    def __init__(self):
        self.exchange = settings.EXCHANGE
        self._client: Optional[BinanceClient] = None

    @property
    def client(self) -> BinanceClient:
        """获取Binance客户端（懒加载）"""
        if self._client is None:
            if settings.BINANCE_TESTNET:
                self._client = BinanceClient(
                    api_key=settings.BINANCE_API_KEY,
                    api_secret=settings.BINANCE_SECRET_KEY,
                    testnet=True
                )
            else:
                self._client = BinanceClient(
                    api_key=settings.BINANCE_API_KEY,
                    api_secret=settings.BINANCE_SECRET_KEY
                )
        return self._client

    # ==================== 生产网络安全护栏 ====================

    def _is_production(self) -> bool:
        return self.exchange == "binance" and not settings.BINANCE_TESTNET

    def _allowed_symbols(self) -> List[str]:
        return [s.strip().upper() for s in settings.PRODUCTION_ALLOWED_SYMBOLS.split(",") if s.strip()]

    def enforce_production_guard(self, parsed: ParsedOrder) -> None:
        """
        生产网络硬性限制：
          1) 交易对必须在白名单内
          2) 单笔 quote 金额 ≤ PRODUCTION_MAX_QUOTE_USDT
          3) 单笔 base 数量 ≤ PRODUCTION_MAX_BASE_QTY
        测试网或 DRY_RUN 时直接放行。
        """
        if not self._is_production() or settings.DRY_RUN:
            return

        symbol = (parsed.symbol or "").upper()
        if symbol not in self._allowed_symbols():
            raise SafetyGuardError(
                f"交易对 {symbol} 不在白名单 {self._allowed_symbols()} 内，已拦截"
            )

        if parsed.amount_type == "quote" and parsed.amount > settings.PRODUCTION_MAX_QUOTE_USDT:
            raise SafetyGuardError(
                f"单笔金额 {parsed.amount} USDT 超过上限 {settings.PRODUCTION_MAX_QUOTE_USDT}"
            )
        if parsed.amount_type == "base" and parsed.amount > settings.PRODUCTION_MAX_BASE_QTY:
            raise SafetyGuardError(
                f"单笔数量 {parsed.amount} 超过上限 {settings.PRODUCTION_MAX_BASE_QTY}"
            )

        logger.warning(
            f"[PROD GUARD] action={parsed.action} symbol={symbol} "
            f"amount={parsed.amount} {parsed.amount_type}"
        )

    def convert_order(self, parsed: ParsedOrder) -> ExchangeOrder:
        """将ParsedOrder转换为交易所订单格式"""
        side = "BUY" if parsed.action == "buy" else "SELL"
        
        # 确定订单类型
        order_type = "MARKET"
        if parsed.order_type == "limit":
            order_type = "LIMIT"
        if parsed.stop_price:
            order_type = "STOP_LOSS_LIMIT"

        # 构建订单
        order = ExchangeOrder(
            symbol=parsed.symbol.upper(),
            side=side,
            order_type=order_type,
            quantity=None,
            quote_order_qty=None,
            price=None,
            stop_price=None
        )

        # 设置数量
        if parsed.amount_type == "quote":
            # 金额模式：用户指定USDT金额
            order.quote_order_qty = str(parsed.amount)
        else:
            # 数量模式：用户指定币的数量
            order.quantity = str(parsed.amount)

        # 设置限价价格
        if parsed.price:
            order.price = str(parsed.price)

        # 设置止损价格
        if parsed.stop_price:
            order.stop_price = str(parsed.stop_price)

        return order

    async def place_order(self, parsed: ParsedOrder) -> Dict[str, Any]:
        """执行下单"""
        exchange_order = self.convert_order(parsed)

        # 生产网络：先过安全护栏
        try:
            self.enforce_production_guard(parsed)
        except SafetyGuardError as e:
            return {
                "success": False,
                "message": f"[PROD GUARD] {e}",
                "order_id": None,
            }

        # DRY_RUN：不调交易所，只返回模拟订单
        if settings.DRY_RUN:
            mock_id = f"DRY-{uuid.uuid4().hex[:10].upper()}"
            logger.info(f"[DRY-RUN] mock order: {exchange_order}")
            return {
                "success": True,
                "message": "DRY-RUN：未真实下单，已模拟成功",
                "order_id": mock_id,
                "symbol": exchange_order.symbol,
                "side": exchange_order.side,
                "type": exchange_order.order_type,
                "status": "DRY_FILLED",
                "dry_run": True,
            }

        try:
            if self.exchange == "binance":
                return await self._place_binance_order(exchange_order)
            else:
                raise ValueError(f"不支持的交易所: {self.exchange}")
        except BinanceAPIException as e:
            return {
                "success": False,
                "message": f"Binance API错误: {e.message}",
                "order_id": None
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"下单失败: {str(e)}",
                "order_id": None
            }

    async def _place_binance_order(self, order: ExchangeOrder) -> Dict[str, Any]:
        """Binance下单"""
        params = {
            "symbol": order.symbol,
            "side": order.side,
            "type": order.order_type,
        }

        # 市价单金额模式
        if order.quote_order_qty:
            params["quoteOrderQty"] = order.quote_order_qty

        # 限价单/止损单
        if order.quantity:
            params["quantity"] = order.quantity
        if order.price:
            params["price"] = order.price
            params["timeInForce"] = "GTC"
        if order.stop_price:
            params["stopPrice"] = order.stop_price

        # python-binance 新版本方法名
        result = self.client.create_order(**params)
        
        return {
            "success": True,
            "message": "订单提交成功",
            "order_id": str(result["orderId"]),
            "symbol": result["symbol"],
            "side": result["side"],
            "type": result["type"],
            "status": result["status"],
        }


# 全局实例
trading_executor = TradingExecutor()
