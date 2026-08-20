"""
账户类型（现货 / 合约）支持的端到端测试

覆盖：
  - 默认现货
  - 切换到合约后 AgentResponse 带 account_type=futures
  - HTTP 端点 GET/POST /api/agent/account-type
  - 预览订单里 account_type 字段透传
  - agent.py 携带 _account_type 状态
"""
import asyncio
import pytest


# ==================== 辅助 ====================

def _run_agent_sync(user_input: str, filled_fields=None, account_type=None) -> dict:
    from backend.agent.agent import trading_agent
    return asyncio.run(
        trading_agent.run(user_input, filled_fields=filled_fields, account_type=account_type)
    )


def _run_http_chat(client, message: str, filled_fields=None, account_type=None) -> dict:
    payload = {"message": message, "filled_fields": filled_fields}
    if account_type is not None:
        payload["account_type"] = account_type
    resp = client.post("/api/agent/chat", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ==================== 1. 默认现货 ====================

def test_default_account_type_is_spot():
    """TradingAgent 默认账户类型是现货"""
    from backend.agent.agent import trading_agent
    assert trading_agent.account_type == "spot"


def test_response_default_account_type_zh():
    """AgentResponse 默认带 account_type_zh=现货"""
    from backend.schemas import AgentResponse
    resp = AgentResponse(success=True, message="ok")
    assert resp.account_type == "spot"
    assert resp.account_type_zh == "现货"


# ==================== 2. 切换账户类型 ====================

def test_set_account_type_persists():
    """set_account_type 后 trading_agent.account_type 更新"""
    from backend.agent.agent import trading_agent
    original = trading_agent.account_type
    try:
        trading_agent.set_account_type("futures")
        assert trading_agent.account_type == "futures"
    finally:
        trading_agent.set_account_type(original)


def test_set_account_type_rejects_invalid():
    """set_account_type 拒绝非法值"""
    from backend.agent.agent import trading_agent
    with pytest.raises(ValueError):
        trading_agent.set_account_type("invalid")


def test_http_switch_account_type(client):
    """POST /api/agent/account-type 切换后 GET 返回新值"""
    # 切到 futures
    resp = client.post(
        "/api/agent/account-type",
        json={"account_type": "futures"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["account_type"] == "futures"
    assert body["account_type_zh"] == "合约"

    # GET 应返回新值
    get_resp = client.get("/api/agent/account-type")
    assert get_resp.status_code == 200
    assert get_resp.json()["account_type"] == "futures"

    # 还原回 spot 避免污染后续测试
    client.post("/api/agent/account-type", json={"account_type": "spot"})


def test_http_switch_account_type_rejects_invalid(client):
    """POST /api/agent/account-type 拒绝非法值"""
    resp = client.post(
        "/api/agent/account-type",
        json={"account_type": "options"},
    )
    assert resp.status_code == 400


def test_http_get_account_type_default(client):
    """GET /api/agent/account-type 返回支持的类型和当前值"""
    resp = client.get("/api/agent/account-type")
    assert resp.status_code == 200
    body = resp.json()
    assert body["account_type"] in ("spot", "futures")
    assert body["account_type_zh"] in ("现货", "合约")
    assert "spot" in body["supported_types"]
    assert "futures" in body["supported_types"]


# ==================== 3. 响应透传 account_type ====================

def test_chat_response_includes_account_type(client):
    """/api/agent/chat 响应体包含 account_type + account_type_zh"""
    data = _run_http_chat(client, "查询余额")
    assert "account_type" in data
    assert "account_type_zh" in data
    assert data["account_type"] in ("spot", "futures")
    assert data["account_type_zh"] in ("现货", "合约")


def test_chat_with_futures_account_type_propagates(client):
    """请求里带 account_type=futures → 响应也是 futures"""
    data = _run_http_chat(
        client,
        "查询余额",
        account_type="futures",
    )
    assert data["account_type"] == "futures"
    assert data["account_type_zh"] == "合约"


def test_chat_with_spot_account_type_propagates(client):
    """请求里带 account_type=spot → 响应也是 spot"""
    data = _run_http_chat(
        client,
        "查询余额",
        account_type="spot",
    )
    assert data["account_type"] == "spot"
    assert data["account_type_zh"] == "现货"


# ==================== 4. 预览订单带 account_type ====================

def test_preview_includes_account_type(client):
    """参数齐全走预览时，预览里带 account_type_zh"""
    data = _run_http_chat(
        client,
        "用 30 USDT 买 BTC",
        account_type="futures",
    )
    assert data["requires_confirmation"] is True
    assert data["order_preview"]["account_type"] == "futures"
    assert data["order_preview"]["account_type_zh"] == "合约"
    # 消息文本里也提到「合约」
    assert "合约" in data["message"]


def test_confirm_propagates_account_type(client):
    """confirm 时不带 account_type → 沿用之前设的值"""
    # Step 1: 切到 futures
    client.post("/api/agent/account-type", json={"account_type": "futures"})

    # Step 2: 拿预览
    preview_data = _run_http_chat(
        client,
        "用 30 USDT 买 BTC",
        account_type="futures",
    )
    assert preview_data["requires_confirmation"] is True

    # Step 3: confirm（显式传 account_type=futures）
    confirm_resp = client.post(
        "/api/agent/confirm",
        json={
            "message": "用 30 USDT 买 BTC",
            "preview_id": preview_data["preview_id"],
            "parsed_intent": preview_data["parsed_intent"],
            "account_type": "futures",
        },
    )
    body = confirm_resp.json()
    assert body["account_type"] == "futures"
    assert "合约" in body["message"]

    # 还原
    client.post("/api/agent/account-type", json={"account_type": "spot"})


# ==================== 5. TradingAgent 直接调用 ====================

def test_agent_run_passes_account_type_to_preview():
    """TradingAgent.run(account_type='futures') → 预览含 futures"""
    result = _run_agent_sync(
        "用 25 USDT 买 BTC",
        account_type="futures",
    )
    assert result["account_type"] == "futures"
    assert result["account_type_zh"] == "合约"
    if result.get("requires_confirmation"):
        assert result["order_preview"]["account_type"] == "futures"


def test_agent_run_default_account_type_is_spot():
    """不传 account_type 时默认沿用 agent 状态"""
    result = _run_agent_sync("查询余额")
    assert result["account_type"] in ("spot", "futures")
    assert result["account_type_zh"] in ("现货", "合约")


def test_agent_confirm_order_respects_account_type():
    """confirm_order 时切到合约，响应里 account_type 跟随"""
    from backend.agent.agent import trading_agent

    original = trading_agent.account_type
    try:
        result = asyncio.run(trading_agent.confirm_order(
            preview_id="PV-TEST-FUT",
            parsed_intent={
                "action": "buy",
                "symbol": "BTCUSDT",
                "amount": 20,
                "amount_type": "quote",
                "order_type": "market",
            },
            original_message="用 20 USDT 买 BTC",
            account_type="futures",
        ))
        assert result["account_type"] == "futures"
        assert result["account_type_zh"] == "合约"
        assert "合约" in result["message"]
    finally:
        trading_agent.set_account_type(original)


# ==================== 6. ParsedOrder 带 account_type ====================

def test_parsed_order_default_account_type():
    """ParsedOrder 默认 spot"""
    from backend.schemas import ParsedOrder
    parsed = ParsedOrder(action="buy", symbol="BTCUSDT", amount=10)
    assert parsed.account_type == "spot"


def test_parsed_order_can_be_futures():
    """ParsedOrder 可以是 futures"""
    from backend.schemas import ParsedOrder
    parsed = ParsedOrder(action="buy", symbol="BTCUSDT", amount=10, account_type="futures")
    assert parsed.account_type == "futures"


# ==================== 7. TradingExecutor 路径选择 ====================

def test_executor_probe_account_type():
    """TradingExecutor.probe_account_type 返回 spot/futures 可用性"""
    from backend.trading.executor import trading_executor
    probe = trading_executor.probe_account_type()
    assert "spot_available" in probe
    assert "futures_available" in probe
    assert "default" in probe
    assert probe["default"] in ("spot", "futures")