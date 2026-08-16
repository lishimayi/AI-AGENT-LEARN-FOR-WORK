"""
交易 Agent 工具集
使用 LangChain @tool 装饰器定义可调用工具
"""
import json
import logging
from typing import Any, Dict, List, Optional
from langchain.tools import tool
from backend.trading.executor import trading_executor
from binance.client import Client as BinanceClient

logger = logging.getLogger(__name__)


@tool
def get_balance(asset: str = "USDT") -> str:
    """
    查询账户中指定币种的余额。

    Args:
        asset: 币种名称，如 USDT、BTC、ETH（默认 USDT）

    Returns:
        该币种的可用余额字符串
    """
    try:
        balance = trading_executor.client.get_asset_balance(asset=asset)
        if balance:
            free = balance.get("free", "0")
            locked = balance.get("locked", "0")
            return f"{asset} 余额: 可用 {free}, 冻结 {locked}"
        return f"未找到 {asset} 余额"
    except Exception as e:
        logger.error(f"查询余额失败: {e}")
        return f"查询 {asset} 余额失败: {str(e)}"


@tool
def get_market_price(symbol: str) -> str:
    """
    查询交易对的当前市场价格和24小时统计信息。

    Args:
        symbol: 交易对，如 BTCUSDT、ETHUSDT

    Returns:
        当前价格、24h涨跌、成交量等信息
    """
    try:
        client = trading_executor.client
        # 转换 symbol 格式（如 BTCUSDT -> BTC/USDT）
        symbol_clean = symbol.upper().replace("USDT", "")

        # 获取 ticker 信息
        ticker = client.get_symbol_ticker(symbol=symbol.upper())
        price = ticker.get("price", "0")

        # 获取 24h 统计
        stats = client.get_ticker(symbol=symbol.upper())
        price_change = stats.get("priceChange", "0")
        price_change_percent = stats.get("priceChangePercent", "0")
        high_price = stats.get("highPrice", "0")
        low_price = stats.get("lowPrice", "0")
        volume = stats.get("volume", "0")

        result = f"""
{symbol_clean}/USDT 当前行情:
- 当前价格: ${float(price):,.2f}
- 24h涨跌: {float(price_change):+,.2f} ({float(price_change_percent):+.2f}%)
- 24h最高: ${float(high_price):,.2f}
- 24h最低: ${float(low_price):,.2f}
- 24h成交量: {float(volume):,.2f} {symbol_clean}
"""
        return result.strip()
    except Exception as e:
        logger.error(f"查询价格失败: {e}")
        return f"查询 {symbol} 价格失败: {str(e)}"


@tool
def get_account_info() -> str:
    """
    获取账户概览，包括所有币种的余额和总体资产估值。

    Returns:
        账户资产总览字符串
    """
    try:
        account = trading_executor.client.get_account()

        balances = []
        total_estimate = 0.0

        for balance in account["balances"]:
            free = float(balance.get("free", 0))
            locked = float(balance.get("locked", 0))
            total = free + locked

            if total > 0:
                asset = balance["asset"]
                # 尝试获取 USDT 估值
                try:
                    if asset == "USDT":
                        estimate = total
                    else:
                        ticker = trading_executor.client.get_symbol_ticker(
                            symbol=f"{asset}USDT"
                        )
                        estimate = total * float(ticker["price"])
                except:
                    estimate = 0

                total_estimate += estimate
                balances.append({
                    "asset": asset,
                    "free": free,
                    "locked": locked,
                    "estimate_usdt": estimate
                })

        # 按估值排序
        balances.sort(key=lambda x: x["estimate_usdt"], reverse=True)

        lines = ["账户概览:"]
        for b in balances[:10]:  # 只显示前10个
            if b["estimate_usdt"] > 0.01:
                lines.append(f"- {b['asset']}: {b['free']:.6f} (≈${b['estimate_usdt']:.2f})")

        lines.append(f"\n总估值: ≈${total_estimate:.2f} USDT")
        lines.append(f"账户类型: {'现货' if account.get('accountType') == 'SPOT' else account.get('accountType', '未知')}")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"查询账户信息失败: {e}")
        return f"查询账户信息失败: {str(e)}"


@tool
def place_order(
    action: str,
    symbol: str,
    amount: float,
    amount_type: str = "quote",
    order_type: str = "market",
    price: Optional[float] = None,
    stop_price: Optional[float] = None
) -> str:
    """
    执行交易订单。

    Args:
        action: 交易方向，"buy" 或 "sell"
        symbol: 交易对，如 BTCUSDT
        amount: 数量或金额（取决于 amount_type）
        amount_type: "quote" 表示金额(USDT)，"base" 表示数量(币)
        order_type: "market" 市价单 或 "limit" 限价单
        price: 限价单价格（可选）
        stop_price: 触发价格（可选，用于止损止盈）

    Returns:
        订单执行结果字符串
    """
    from backend.schemas import ParsedOrder

    try:
        parsed = ParsedOrder(
            action=action,
            symbol=symbol.upper(),
            amount=amount,
            amount_type=amount_type,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            reasoning=f"Agent 下单: {action} {amount} {symbol}"
        )

        result = trading_executor.place_order(parsed)

        if result["success"]:
            return f"订单执行成功!\n- 订单ID: {result.get('order_id')}\n- 交易对: {result.get('symbol')}\n- 方向: {result.get('side')}\n- 类型: {result.get('type')}\n- 状态: {result.get('status')}"
        else:
            return f"订单执行失败: {result.get('message')}"
    except Exception as e:
        logger.error(f"下单失败: {e}")
        return f"下单失败: {str(e)}"


@tool
def cancel_order(order_id: str, symbol: str) -> str:
    """
    取消指定订单。

    Args:
        order_id: 订单ID
        symbol: 交易对，如 BTCUSDT

    Returns:
        取消结果字符串
    """
    try:
        result = trading_executor.client.cancel_order(
            symbol=symbol.upper(),
            orderId=order_id
        )
        return f"撤单成功!\n- 订单ID: {order_id}\n- 交易对: {symbol}\n- 状态: {result.get('status')}"
    except Exception as e:
        logger.error(f"撤单失败: {e}")
        return f"撤单失败: {str(e)}"


@tool
def get_open_orders(symbol: Optional[str] = None) -> str:
    """
    查询当前挂起的订单。

    Args:
        symbol: 交易对筛选，如 BTCUSDT（可选，不填则返回所有）

    Returns:
        挂单列表字符串
    """
    try:
        if symbol:
            orders = trading_executor.client.get_open_orders(symbol=symbol.upper())
        else:
            orders = trading_executor.client.get_open_orders()

        if not orders:
            return "当前没有挂起的订单"

        lines = [f"当前挂单 ({len(orders)} 个):"]
        for o in orders[:20]:  # 最多显示20个
            lines.append(
                f"- {o['symbol']}: {o['side']} {o['origQty']}@{o['price']} "
                f"(ID: {o['orderId']}, 类型: {o['type']})"
            )

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"查询挂单失败: {e}")
        return f"查询挂单失败: {str(e)}"


def get_all_tools() -> List:
    """获取所有可用的交易工具"""
    return [
        get_balance,
        get_market_price,
        get_account_info,
        place_order,
        cancel_order,
        get_open_orders,
    ]
