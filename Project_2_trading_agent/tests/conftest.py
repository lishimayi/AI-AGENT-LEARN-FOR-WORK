"""
Pytest 全局 fixtures：
1. 跳过无 OPENAI_API_KEY 的环境
2. 用 FakeClient 替换 BinanceClient（避免真实联网）
3. 提供 FastAPI TestClient
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

# 把项目根目录加入 sys.path，兼容 pytest < 7（不支持 pythonpath 配置项）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==================== 环境检查 ====================

def _has_openai_key() -> bool:
    """检查 .env 或环境变量里是否有 OPENAI_API_KEY"""
    from dotenv import load_dotenv
    load_dotenv()  # 确保 .env 被加载
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key)


# ==================== Fake Binance Client ====================

class FakeBinanceClient:
    """替代 python-binance 的 Client，避免真实联网"""

    def get_asset_balance(self, asset: str = "USDT") -> Dict[str, Any]:
        return {"asset": asset, "free": "1234.56", "locked": "0.00"}

    def get_symbol_ticker(self, symbol: str = "") -> Dict[str, Any]:
        return {"symbol": symbol, "price": "60000.00"}

    def get_ticker(self, symbol: str = "") -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "priceChange": "100.00",
            "priceChangePercent": "0.17",
            "highPrice": "60500.00",
            "lowPrice": "59500.00",
            "volume": "12345.67",
        }

    def get_account(self) -> Dict[str, Any]:
        return {
            "accountType": "SPOT",
            "balances": [
                {"asset": "USDT", "free": "1234.56", "locked": "0.00"},
                {"asset": "BTC", "free": "0.01", "locked": "0.00"},
            ],
        }

    def get_open_orders(self, symbol: str = None) -> list:
        return []

    def cancel_order(self, symbol: str, orderId: str) -> Dict[str, Any]:
        return {"symbol": symbol, "orderId": orderId, "status": "CANCELED"}

    def create_order(self, **kwargs) -> Dict[str, Any]:
        return {
            "orderId": 999999,
            "symbol": kwargs.get("symbol"),
            "side": kwargs.get("side"),
            "type": kwargs.get("type"),
            "status": "FILLED",
        }

    # ==================== 合约（USDⓈ-M 永续）接口 ====================

    def futures_account(self) -> Dict[str, Any]:
        return {
            "canDeposit": True,
            "canWithdraw": True,
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "1000.00",
                    "unrealizedProfit": "0.00",
                    "availableBalance": "1000.00",
                }
            ],
        }

    def futures_create_order(self, **kwargs) -> Dict[str, Any]:
        return {
            "orderId": 888888,
            "symbol": kwargs.get("symbol"),
            "side": kwargs.get("side"),
            "type": kwargs.get("type"),
            "status": "FILLED",
        }


@pytest.fixture(autouse=True)
def mock_binance_client(monkeypatch):
    """
    自动应用到所有测试：把 trading_executor.client 替换为 FakeBinanceClient。
    tools.py 里写的是 trading_executor.client.get_asset_balance(asset=asset)，
    所以只替换 client 属性即可。
    """
    from backend.trading.executor import trading_executor

    monkeypatch.setattr(
        trading_executor,
        "_client",
        FakeBinanceClient(),
        raising=False,
    )

    # 同时屏蔽懒加载路径：重置 _client 缓存并强制走 Fake
    original_client_property = trading_executor.__class__.client.fget

    def fake_client(self):
        if self._client is None:
            self._client = FakeBinanceClient()
        return self._client

    monkeypatch.setattr(
        trading_executor.__class__,
        "client",
        property(fake_client),
    )


# ==================== LLM 可用性检查 ====================

@pytest.fixture(scope="session", autouse=True)
def require_openai_key():
    """若 OPENAI_API_KEY 未配置，则跳过所有需要 LLM 的测试"""
    if not _has_openai_key():
        pytest.skip(
            "需要 OPENAI_API_KEY 才能运行端到端测试，"
            "请在 .env 或环境变量中设置后再试",
            allow_module_level=False,
        )


# ==================== TestClient ====================

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient（同步），覆盖 /api/agent/chat 全链路"""
    from backend.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_agent_history():
    """每个测试前清空 agent 对话历史，避免前一个测试的工具调用残留导致 LLM 跳过工具调用"""
    from backend.agent.agent import trading_agent
    trading_agent.reset_history()
    yield
    trading_agent.reset_history()
