<template>
  <div class="agent-chat">
    <!-- 顶部：账户类型开关 -->
    <div class="account-type-bar">
      <span class="account-label">账户类型</span>
      <div class="toggle-group">
        <button
          v-for="opt in accountTypeOptions"
          :key="opt.value"
          type="button"
          :class="['toggle-btn', accountType === opt.value ? 'toggle-active' : '']"
          :disabled="loading"
          @click="handleSwitchAccountType(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>

    <!-- 对话历史 -->
    <div ref="messagesContainer" class="messages-container">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message', msg.role]"
      >
        <div class="message-avatar">
          <span v-if="msg.role === 'user'">👤</span>
          <span v-else>🤖</span>
        </div>
        <div class="message-content">
          <div class="message-header">
            <span class="sender">{{ msg.role === 'user' ? '你' : 'Agent' }}</span>
            <!-- 账户类型标签（仅 assistant 消息展示；user 消息直接显示开关当前值） -->
            <span
              v-if="msg.role === 'user'"
              :class="['account-tag', msg.accountType === 'futures' ? 'tag-futures' : 'tag-spot']"
            >
              {{ msg.accountTypeZh || ACCOUNT_TYPE_LABEL[accountType] }}
            </span>
            <span
              v-else-if="msg.accountTypeZh"
              :class="['account-tag', msg.accountType === 'futures' ? 'tag-futures' : 'tag-spot']"
            >
              {{ msg.accountTypeZh }}
            </span>
            <span class="time">{{ formatTime(msg.timestamp) }}</span>
          </div>

          <!-- 普通文本消息 -->
          <div
            v-if="!msg.needsInput"
            class="message-body"
            v-html="formatContent(msg.content)"
          ></div>

          <!-- 参数补全表单 -->
          <div v-else-if="msg.needsInput" class="order-form">
            <div class="message-body" v-html="formatContent(msg.content)"></div>

            <div class="form-grid">
              <!-- 买卖方向 -->
              <div class="form-field">
                <label>买卖方向</label>
                <div class="chip-group">
                  <button
                    v-for="opt in actionOptions"
                    :key="opt.value"
                    type="button"
                    :class="[
                      'chip',
                      form.action === opt.value ? 'chip-active' : '',
                      isMissing('action') ? 'chip-required' : ''
                    ]"
                    :disabled="loading"
                    @click="form.action = opt.value"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>

              <!-- 交易对 -->
              <div class="form-field">
                <label>交易对</label>
                <div class="chip-group">
                  <button
                    v-for="opt in symbolOptions"
                    :key="opt.value"
                    type="button"
                    :class="[
                      'chip',
                      form.symbol === opt.value ? 'chip-active' : '',
                      isMissing('symbol') ? 'chip-required' : ''
                    ]"
                    :disabled="loading"
                    @click="form.symbol = opt.value"
                  >
                    {{ opt.label }}
                  </button>
                </div>
                <input
                  v-model="form.symbol"
                  type="text"
                  placeholder="或手动输入，如 BTCUSDT"
                  class="text-input"
                  :disabled="loading"
                />
              </div>

              <!-- 金额 -->
              <div class="form-field">
                <label>
                  {{ form.amount_type === 'quote' ? '买入金额' : '买入数量' }}（USDT）
                </label>
                <input
                  v-model.number="form.amount"
                  type="number"
                  step="any"
                  min="0"
                  placeholder="例如 100"
                  :class="['text-input', isMissing('amount') ? 'input-required' : '']"
                  :disabled="loading"
                />
                <div class="chip-group">
                  <button
                    v-for="opt in amountOptions"
                    :key="opt.value"
                    type="button"
                    :class="[
                      'chip',
                      Number(form.amount) === opt.value ? 'chip-active' : ''
                    ]"
                    :disabled="loading"
                    @click="form.amount = opt.value"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>
            </div>

            <div class="form-actions">
              <button
                type="button"
                class="cancel-btn"
                :disabled="loading"
                @click="handleCancelForm(index)"
              >
                取消
              </button>
              <button
                type="button"
                class="submit-btn"
                :disabled="loading || !isFormValid"
                @click="handleSubmitForm(msg.rawText || '')"
              >
                {{ loading ? '处理中...' : '确认下单' }}
              </button>
            </div>
          </div>

          <!-- 订单预览卡片 -->
          <div v-else-if="msg.orderPreview" class="order-preview">
            <div class="preview-header">
              <span class="preview-title">📋 订单预览</span>
              <span class="preview-id-area">
                <span
                  v-if="msg.orderPreview.account_type_zh"
                  :class="['account-tag', msg.orderPreview.account_type === 'futures' ? 'tag-futures' : 'tag-spot']"
                >
                  {{ msg.orderPreview.account_type_zh }}
                </span>
                <span class="preview-id">ID: {{ msg.previewId }}</span>
              </span>
            </div>

            <div class="preview-grid">
              <div class="preview-row">
                <span class="preview-label">操作</span>
                <span
                  :class="[
                    'preview-value',
                    'action-tag',
                    msg.orderPreview.action_zh === '买入' ? 'action-buy' : 'action-sell'
                  ]"
                >
                  {{ msg.orderPreview.action_zh }}
                </span>
              </div>
              <div class="preview-row">
                <span class="preview-label">交易对</span>
                <span class="preview-value">{{ msg.orderPreview.symbol }}</span>
              </div>
              <div class="preview-row">
                <span class="preview-label">金额</span>
                <span class="preview-value amount-value">
                  {{ msg.orderPreview.amount_display }}
                </span>
              </div>
              <div class="preview-row">
                <span class="preview-label">类型</span>
                <span class="preview-value">{{ msg.orderPreview.order_type_zh }}</span>
              </div>
              <div v-if="msg.orderPreview.price" class="preview-row">
                <span class="preview-label">限价</span>
                <span class="preview-value">{{ msg.orderPreview.price }} USDT</span>
              </div>
              <div v-if="msg.orderPreview.stop_price" class="preview-row">
                <span class="preview-label">触发价</span>
                <span class="preview-value">{{ msg.orderPreview.stop_price }} USDT</span>
              </div>
            </div>

            <div v-if="msg.previewStatus === 'pending'" class="preview-actions">
              <button
                type="button"
                class="cancel-btn"
                :disabled="loading"
                @click="handleCancelPreview(index)"
              >
                取消
              </button>
              <button
                type="button"
                class="submit-btn"
                :disabled="loading"
                @click="handleConfirmOrder(index)"
              >
                {{ loading ? '处理中...' : '确认下单' }}
              </button>
            </div>
            <div v-else-if="msg.previewStatus === 'cancelled'" class="preview-status cancelled">
              已取消
            </div>
            <div v-else-if="msg.previewStatus === 'confirmed'" class="preview-status confirmed">
              已提交
            </div>
          </div>
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="loading" class="message assistant">
        <div class="message-avatar">
          <span>🤖</span>
        </div>
        <div class="message-content">
          <div class="message-header">
            <span class="sender">Agent</span>
            <span class="thinking-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </span>
          </div>
          <div class="message-body loading-text">思考中...</div>
        </div>
      </div>
    </div>

    <!-- 输入框 -->
    <div class="input-area">
      <textarea
        v-model="inputText"
        placeholder="输入你的问题或下单指令，如：帮我买100美元的BTC"
        @keydown.enter.exact.prevent="handleSend"
        :disabled="loading"
        rows="1"
      ></textarea>
      <button @click="handleSend" :disabled="loading || !inputText.trim()" class="send-btn">
        <span v-if="loading">处理中...</span>
        <span v-else>发送</span>
      </button>
      <button @click="handleReset" :disabled="loading" class="reset-btn" title="清空对话">
        <span>清空</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, reactive, computed, onMounted } from 'vue'
