# 生产网络（Binance 正式网）使用指南

> ⚠️ 正式网任何成功的下单都涉及真金白银。**先用 DRY_RUN 走通流程，再逐步打开**。

## 1. 三道安全闸门（已经在代码里）

| 闸门 | 作用 | 配置项 |
|---|---|---|
| 交易对白名单 | 只能下白名单里的币对 | `PRODUCTION_ALLOWED_SYMBOLS` |
| 金额/数量上限 | 防"全部梭哈" | `PRODUCTION_MAX_QUOTE_USDT`, `PRODUCTION_MAX_BASE_QTY` |
| Confirm-Token | 调用 `/api/order` 必须带正确 header | `PRODUCTION_CONFIRM_TOKEN` |

任意一条不满足 → 返回 `success=false`，**不会到 Binance**。

## 2. 四种启动模式

| 模式 | `BINANCE_TESTNET` | `DRY_RUN` | 用途 |
|---|---|---|---|
| 安全演练 | `true` | - | 跑通端到端，不动真钱 |
| 试实盘 | `false` | `true` | 接正式网 key，但只模拟成交 |
| 小额实盘 | `false` | `false` | 真下单，护栏兜底 |
| 完全开放 | `false` | `false`，且调大上限 | 不推荐 |

## 3. 启动流程

```bash
# 第一次：生成 .env.production
cp .env.production.example .env.production

# 填入生产 key
vim .env.production
#   BINANCE_API_KEY=xxxxxxxxxx
#   BINANCE_SECRET_KEY=xxxxxxxxxx
#   PRODUCTION_CONFIRM_TOKEN=$(openssl rand -hex 16)
#   DRY_RUN=true                       # 先别急着真下单

# 启动
bash scripts/start_production.sh
```

## 4. 烟囱测试

启动后执行：
```bash
source .env.production        # 让脚本能拿到 PRODUCTION_CONFIRM_TOKEN
bash scripts/smoke_prod_api.sh
```

预期看到 4 段输出：
1. `/health` 返回 200
2. `/api/parse` 返回解析后的结构化订单
3. `/api/order` 因为 DRY_RUN 直接返回 `DRY-xxxxx` 模拟订单号
4. 故意买 999 USDT / DOGEUSDT → `[PROD GUARD 拦截]`

## 5. 切换到真下单

等以上 4 步都正常，再做：

```bash
vim .env.production
#   DRY_RUN=false
bash scripts/start_production.sh
# 脚本会问你"确定要继续吗？"，输入 YES
```

## 6. 关闭生产模式回到开发

```bash
# 把环境切回去，重新启动
# 推荐：直接停止 uvicorn（Ctrl+C），再按平时习惯用 .env
pkill -f "uvicorn backend.main:app"
uvicorn backend.main:app --reload
```

## 常见误区

- **Q: 我把 `.env.production` 提交到 Git 了怎么办？**
  A: 立刻去 https://www.binance.com/en/my/settings/api-management 撤销该 key，重新生成。

- **Q: DRY_RUN 是不是完全不会连网？**
  A: 不是。LLM 解析那一段还是会打到 minimaxi.com。所以网络是通的，只是不会真有交易动作。

- **Q: 前端怎么传 token？**
  A: 调用 `/api/order` 时加 header `X-Confirm-Token: <你的 token>`。前端代码里我没改，保持现状即可（生产模式下前端可以走单独的"正式网模式"再做）。
