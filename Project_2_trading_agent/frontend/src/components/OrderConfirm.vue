<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="handleCancel">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
      <!-- 头部 -->
      <div class="bg-yellow-50 px-6 py-4 border-b border-yellow-200">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h3 class="text-lg font-semibold text-yellow-800">确认下单</h3>
            <p class="text-sm text-yellow-600">请仔细核对订单信息</p>
          </div>
        </div>
      </div>

      <!-- 订单详情 -->
      <div class="px-6 py-5 space-y-3">
        <!-- 操作类型 -->
        <div class="flex items-center justify-between py-2 border-b border-gray-100">
          <span class="text-gray-500">操作</span>
          <span :class="parsedOrder.action === 'buy' ? 'text-green-600' : 'text-red-600'" class="font-semibold text-lg">
            {{ parsedOrder.action === 'buy' ? '买入' : '卖出' }}
          </span>
        </div>

        <!-- 交易对 -->
        <div class="flex items-center justify-between py-2 border-b border-gray-100">
          <span class="text-gray-500">交易对</span>
          <span class="font-mono font-semibold text-gray-800">{{ parsedOrder.symbol }}</span>
        </div>

        <!-- 订单类型 -->
        <div class="flex items-center justify-between py-2 border-b border-gray-100">
          <span class="text-gray-500">订单类型</span>
          <span class="px-3 py-1 rounded-full text-sm font-medium"
            :class="parsedOrder.order_type === 'market' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'">
            {{ parsedOrder.order_type === 'market' ? '市价单' : '限价单' }}
          </span>
        </div>

        <!-- 数量/金额 -->
        <div class="flex items-center justify-between py-2 border-b border-gray-100">
          <span class="text-gray-500">{{ parsedOrder.amount_type === 'quote' ? '买入金额' : '买入数量' }}</span>
          <span class="font-semibold text-lg text-gray-800">
            {{ parsedOrder.amount }}
            <span class="text-sm font-normal text-gray-500">
              {{ parsedOrder.amount_type === 'quote' ? 'USDT' : parsedOrder.symbol.replace('USDT', '') }}
            </span>
          </span>
        </div>

        <!-- 限价价格 -->
        <div v-if="parsedOrder.price" class="flex items-center justify-between py-2 border-b border-gray-100">
          <span class="text-gray-500">限价价格</span>
          <span class="font-semibold text-gray-800">${{ parsedOrder.price }}</span>
        </div>

        <!-- 止损价格 -->
        <div v-if="parsedOrder.stop_price" class="flex items-center justify-between py-2 border-b border-gray-100">
          <span class="text-gray-500">止损价格</span>
          <span class="font-semibold text-orange-600">${{ parsedOrder.stop_price }}</span>
        </div>

        <!-- 账户余额 -->
        <div v-if="!loadingBalances" class="mt-4 p-3 bg-gray-50 rounded-lg space-y-2">
          <p class="text-xs text-gray-500 font-medium">账户余额</p>
          
          <!-- 现货账户 -->
          <div class="flex justify-between text-sm">
            <span class="text-gray-600">现货账户</span>
            <span class="font-medium text-gray-800">
              {{ spotBalance }} USDT
              <span v-if="orderAmount > 0 && spotBalance > 0" class="text-xs text-gray-400">
                ({{ orderPercent }}%)
              </span>
            </span>
          </div>
          
          <!-- 合约账户 -->
          <div class="flex justify-between text-sm">
            <span class="text-gray-600">合约账户</span>
            <span class="font-medium text-gray-800">
              {{ futuresBalance }} USDT
              <span v-if="orderAmount > 0 && futuresBalance > 0" class="text-xs text-gray-400">
                ({{ futuresPercent }}%)
              </span>
            </span>
          </div>
        </div>

        <!-- 加载余额中 -->
        <div v-else class="mt-4 p-3 bg-gray-50 rounded-lg">
          <div class="flex items-center gap-2 text-sm text-gray-500">
            <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            加载余额中...
          </div>
        </div>

        <!-- AI解析说明 -->
        <div v-if="parsedOrder.reasoning" class="mt-2 p-3 bg-blue-50 rounded-lg">
          <p class="text-xs text-blue-500 mb-1">AI理解</p>
          <p class="text-sm text-gray-700 italic">"{{ parsedOrder.reasoning }}"</p>
        </div>
      </div>

      <!-- 按钮 -->
      <div class="px-6 py-4 bg-gray-50 flex gap-3">
        <button
          @click="handleCancel"
          class="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-100 transition-colors"
        >
          取消
        </button>
        <button
          @click="handleConfirm"
          :disabled="loading"
          :class="parsedOrder.action === 'buy' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'"
          class="flex-1 px-4 py-2.5 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
        >
          {{ loading ? '处理中...' : '确认下单' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { ParsedOrder } from '../api'

const props = defineProps<{
  parsedOrder: ParsedOrder
  loading: boolean
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

// 余额数据
const spotBalance = ref('0.00')
const futuresBalance = ref('0.00')
const loadingBalances = ref(true)

// 计算订单金额（USDT）
const orderAmount = computed(() => {
  if (props.parsedOrder.amount_type === 'quote') {
    return props.parsedOrder.amount || 0
  }
  // 如果是数量模式，需要获取当前价格计算
  return 0
})

// 计算下单比例
const orderPercent = computed(() => {
  if (orderAmount.value <= 0 || parseFloat(spotBalance.value) <= 0) return '0'
  const percent = (orderAmount.value / parseFloat(spotBalance.value)) * 100
  return percent.toFixed(1)
})

const futuresPercent = computed(() => {
  if (orderAmount.value <= 0 || parseFloat(futuresBalance.value) <= 0) return '0'
  const percent = (orderAmount.value / parseFloat(futuresBalance.value)) * 100
  return percent.toFixed(1)
})

async function fetchBalances() {
  loadingBalances.value = true
  try {
    const response = await fetch('http://localhost:8000/api/balances')
    const data = await response.json()
    
    if (data.success) {
      // 现货余额
      if (data.spot.USDT) {
        spotBalance.value = data.spot.USDT.free.toFixed(2)
      }
      // 合约余额
      if (data.futures.USDT) {
        futuresBalance.value = data.futures.USDT.free.toFixed(2)
      }
    }
  } catch (error) {
    console.error('获取余额失败:', error)
  } finally {
    loadingBalances.value = false
  }
}

onMounted(() => {
  fetchBalances()
})

function handleConfirm() {
  emit('confirm')
}

function handleCancel() {
  emit('cancel')
}
</script>
