# 测试说明

本目录包含"查询余额"场景的端到端测试，验证从 HTTP 接口到 Agent 推理、再到工具调用的完整链路。

## 文件结构

```
tests/
├── __init__.py
├── conftest.py                      # 共享 fixtures：Fake Binance / TestClient / LLM skip
├── test_query_balance_e2e.py        # "查询余额"场景测试
└── README_TEST.md                   # 本文件
```

## 运行前准备

1. 安装测试依赖：

```bash
pip install -r requirements-dev.txt
```

2. 确保 `.env` 中有 `OPENAI_API_KEY`（真实 LLM 调用需要）。

> 如果 `.env` 中没有 `OPENAI_API_KEY`，所有测试会自动 skip（不会失败）。

## 运行测试

```bash
# 全部测试
pytest tests/ -v

# 只跑"查询余额"场景
pytest tests/test_query_balance_e2e.py -v
```

## 设计要点

### 真实 LLM + 假 Binance
- LLM 真实调用：让 IntentRecognizer 和 ReAct Agent 都走真实路径，验证端到端行为
- Binance 客户端被 `FakeBinanceClient` 替换，避免真实联网下单或泄露 key

### 测试覆盖矩阵

| 用例 | 验证点 |
|------|--------|
| `test_health_endpoint` | FastAPI 服务能起来 |
| `test_query_balance_intent_recognition_only` | 意图识别正确判定"查询余额"为非下单意图 |
| `test_query_balance_full_flow_via_http` | HTTP 全链路：响应结构、needs_input、message 内容 |
| `test_query_balance_via_agent_run_directly` | Agent 层直接调用，便于排查失败点 |
| `test_query_specific_asset_balance` | 变体：指定币种的查询也能正确触发工具 |

### 断言策略
- LLM 输出非确定性，对 message 使用 `in` 模糊匹配（"余额" / "USDT"）
- 不检查具体 token 数 / 具体数值，避免模型升级或 prompt 微调就挂

## 排查指南

| 现象 | 排查方向 |
|------|----------|
| 整个测试 skip | `.env` 里没有 `OPENAI_API_KEY` |
| `test_query_balance_intent_recognition_only` 失败 | LLM 误判为下单意图——检查 `INTENT_SYSTEM_PROMPT` |
| `test_query_balance_full_flow_via_http` 失败但上面那个通过 | ReAct Agent 没调 `get_balance` 工具——检查 `tools.py` 中的 `@tool` 描述 |
| 报网络错误 | 检查 `OPENAI_BASE_URL` 是否可达 |

## 扩展

要加新的端到端测试场景（如"查询行情"、"下单"），可参考 `test_query_balance_e2e.py` 的写法：
- 复制文件改名为 `test_xxx_e2e.py`
- 如果涉及下单，记得 `FakeBinanceClient.create_order` 已经被 mock，可以直接验证 `success=True`