import {
  agentChat,
  agentReset,
  agentConfirm,
  getAccountType,
  switchAccountType,
  ACCOUNT_TYPE_LABEL,
  type OrderPreview,
  type AccountType,
} from '../api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  needsInput?: boolean
  rawText?: string
  missingFields?: string[]
  parsedIntent?: Record<string, any> | null
  /** 预览订单：requires_confirmation=true 时显示卡片 */
  previewId?: string
  orderPreview?: OrderPreview | null
  /** 用户已经处理过的预览（已确认/已取消），用于锁定按钮 */
  previewStatus?: 'pending' | 'confirmed' | 'cancelled'
  /** 当前消息使用的账户类型（仅 assistant 真实值；user 写当前开关值） */
  accountType?: AccountType
  accountTypeZh?: string
}

interface IntentForm {
  action: string
  symbol: string
  amount: number | null
  amount_type: 'base' | 'quote'
}

const messages = ref<Message[]>([])
const inputText = ref('')
const loading = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)
const accountType = ref<AccountType>('spot')

const accountTypeOptions: { value: AccountType; label: string }[] = [
  { value: 'spot', label: ACCOUNT_TYPE_LABEL.spot },
  { value: 'futures', label: ACCOUNT_TYPE_LABEL.futures },
]

// 初始化：从后端拉一次账户类型
onMounted(async () => {
  try {
    const info = await getAccountType()
    accountType.value = info.account_type
  } catch (e) {
    // 默认 spot，不阻塞 UI
    console.warn('获取账户类型失败，使用默认 spot:', e)
  }
})

