"""
业务错误码 10101 的端到端测试

覆盖场景：
  - 买单 + amount 缺失 → error_code=10101 + needs_input=True
  - 买单 + amount 完整 → error_code != 10101
  - 卖出场景（amount_type=base）→ 不应触发 10101
"""
import asyncio
import pytest


# ==================== 辅助 ====================

def _run_agent_sync(user_input: str, filled_fields=None) -> dict:
    """同步执行 AsyncAgent.run"""
    from backend.agent.agent import trading_agent

    return asyncio.run(trading_agent.run(user_input, filled_fields=filled_fields))


def _run_http_sync(client, message: str, filled_fields=None) -> dict:
    """通过 HTTP /api/agent/chat 发起请求，返回响应体"""
    resp = client.post(
        "/api/agent/chat",
        json={"message": message, "filled_fields": filled_fields},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ==================== Test 1: 买单 + amount 缺失 ====================

def test_buy_without_amount_triggers_10101():
    """买单但没指定 amount → error_code=10101 + needs_input=True"""
    result = _run_agent_sync("帮我买 BTC")

    assert result["success"] is True
    assert result["needs_input"] is True, f"应进入 needs_input 分支，实际: {result}"
    assert result["error_code"] == 10101, (
        f"amount 缺失且 amount_type=quote 应触发 10101，实际 error_code={result.get('error_code')}"
    )
    assert "amount" in result["missing_fields"], (
        f"missing_fields 应包含 amount，实际: {result.get('missing_fields')}"
    )


def test_buy_without_amount_http_returns_10101(client):
    """HTTP 路径：买单 + 没指定金额 → 响应体 error_code=10101"""
    # 注意："帮我买点 ETH" 不含 USDT/数量，LLM 识别不出 amount → 走 needs_input 分支
    data = _run_http_sync(client, "帮我买点 ETH")

    assert data["error_code"] == 10101
    assert data["needs_input"] is True
    assert "amount" in data["missing_fields"]


# ==================== Test 2: 买单 + amount 完整 ====================

def test_buy_with_amount_does_not_trigger_10101():
    """买单 + amount 由前端表单补齐 → 不应触发 10101"""
    filled = {
        "action": "buy",
        "symbol": "BTCUSDT",
        "amount": 100,
        "amount_type": "quote",
        "order_type": "market",
    }
    # DRY_RUN 或 safety guard 决定 success，但 error_code 一定不是 10101
    result = _run_agent_sync(
        "用 100 USDT 买 BTC", filled_fields=filled
    )

    assert result.get("error_code") != 10101, (
        f"amount 已提供时不应触发 10101，实际: {result.get('error_code')}"
    )


# ==================== Test 3: 卖出场景不触发 10101 ====================

def test_sell_does_not_trigger_10101():
    """卖出场景默认 amount_type=base，不应触发 10101"""
    result = _run_agent_sync("卖出 0.01 BTC")

    assert result.get("error_code") != 10101, (
        f"卖出场景不应触发 10101，实际 error_code={result.get('error_code')}"
    )


# ==================== Test 4: default amount_type 推论 ====================

def test_default_amount_type_is_quote():
    """不指定 amount_type 时默认为 quote（introspect schema 默认值）"""
    from backend.schemas import ParsedOrder

    parsed = ParsedOrder(
        action="buy",
        symbol="BTCUSDT",
        amount=100,
    )
    assert parsed.amount_type == "quote"


# ==================== Test 5: AgentResponse 默认 error_code = 0 ====================

def test_agent_response_default_error_code_is_zero():
    """未触发错误码时响应体 error_code 默认为 0"""
    from backend.schemas import AgentResponse

    resp = AgentResponse(success=True, message="hello")
    assert resp.error_code == 0
