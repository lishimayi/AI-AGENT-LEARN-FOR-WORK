#!/usr/bin/env bash
#
# scripts/start_production.sh
# ------------------------------------------------------------
# 用生产网络（真实资金）的 Binance key 启动 Agent。
#
# 用法：
#   1) 第一次：cp .env.production.example .env.production
#      编辑 .env.production，把 API key/secret/PRODUCTION_CONFIRM_TOKEN 填好
#   2) 执行：bash scripts/start_production.sh
#
# 该脚本做三件事：
#   - 强制检查 DRY_RUN 状态，warn 一下确认是否真的下单
#   - 加载 .env.production
#   - 启动 uvicorn
# ------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.production"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ 找不到 $ENV_FILE"
  echo "   先执行: cp .env.production.example .env.production  并填好 key"
  exit 1
fi

# 加载 .env.production 到当前 shell 进程，避免 uvicorn 看不到
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# 检查是否"故意真下单"
if [ "${DRY_RUN:-true}" = "true" ]; then
  echo "✅ 当前是 DRY_RUN=true，不会真实下单"
else
  echo "⚠️  警告：DRY_RUN=false —— 一切成功的下单都会真金白银成交！"
  read -rp "确定要继续吗？(输入 YES 继续): " answer
  if [ "$answer" != "YES" ]; then
    echo "已取消启动"
    exit 0
  fi
fi

echo "🚀 启动生产网络 Agent (exchange=binance, testnet=$BINANCE_TESTNET)"
echo "   Allowed symbols: $PRODUCTION_ALLOWED_SYMBOLS"
echo "   Max quote USDT : $PRODUCTION_MAX_QUOTE_USDT"
echo "   Max base qty   : $PRODUCTION_MAX_BASE_QTY"

cd "$ROOT_DIR"
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