async function handleSwitchAccountType(next: AccountType) {
  if (accountType.value === next || loading.value) return
  loading.value = true
  try {
    const res = await switchAccountType(next)
    accountType.value = res.account_type
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content:
        '切换账户类型失败: ' +
        (e instanceof Error ? e.message : '未知错误'),
      timestamp: new Date(),
    })
  } finally {
    loading.value = false
  }
}

const actionOptions = [
  { value: 'buy', label: '买入' },
  { value: 'sell', label: '卖出' },
]
const symbolOptions = [
  { value: 'BTCUSDT', label: 'BTC/USDT' },
  { value: 'ETHUSDT', label: 'ETH/USDT' },
  { value: 'SOLUSDT', label: 'SOL/USDT' },
]
const amountOptions = [
  { value: 50, label: '$50' },
  { value: 100, label: '$100' },
  { value: 500, label: '$500' },
  { value: 1000, label: '$1000' },
]

const form = reactive<IntentForm>({
  action: '',
  symbol: '',
  amount: null,
  amount_type: 'quote',
})
let currentMissing: string[] = []

function isMissing(field: string): boolean {
  return currentMissing.includes(field)
}

const isFormValid = computed(() => {
  return Boolean(form.action && form.symbol && form.amount && form.amount > 0)
})

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatContent(content: string): string {
  if (!content) return ''
  return content
    .replace(/```([\s\S]*?)```/g, '<pre class="code-block">$1</pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

function resetForm(intent?: Record<string, any> | null) {
  form.action = intent?.action || ''
  form.symbol = intent?.symbol || ''
  form.amount =
    typeof intent?.amount === 'number' && intent.amount > 0 ? intent.amount : null
  form.amount_type = (intent?.amount_type as 'base' | 'quote') || 'quote'
}

function applyIntent(intent?: Record<string, any> | null) {
  resetForm(intent)
  currentMissing = []
}

async function callAgent(
  message: string,
  filledFields?: Record<string, any>,
) {
  return agentChat(message, filledFields, accountType.value)
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  // 记录 user 消息时同步记下当前账户类型（用户当时在哪个账户下发的指令）
  const msgAccountType = accountType.value
  const msgAccountTypeZh = ACCOUNT_TYPE_LABEL[msgAccountType]

  messages.value.push({
    role: 'user',
    content: text,
    timestamp: new Date(),
    accountType: msgAccountType,
    accountTypeZh: msgAccountTypeZh,
  })
  inputText.value = ''
  loading.value = true
  await nextTick()
  scrollToBottom()

  try {
    const data = await callAgent(text)
    handleAgentResponse(data, text)
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '请求失败: ' + (error instanceof Error ? error.message : '未知错误'),
      timestamp: new Date(),
      accountType: msgAccountType,
      accountTypeZh: msgAccountTypeZh,
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function handleAgentResponse(data: AgentResponse, userText: string) {
  const responseAccountType = data.account_type || accountType.value
  const responseAccountTypeZh =
    data.account_type_zh || ACCOUNT_TYPE_LABEL[responseAccountType]

  const pushAssistant = (overrides: Partial<Message> = {}): Message => ({
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    accountType: responseAccountType,
    accountTypeZh: responseAccountTypeZh,
    ...overrides,
  })

  if (!data.success) {
    messages.value.push(
      pushAssistant({ content: `错误: ${data.message}` }),
    )
    return
  }

  // 业务错误码 10101：quoteOrderQty 缺失 → 自动转 needs_input 渲染表单
  const requiresForm = data.needs_input || data.error_code === 10101

  if (requiresForm) {
    currentMissing = data.missing_fields || []
    resetForm(data.parsed_intent)

    const prompt =
      data.error_code === 10101
        ? `需要您补充买入金额才能下单（错误码 10101：quoteOrderQty 缺失）\n\n${data.message}`
        : data.message

    messages.value.push(
      pushAssistant({
        content: prompt,
        needsInput: true,
        rawText: userText,
        missingFields: data.missing_fields || [],
        parsedIntent: data.parsed_intent || null,
      }),
    )
    return
  }

  // 预览订单：参数齐全 → 后端不直接下单，先返回预览让用户确认
  if (data.requires_confirmation && data.preview_id && data.order_preview) {
    applyIntent(data.parsed_intent)
    messages.value.push(
      pushAssistant({
        content: data.message,
        previewId: data.preview_id,
        orderPreview: data.order_preview,
        parsedIntent: data.parsed_intent || null,
        rawText: userText,
        previewStatus: 'pending',
      }),
    )
    return
  }

  applyIntent(null)
  messages.value.push(pushAssistant({ content: data.message }))
}

async function handleSubmitForm(originalText: string) {
  if (!isFormValid.value) return

  loading.value = true
  await nextTick()
  scrollToBottom()

  const filled = {
    action: form.action,
    symbol: form.symbol,
    amount: form.amount,
    amount_type: form.amount_type,
  }

  // 把用户提交的信息也作为一条消息流，方便上下文中可见
  messages.value.push({
    role: 'user',
    content: `补充参数：${formatFilledSummary(filled)}`,
    timestamp: new Date(),
  })

  try {
    const data = await callAgent(originalText, filled)
    applyIntent(null)
    messages.value.push({
      role: 'assistant',
      content: data.success ? data.message : `错误: ${data.message}`,
      timestamp: new Date(),
    })
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '请求失败: ' + (error instanceof Error ? error.message : '未知错误'),
      timestamp: new Date(),
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function handleCancelForm(index: number) {
  // 取消补全：追加一条提示消息，并清空表单状态
  messages.value.splice(index, 1)
  applyIntent(null)
  messages.value.push({
    role: 'assistant',
    content: '已取消这次下单，你可以重新告诉我你的需求。',
    timestamp: new Date(),
  })
  scrollToBottom()
}

// ==================== 预览订单：确认 / 取消 / 补充文案 ====================

async function handleConfirmOrder(messageIndex: number) {
  const msg = messages.value[messageIndex]
  if (!msg || !msg.previewId || !msg.parsedIntent) return
  if (loading.value) return

  loading.value = true
  await nextTick()
  scrollToBottom()

  try {
    const data = await agentConfirm(
      msg.rawText || '',
      msg.previewId,
      msg.parsedIntent,
      accountType.value,
    )

    // 标记预览状态为 confirmed
    msg.previewStatus = 'confirmed'

    const accType = data.account_type || accountType.value
    const accZh = data.account_type_zh || ACCOUNT_TYPE_LABEL[accType]

    // 把确认结果作为新消息追加
    messages.value.push({
      role: 'assistant',
      content: data.success ? data.message : `错误: ${data.message}`,
      timestamp: new Date(),
      accountType: accType,
      accountTypeZh: accZh,
    })
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content:
        '确认下单请求失败: ' +
        (error instanceof Error ? error.message : '未知错误'),
      timestamp: new Date(),
      accountType: accountType.value,
      accountTypeZh: ACCOUNT_TYPE_LABEL[accountType.value],
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function handleCancelPreview(messageIndex: number) {
  const msg = messages.value[messageIndex]
  if (!msg) return
  msg.previewStatus = 'cancelled'
  messages.value.push({
    role: 'assistant',
    content:
      '已取消这次下单预览。如果你有补充说明（比如想改成限价单、改金额），请直接在下方输入框里告诉我。',
    timestamp: new Date(),
    accountType: msg.accountType,
    accountTypeZh: msg.accountTypeZh,
  })
  scrollToBottom()
}

function formatFilledSummary(filled: Record<string, any>): string {
  const parts: string[] = []
  if (filled.action === 'buy') parts.push('买入')
  else if (filled.action === 'sell') parts.push('卖出')
  if (filled.symbol) parts.push(filled.symbol)
  if (filled.amount) parts.push(`${filled.amount} USDT`)
  return parts.join(' · ')
}

async function handleReset() {
  try {
    await agentReset()
  } catch (e) {
    console.error('重置失败:', e)
  }
  messages.value = []
  applyIntent(null)
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<style scoped>
.agent-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f5f5;
  border-radius: 12px;
  overflow: hidden;
}

/* ==================== 顶部账户类型开关 ==================== */

.account-type-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
}

.account-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
}

.toggle-group {
  display: inline-flex;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 2px;
}

.toggle-btn {
  border: none;
  background: transparent;
  padding: 6px 14px;
  font-size: 13px;
  color: #6b7280;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.toggle-btn:hover:not(:disabled) {
  color: #111827;
}

.toggle-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.toggle-btn.toggle-active {
  background: #ffffff;
  color: #111827;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

/* ==================== 账户类型标签（消息头部）==================== */

.account-tag {
  display: inline-block;
  padding: 1px 8px;
  font-size: 11px;
  border-radius: 10px;
  margin-left: 6px;
  line-height: 1.5;
  font-weight: 500;
}

.tag-spot {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
}

.tag-futures {
  background: #fef3c7;
  color: #b45309;
  border: 1px solid #fcd34d;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 92%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: #2196f3;
}

.message.assistant .message-avatar {
  background: #4caf50;
}

.message-content {
  background: white;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message.user .message-content {
  background: #2196f3;
  color: white;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  opacity: 0.7;
}

.message-body {
  line-height: 1.6;
  font-size: 14px;
}

.loading-text {
  color: #999;
  font-style: italic;
}

.thinking-indicator {
  display: flex;
  gap: 4px;
}

.thinking-indicator .dot {
  width: 6px;
  height: 6px;
  background: #4caf50;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.thinking-indicator .dot:nth-child(1) { animation-delay: -0.32s; }
.thinking-indicator .dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: white;
  border-top: 1px solid #e0e0e0;
}

.input-area textarea {
  flex: 1;
  padding: 8px 14px;
  border: 1px solid #ddd;
  border-radius: 20px;
  resize: none;
  font-size: 14px;
  line-height: 20px;
  min-height: 0;
  height: 36px;
  max-height: 36px;
  overflow-y: auto;
  outline: none;
  transition: border-color 0.2s;
}

.input-area textarea:focus {
  border-color: #2196f3;
}

.send-btn {
  height: 36px;
  padding: 0 20px;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-weight: 500;
  font-size: 14px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #1976d2;
}

.send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.reset-btn {
  height: 36px;
  padding: 0 14px;
  background: #f5f5f5;
  color: #666;
  border: 1px solid #ddd;
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.reset-btn:hover:not(:disabled) {
  background: #e0e0e0;
}

.reset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.code-block {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 12px;
}

code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 13px;
}

/* ===== 参数补全表单 ===== */
.order-form {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e0e0e0;
  color: #333;
}

.form-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 8px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 6px 14px;
  font-size: 13px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s;
  color: #333;
}

.chip:hover:not(:disabled) {
  border-color: #2196f3;
  color: #2196f3;
}

.chip-active {
  background: #2196f3;
  color: white;
  border-color: #2196f3;
}

.chip-required {
  border-color: #ff9800;
  box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.1);
}

.chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.text-input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.text-input:focus {
  border-color: #2196f3;
}

.input-required {
  border-color: #ff9800;
  background: #fff8e1;
}

.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

.cancel-btn,
.submit-btn {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  font-size: 14px;
  transition: all 0.15s;
}

.cancel-btn {
  background: #f5f5f5;
  color: #666;
  border: 1px solid #ddd;
}

.cancel-btn:hover:not(:disabled) {
  background: #e0e0e0;
}

.submit-btn {
  background: #4caf50;
  color: white;
}

.submit-btn:hover:not(:disabled) {
  background: #43a047;
}

.submit-btn:disabled,
.cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ==================== 订单预览卡片 ==================== */

.order-preview {
  margin-top: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fafbfc;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #f0f4f8;
  border-bottom: 1px solid #e0e0e0;
}

.preview-title {
  font-weight: 600;
  color: #2c3e50;
}

.preview-id {
  font-size: 12px;
  color: #95a5a6;
  font-family: 'Courier New', monospace;
}

.preview-grid {
  padding: 12px 14px;
}

.preview-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed #ecf0f1;
}

.preview-row:last-child {
  border-bottom: none;
}

.preview-label {
  color: #7f8c8d;
  font-size: 14px;
}

.preview-value {
  font-weight: 600;
  color: #2c3e50;
}

.amount-value {
  color: #e67e22;
  font-size: 15px;
}

.action-tag {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  color: white;
}

.action-buy {
  background: #27ae60;
}

.action-sell {
  background: #e74c3c;
}

.preview-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 10px 14px;
  background: #f8f9fa;
  border-top: 1px solid #e0e0e0;
}

.preview-status {
  text-align: center;
  padding: 8px 14px;
  font-size: 13px;
  background: #f8f9fa;
  border-top: 1px solid #e0e0e0;
}

.preview-status.cancelled {
  color: #95a5a6;
}

.preview-status.confirmed {
  color: #27ae60;
}
</style>