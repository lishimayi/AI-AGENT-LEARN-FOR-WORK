import logging
from typing import Optional, Dict, Any
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException
from config import settings
from backend.schemas import ParsedOrder, ExchangeOrder

logger = logging.getLogger(__name__)


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

    async def get_balance(self, asset: str = "USDT") -> float:
        """获取账户余额（现货）"""
        if self.exchange == "binance":
            # 获取账户信息
            account = self.client.get_account()
            for balance in account["balances"]:
                if balance["asset"] == asset:
                    return float(balance["free"])
            return 0.0
        return 0.0

    async def get_all_balances(self) -> Dict[str, Dict[str, float]]:
        """获取现货和合约账户余额"""
        result = {"spot": {}, "futures": {}}
        
        if self.exchange == "binance":
            # 测试网模式：API Key 权限不足，返回提示
            if settings.BINANCE_TESTNET:
                logger.warning("测试网模式：余额查询可能失败，请检查API权限")
            
            # 现货账户
            try:
                account = self.client.get_account()
                for balance in account["balances"]:
                    free = float(balance["free"])
                    locked = float(balance["locked"])
                    if free > 0 or locked > 0:
                        result["spot"][balance["asset"]] = {
                            "free": free,
                            "locked": locked
                        }
            except Exception as e:
                logger.warning(f"获取现货余额失败: {e}")
            
            # 合约账户
            try:
                # 测试网使用单独的合约端点
                from binance.client import Client
                futures_client = Client(
                    api_key=settings.BINANCE_API_KEY,
                    api_secret=settings.BINANCE_SECRET_KEY,
                    testnet=True,
                    futures=True  # 合约专用
                )
                futures_balance = futures_client.futures_account_balance()
                for b in futures_balance:
                    available = float(b.get("availableBalance", 0))
                    wallet = float(b.get("walletBalance", 0))
                    if available > 0 or wallet > 0:
                        result["futures"][b["asset"]] = {
                            "free": available,
                            "wallet": wallet
                        }
            except Exception as e:
                logger.warning(f"获取合约余额失败: {e}")
        
        return result


# 全局实例
trading_executor = TradingExecutor()
