<script setup lang="ts">
import { ref } from 'vue'
import OrderInput from './components/OrderInput.vue'
import OrderPreview from './components/OrderPreview.vue'
import OrderResult from './components/OrderResult.vue'
import OrderConfirm from './components/OrderConfirm.vue'
import { placeOrder, type ParsedOrder, type OrderResponse } from './api'

const loading = ref(false)
const previewMode = ref(false)
const parsedOrder = ref<ParsedOrder | null>(null)
const pendingText = ref('')  // 保存待确认的原始输入
const showConfirmDialog = ref(false)
const orderResult = ref<OrderResponse | null>(null)
const errorMessage = ref('')

async function handleSubmit(text: string) {
  errorMessage.value = ''
  orderResult.value = null

  try {
    if (previewMode.value) {
      // 预览模式：只解析不下单
      loading.value = true
      const response = await fetch('http://localhost:8000/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ natural_language: text }),
      })
      const data = await response.json()
      parsedOrder.value = data.parsed_order
    } else {
      // 实盘模式：先解析，再弹窗确认，最后下单
      loading.value = true
      const response = await fetch('http://localhost:8000/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ natural_language: text }),
      })
      const data = await response.json()
      parsedOrder.value = data.parsed_order
      pendingText.value = text
      showConfirmDialog.value = true
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '发生未知错误'
  } finally {
    loading.value = false
  }
}

async function handleConfirm() {
  showConfirmDialog.value = false
  loading.value = true
  
  try {
    const response = await placeOrder(pendingText.value)
    orderResult.value = response
    if (response.success) {
      parsedOrder.value = null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '下单失败'
  } finally {
    loading.value = false
    pendingText.value = ''
  }
}

function handleCancel() {
  showConfirmDialog.value = false
  pendingText.value = ''
  parsedOrder.value = null
}

function resetAll() {
  parsedOrder.value = null
  orderResult.value = null
  errorMessage.value = ''
  pendingText.value = ''
  showConfirmDialog.value = false
}
</script>

<template>
  <div class="min-h-screen bg-gray-100">
    <!-- 头部 -->
    <header class="bg-white shadow-sm">
      <div class="max-w-2xl mx-auto px-4 py-4">
        <h1 class="text-xl font-bold text-gray-800">交易Agent - 自然语言下单</h1>
        <p class="text-sm text-gray-500 mt-1">使用AI理解你的交易意图</p>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="max-w-2xl mx-auto px-4 py-8">
      <!-- 模式切换 -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <span class="text-sm text-gray-600">模式:</span>
          <button
            @click="previewMode = false; resetAll()"
            :class="!previewMode ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'"
            class="px-4 py-1.5 rounded-full text-sm font-medium transition-colors"
          >
            实盘下单
          </button>
          <button
            @click="previewMode = true; resetAll()"
            :class="previewMode ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'"
            class="px-4 py-1.5 rounded-full text-sm font-medium transition-colors"
          >
            预览解析
          </button>
        </div>
        <button
          v-if="parsedOrder || orderResult"
          @click="resetAll"
          class="text-sm text-gray-500 hover:text-gray-700"
        >
          重置
        </button>
      </div>

      <!-- 输入框 -->
      <OrderInput
        :loading="loading"
        :preview-mode="previewMode"
        @submit="handleSubmit"
      />

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
        <p class="text-red-700 text-sm">{{ errorMessage }}</p>
      </div>

      <!-- 订单预览（预览模式） -->
      <div v-if="parsedOrder && previewMode" class="mt-6">
        <OrderPreview :parsed-order="parsedOrder" />
      </div>

      <!-- 订单结果 -->
      <div v-if="orderResult" class="mt-6">
        <OrderResult :result="orderResult" />
      </div>

      <!-- 使用提示 -->
      <div v-if="!parsedOrder && !orderResult" class="mt-8 bg-white rounded-lg p-4 border border-gray-200">
        <h3 class="font-medium text-gray-700 mb-2">使用示例</h3>
        <ul class="text-sm text-gray-600 space-y-1">
          <li>• "帮我买100美元的BTC"</li>
          <li>• "买入0.5个以太坊"</li>
          <li>• "在50000美元价格买入比特币"</li>
          <li>• "如果BTC跌到45000就卖掉0.1个"</li>
        </ul>
      </div>
    </main>

    <!-- 底部 -->
    <footer class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 py-3">
      <div class="max-w-2xl mx-auto px-4 text-center text-xs text-gray-400">
        注意：仅使用测试网，请勿用于真实交易
      </div>
    </footer>

    <!-- 确认弹窗 -->
    <OrderConfirm
      v-if="showConfirmDialog && parsedOrder"
      :parsed-order="parsedOrder"
      :loading="loading"
      @confirm="handleConfirm"
      @cancel="handleCancel"
    />
  </div>
</template>
