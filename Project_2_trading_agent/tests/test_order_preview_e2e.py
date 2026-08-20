"""
下单预览 + 用户确认交互的端到端测试

覆盖场景：
  - 参数齐全时返回 requires_confirmation=True 的预览（不再直接下单）
  - 用户点击确认 → /api/agent/confirm → 真正下单
  - 用户取消 → 仅生成提示，不下单
  - 取消后用户补充新文案 → 重新走 /api/agent/chat 让 Agent 重新解析
"""
import asyncio
import pytest


def _run_agent_sync(user_input: str, filled_fields=None) -> dict:
    """直接调 TradingAgent.run"""
    from backend.agent.agent import trading_agent
    return asyncio.run(trading_agent.run(user_input, filled_fields=filled_fields))


def _run_http_chat(client, message: str, filled_fields=None) -> dict:
    resp = client.post(
        "/api/agent/chat",
        json={"message": message, "filled_fields": filled_fields},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _run_http_confirm(client, message: str, preview_id: str, parsed_intent: dict) -> dict:
    resp = client.post(
        "/api/agent/confirm",
        json={
            "message": message,
            "preview_id": preview_id,
            "parsed_intent": parsed_intent,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ==================== 1. 预览路径（参数齐全时不直接下单）====================

def _to_float(s: str) -> float:
    """'30 USDT' / '30.0 USDT' / '0.01 BTC' → 30.0 / 30.0 / 0.01"""
    import re
    m = re.match(r"^\s*([\d.]+)\s+", s)
    return float(m.group(1)) if m else 0.0


def test_buy_with_full_params_returns_preview_not_order():
    """买单 + 参数齐全：返回预览订单而非直接下单"""
    result = _run_agent_sync("用 30 USDT 买 BTC")

    assert result["success"] is True
    assert result["requires_confirmation"] is True, (
        f"应进入预览分支，实际: {result}"
    )
    assert result["preview_id"] is not None
    assert result["preview_id"].startswith("PV-")
    assert result["order_preview"] is not None
    preview = result["order_preview"]
    assert preview["action_zh"] == "买入"
    assert preview["symbol"] == "BTCUSDT"
    assert preview["amount"] == 30
    assert preview["amount_type"] == "quote"
    # 容忍 30 / 30.0 / 30.00 形式
    assert _to_float(preview["amount_display"]) == 30.0
    assert "USDT" in preview["amount_display"]
    assert preview["order_type_zh"] == "市价单"


def test_sell_with_full_params_returns_preview():
    """卖单 + 参数齐全：也走预览"""
    result = _run_agent_sync("卖出 0.01 BTC")

    assert result["requires_confirmation"] is True
    assert result["order_preview"]["action_zh"] == "卖出"
    assert result["order_preview"]["amount_type"] == "base"


def test_http_preview_path(client):
    """HTTP：参数齐全 → response 包含 requires_confirmation + order_preview"""
    data = _run_http_chat(client, "用 50 USDT 买 ETH")

    assert data["requires_confirmation"] is True
    assert data["preview_id"] is not None
    assert data["order_preview"] is not None
    assert data["order_preview"]["symbol"] == "ETHUSDT"


# ==================== 2. 确认下单（/api/agent/confirm）====================

def test_confirm_order_success(client):
    """用户点击确认 → /api/agent/confirm → 真正下单成功"""
    # Step 1: 先走 chat 拿预览
    preview_data = _run_http_chat(client, "用 30 USDT 买 BTC")
    assert preview_data["requires_confirmation"] is True

    # Step 2: 调 /confirm
    confirm_data = _run_http_confirm(
        client,
        message="用 30 USDT 买 BTC",
        preview_id=preview_data["preview_id"],
        parsed_intent=preview_data["parsed_intent"],
    )

    assert confirm_data["success"] is True
    assert "订单已提交" in confirm_data["message"] or "已提交" in confirm_data["message"]


def test_confirm_with_invalid_intent_returns_error(client):
    """/confirm 收到非法 intent → 友好错误，不下单"""
    bad_intent = {
        "action": "buy",
        "symbol": "BTCUSDT",
        "amount": "not-a-number",  # 故意给个非法 amount
        "amount_type": "quote",
    }
    confirm_data = _run_http_confirm(
        client,
        message="下单",
        preview_id="PV-BADINTENT01",
        parsed_intent=bad_intent,
    )
    assert confirm_data["success"] is False


# ==================== 3. 取消 / 补充文案 ====================

def test_cancel_preview_via_chat_keeps_history(client):
    """取消预览后，用户继续发新消息不会与上一次意图混淆

    测试目的：取消只是前端动作；后端 agent 不会主动取消。
    用户下一条消息会被当作新输入走意图识别。
    """
    # 第一次：下单 30 USDT
    preview_data = _run_http_chat(client, "用 30 USDT 买 BTC")
    assert preview_data["requires_confirmation"] is True

    # 第二次：用户发新指令（"改为限价 60000 USDT"）
    new_intent = _run_http_chat(
        client,
        message="改为限价 60000 USDT 买 BTC",
    )

    # 新一轮 chat 应该按"limit order" 走预览分支（不是 needs_input）
    assert new_intent["success"] is True
    # order_type=limit, price=60000 都被解析出来
    parsed = new_intent.get("parsed_intent") or {}
    assert parsed.get("order_type") == "limit"
    assert float(parsed.get("price", 0)) == 60000.0


# ==================== 4. schemas 校验 ====================

def test_agent_response_includes_preview_fields():
    """AgentResponse 支持 preview 字段"""
    from backend.schemas import AgentResponse

    resp = AgentResponse(
        success=True,
        message="preview ready",
        requires_confirmation=True,
        preview_id="PV-TEST123",
        order_preview={
            "action_zh": "买入",
            "symbol": "BTCUSDT",
            "amount": 30,
            "amount_type": "quote",
            "amount_display": "30 USDT",
            "order_type_zh": "市价单",
            "price": None,
            "stop_price": None,
            "reasoning": "test",
        },
    )
    assert resp.requires_confirmation is True
    assert resp.preview_id == "PV-TEST123"
    # order_preview 在响应里是 dict（OpenAPI 嵌套对象），
    # 但 dict 形式也允许直接用 [] 取字段
    assert resp.order_preview["symbol"] == "BTCUSDT"


def test_confirm_request_model_validates():
    """ConfirmRequest 校验必填字段"""
    from backend.schemas import ConfirmRequest
    from pydantic import ValidationError

    # 缺 parsed_intent → ValidationError
    with pytest.raises(ValidationError):
        ConfirmRequest(message="x", preview_id="PV-X")


# ==================== 5. TradingAgent.confirm_order 直接调用 ====================

def test_confirm_order_directly():
    """直接调 TradingAgent.confirm_order（不走 HTTP）"""
    from backend.agent.agent import trading_agent

    result = asyncio.run(trading_agent.confirm_order(
        preview_id="PV-DIRECT01",
        parsed_intent={
            "action": "buy",
            "symbol": "BTCUSDT",
            "amount": 25,
            "amount_type": "quote",
            "order_type": "market",
        },
        original_message="用 25 USDT 买 BTC",
    ))

    assert result["success"] is True
    assert "已提交" in result["message"]