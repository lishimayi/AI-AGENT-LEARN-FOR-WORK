/**
 * API 调用模块
 * 与后端 FastAPI 服务通信
 */

const API_BASE = 'http://localhost:8000'

export interface ParsedOrder {
  action: 'buy' | 'sell'
  symbol: string
  amount: number
  amount_type: 'base' | 'quote'
  order_type: 'market' | 'limit'
  price: number | null
  stop_price: number | null
  reasoning: string
}

export interface OrderResponse {
  success: boolean
  message: string
  order_id: string | null
  parsed_order: ParsedOrder | null
}

export interface ParseResponse {
  success: boolean
  parsed_order: ParsedOrder
}

/**
 * 仅解析订单（不执行）- 用于预览
 */
export async function parseOrder(naturalLanguage: string): Promise<ParseResponse> {
  const response = await fetch(`${API_BASE}/api/parse`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ natural_language: naturalLanguage }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || '解析失败')
  }

  return response.json()
}

/**
 * 执行订单（解析 + 下单）
 */
export async function placeOrder(naturalLanguage: string): Promise<OrderResponse> {
  const response = await fetch(`${API_BASE}/api/order`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ natural_language: naturalLanguage }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || '下单失败')
  }

  return response.json()
}

/**
 * 查询余额
 */
export async function getBalance(asset: string = 'USDT'): Promise<{ success: boolean; asset: string; free: number }> {
  const response = await fetch(`${API_BASE}/api/balance?asset=${asset}`)

  if (!response.ok) {
    throw new Error('查询余额失败')
  }

  return response.json()
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<{ status: string; llm_provider: string; exchange: string }> {
  const response = await fetch(`${API_BASE}/health`)
  return response.json()
}
