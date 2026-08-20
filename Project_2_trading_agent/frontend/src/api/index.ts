/**
 * API 调用模块
 * 与后端 FastAPI 服务通信
 *
 * 设计原则：前端只负责"对话入口"，所有业务决策（解析、下单、查余额）
 * 都交给后端 Agent。后端会通过意图识别 + ReAct 工具链自动处理。
 */

const API_BASE = 'http://localhost:8000'

export type AccountType = 'spot' | 'futures'

export const ACCOUNT_TYPE_LABEL: Record<AccountType, string> = {
  spot: '现货',
  futures: '合约',
}

export interface OrderPreview {
  action_zh: '买入' | '卖出'
  symbol: string
  amount: number
  amount_type: 'base' | 'quote'
  amount_display: string
  order_type_zh: string
  price?: number | null
  stop_price?: number | null
  account_type?: AccountType
  account_type_zh?: string
  reasoning: string
}

export interface AgentResponse {
  success: boolean
  message: string
  session_id?: string | null
  /** 当前账户类型（每条消息都带，前端消息列表用它显示「现货/合约」标签） */
  account_type?: AccountType
  account_type_zh?: string
  needs_input?: boolean
  missing_fields?: string[]
  parsed_intent?: Record<string, unknown> | null
  intermediate_steps?: Array<{ tool: string; input: any; output: string }>
  /**
   * 业务错误码：
   * 0 — 无错误
   * 10101 — quoteOrderQty 缺失（amount_type=quote 但 amount 未提供），需要前端弹表单
   */
  error_code?: number
  /** 是否需要用户确认下单（预览订单） */
  requires_confirmation?: boolean
  /** 预览订单ID，前端确认/取消时回传 */
  preview_id?: string
  /** 订单预览详情 */
  order_preview?: OrderPreview
}

export interface AccountTypeInfo {
  account_type: AccountType
  account_type_zh: string
  supported_types: AccountType[]
}

/**
 * 与 Agent 对话
 * 后端会决定是否需要补全参数、是否下单、是否查余额等。
 *
 * @param accountType 当前账户类型；不传则沿用后端状态
 */
export async function agentChat(
  message: string,
  filledFields?: Record<string, unknown>,
  accountType?: AccountType,
): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/api/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      filled_fields: filledFields,
      account_type: accountType,
    }),
  })

  if (!response.ok) {
    throw new Error(`Agent 请求失败 (${response.status})`)
  }

  return response.json()
}

/**
 * 用户点击「确认下单」后真正下单
 */
export async function agentConfirm(
  message: string,
  previewId: string,
  parsedIntent: Record<string, unknown>,
  accountType?: AccountType,
): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/api/agent/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      preview_id: previewId,
      parsed_intent: parsedIntent,
      account_type: accountType,
    }),
  })

  if (!response.ok) {
    throw new Error(`确认下单请求失败 (${response.status})`)
  }

  return response.json()
}

/**
 * 重置 Agent 对话历史
 */
export async function agentReset(): Promise<void> {
  await fetch(`${API_BASE}/api/agent/reset`, { method: 'POST' })
}

/**
 * 获取当前账户类型（用于前端初始化「现货/合约」开关）
 */
export async function getAccountType(): Promise<AccountTypeInfo> {
  const response = await fetch(`${API_BASE}/api/agent/account-type`)
  if (!response.ok) {
    throw new Error(`获取账户类型失败 (${response.status})`)
  }
  return response.json()
}

/**
 * 切换账户类型（现货 ↔ 合约），后续 /api/agent/chat 会按新类型走
 */
export async function switchAccountType(
  accountType: AccountType,
): Promise<{ success: boolean; account_type: AccountType; account_type_zh: string }> {
  const response = await fetch(`${API_BASE}/api/agent/account-type`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account_type: accountType }),
  })
  if (!response.ok) {
    throw new Error(`切换账户类型失败 (${response.status})`)
  }
  return response.json()
}