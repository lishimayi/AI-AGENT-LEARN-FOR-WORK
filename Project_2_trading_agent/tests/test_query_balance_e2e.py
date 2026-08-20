"""
"查询余额"全链路端到端测试

覆盖路径：
  HTTP /api/agent/chat
    → TradingAgent.run
      → IntentRecognizer.recognize（真实 LLM）
      → LangChain ReAct Agent（真实 LLM）
        → get_balance 工具（Fake Binance Client）
    → AgentResponse JSON

真实 LLM 调用（耗时 5–15s），已通过 conftest.require_openai_key 做 skip 保护。
"""
import asyncio
import pytest


# ==================== 辅助：把 async agent.run 包成同步 ====================

def _run_agent_sync(user_input: str, filled_fields=None) -> dict:
    """同步执行 AsyncAgent.run，避免引入额外的 asyncio fixture 复杂度"""
    from backend.agent.agent import trading_agent

    return asyncio.run(trading_agent.run(user_input, filled_fields=filled_fields))


# ==================== Test 1: 健康检查 ====================

def test_health_endpoint(client):
    """最基础的 sanity check：服务能起来"""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "llm_provider" in body
    assert "exchange" in body


# ==================== Test 2: 意图识别单独验证 ====================

def test_query_balance_intent_recognition_only():
    """不经过 Agent，只验证 IntentRecognizer 正确识别为非下单意图"""
    from backend.agent.intent import intent_recognizer

    result = asyncio.run(intent_recognizer.recognize("查询余额"))

    assert result["is_order_intent"] is False
    assert result["intent"] == {}
    assert result["missing_fields"] == []


# ==================== 工具调用断言 ====================

def _assert_get_balance_called(result, expected_asset: str = None):
    """断言工具链路上真的调用了查询余额的工具（而不是 LLM 凭空编答案）

    接受 get_balance 或 get_account_info 中任一个（两个都能拿到 USDT 余额）。
    """
    steps = result.get("intermediate_steps", [])
    assert steps, (
        f"Agent 没有调用任何工具（intermediate_steps 为空）。"
        f"LLM 可能直接编了答案。message: {result.get('message')!r}"
    )

    tool_names = [s["tool"] for s in steps]
    balance_tools = {"get_balance", "get_account_info"}
    used = [t for t in tool_names if t in balance_tools]
    assert used, (
        f"期望调用 get_balance 或 get_account_info，实际调用了: {tool_names}"
    )

    # get_account_info 不传 asset，但返回的内容必须含 USDT 和 1234.56
    if "get_account_info" in used:
        for s in steps:
            if s["tool"] == "get_account_info":
                # 工具返回值是 dict 列表，USDT 项 free 应为 1234.56
                output_str = str(s["output"])
                assert "USDT" in output_str, (
                    f"get_account_info 应包含 USDT，实际: {output_str!r}"
                )
                assert "1234.56" in output_str, (
                    f"get_account_info 应含 1234.56，实际: {output_str!r}"
                )

    if expected_asset is not None and "get_balance" in used:
        # 找到调用 get_balance 的步骤，检查参数
        for s in steps:
            if s["tool"] == "get_balance":
                tool_input = s["input"]
                if isinstance(tool_input, dict):
                    assert tool_input.get("asset") == expected_asset, (
                        f"get_balance 参数 asset 应为 {expected_asset}，实际: {tool_input}"
                    )
                break


def _assert_real_balance_in_message(msg: str):
    """断言 message 里引用了工具返回的真实余额（可能是 1234.56 或 1,234.56）"""
    # LLM 可能加千分位（1,234.56）或保留原样（1234.56），都接受
    assert ("1234.56" in msg) or ("1,234.56" in msg), (
        f"LLM 应引用工具返回的真实余额 1234.56，实际: {msg!r}"
    )


# ==================== Test 3: HTTP 全链路 ====================

def test_query_balance_full_flow_via_http(client):
    """HTTP → Agent → ReAct → get_balance 工具 → 响应"""
    resp = client.post(
        "/api/agent/chat",
        json={"message": "查询余额"},
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()

    # 响应结构
    assert data["success"] is True
    assert data["needs_input"] is False
    assert data["missing_fields"] == []

    # 非下单意图：parsed_intent 应为 None
    assert data.get("parsed_intent") in (None, {})

    # 必须真的调用了 get_balance 工具
    _assert_get_balance_called(data, expected_asset="USDT")

    # message 必须引用工具返回的真实数字（1234.56 或 1,234.56）
    msg = data["message"]
    assert msg, "响应 message 不能为空"
    _assert_real_balance_in_message(msg)


# ==================== Test 4: Agent 层直接调用 ====================

def test_query_balance_via_agent_run_directly():
    """绕过 HTTP 层，直接调用 TradingAgent.run（更快定位失败点）"""
    result = _run_agent_sync("查询余额")

    assert result["success"] is True
    assert result["needs_input"] is False
    assert result["missing_fields"] == []

    # 必须真的调用了 get_balance 工具
    _assert_get_balance_called(result, expected_asset="USDT")

    _assert_real_balance_in_message(result["message"])


# ==================== Test 5: 变体（指定币种） ====================

def test_query_specific_asset_balance():
    """'USDT 还有多少' 这种指定币种的查询也应该走 get_balance 工具"""
    result = _run_agent_sync("USDT 还有多少")

    assert result["success"] is True
    assert result["needs_input"] is False

    _assert_get_balance_called(result, expected_asset="USDT")

    _assert_real_balance_in_message(result["message"])
