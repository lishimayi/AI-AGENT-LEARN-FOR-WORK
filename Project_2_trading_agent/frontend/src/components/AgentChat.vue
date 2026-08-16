<template>
  <div class="agent-chat">
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
            <span class="time">{{ formatTime(msg.timestamp) }}</span>
          </div>

          <!-- 普通文本消息 -->
          <div
            v-if="!msg.needsInput"
            class="message-body"
            v-html="formatContent(msg.content)"
          ></div>

          <!-- 参数补全表单 -->
          <div v-else class="order-form">
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
        rows="2"
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
import { ref, nextTick, reactive, computed } from 'vue'
import { agentChat, agentReset } from '../api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  needsInput?: boolean
  rawText?: string
  missingFields?: string[]
  parsedIntent?: Record<string, any> | null
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
  return agentChat(message, filledFields)
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({
    role: 'user',
    content: text,
    timestamp: new Date(),
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
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function handleAgentResponse(data: AgentResponse, userText: string) {
  if (!data.success) {
    messages.value.push({
      role: 'assistant',
      content: `错误: ${data.message}`,
      timestamp: new Date(),
    })
    return
  }

  if (data.needs_input) {
    currentMissing = data.missing_fields || []
    resetForm(data.parsed_intent)

    messages.value.push({
      role: 'assistant',
      content: data.message,
      timestamp: new Date(),
      needsInput: true,
      rawText: userText,
      missingFields: data.missing_fields || [],
      parsedIntent: data.parsed_intent || null,
    })
    return
  }

  applyIntent(null)
  messages.value.push({
    role: 'assistant',
    content: data.message,
    timestamp: new Date(),
  })
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
  gap: 12px;
  padding: 16px;
  background: white;
  border-top: 1px solid #e0e0e0;
}

.input-area textarea {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #ddd;
  border-radius: 24px;
  resize: none;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.input-area textarea:focus {
  border-color: #2196f3;
}

.send-btn {
  padding: 10px 24px;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 24px;
  cursor: pointer;
  font-weight: 500;
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
  padding: 10px 16px;
  background: #f5f5f5;
  color: #666;
  border: 1px solid #ddd;
  border-radius: 24px;
  cursor: pointer;
  font-size: 13px;
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
</style>