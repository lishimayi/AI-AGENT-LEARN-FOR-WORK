#!/usr/bin/env bash
#
# scripts/smoke_prod_api.sh
# ------------------------------------------------------------
# 生产网络启动后的烟囱测试。演示调用确认 token + 下单护栏。
# ------------------------------------------------------------
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${PRODUCTION_CONFIRM_TOKEN:?请先 source .env.production}"

curl -s -X GET "$BASE/health" | python3 -m json.tool

echo
echo "=== 1) 解析订单（不走护栏）==="
curl -s -X POST "$BASE/api/parse" \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"帮我买 30 美元的 BTC"}' | python3 -m json.tool

echo
echo "=== 2) DRY-RUN 下单 (不带 X-Confirm-Token) ==="
echo "    注意：DRY-RUN 模式不需要 token"

curl -s -X POST "$BASE/api/order" \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"帮我买 30 美元的 BTC"}' | python3 -m json.tool

echo
echo "=== 3) 尝试买 999 USDT —— 应该被 PROD 护栏拦截 ==="
curl -s -X POST "$BASE/api/order" \
  -H "Content-Type: application/json" \
  -H "X-Confirm-Token: $TOKEN" \
  -d '{"natural_language":"帮我买 999 美元的 BTC"}' | python3 -m json.tool

echo
echo "=== 4) 交易对 DOGEUSDT 不在白名单 —— 应该被拦截 ==="
curl -s -X POST "$BASE/api/order" \
  -H "Content-Type: application/json" \
  -H "X-Confirm-Token: $TOKEN" \
  -d '{"natural_language":"帮我买 10 美元的 DOGE"}' | python3 -m json.tool
