/**
 * API 调用模块
 * 与后端 FastAPI 服务通信
 *
 * 设计原则：前端只负责"对话入口"，所有业务决策（解析、下单、查余额）
 * 都交给后端 Agent。后端会通过意图识别 + ReAct 工具链自动处理。
 */

const API_BASE = 'http://localhost:8000'

export interface AgentResponse {
  success: boolean
  message: string
  session_id?: string | null
  needs_input?: boolean
  missing_fields?: string[]
  parsed_intent?: Record<string, unknown> | null
}

/**
 * 与 Agent 对话
 * 后端会决定是否需要补全参数、是否下单、是否查余额等。
 */
export async function agentChat(
  message: string,
  filledFields?: Record<string, unknown>,
): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/api/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      filled_fields: filledFields,
    }),
  })

  if (!response.ok) {
    throw new Error(`Agent 请求失败 (${response.status})`)
  }

  return response.json()
}

/**
 * 重置 Agent 对话历史
 */
export async function agentReset(): Promise<void> {
  await fetch(`${API_BASE}/api/agent/reset`, { method: 'POST' })
}
