<template>
  <div :class="result.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'" class="border rounded-lg p-4">
    <div class="flex items-center gap-2 mb-3">
      <span v-if="result.success" class="text-green-600">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
      </span>
      <span v-else class="text-red-600">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
        </svg>
      </span>
      <span :class="result.success ? 'text-green-800' : 'text-red-800'" class="font-medium">
        {{ result.success ? '下单成功' : '下单失败' }}
      </span>
    </div>

    <div class="space-y-2 text-sm">
      <div class="flex items-center gap-4">
        <span class="text-gray-600 w-20">消息:</span>
        <span :class="result.success ? 'text-green-700' : 'text-red-700'">{{ result.message }}</span>
      </div>

      <div v-if="result.order_id" class="flex items-center gap-4">
        <span class="text-gray-600 w-20">订单ID:</span>
        <span class="font-mono text-gray-800">{{ result.order_id }}</span>
      </div>

      <div v-if="result.parsed_order" class="mt-3 pt-3 border-t border-gray-200">
        <p class="text-xs text-gray-500">
          {{ result.parsed_order.action === 'buy' ? '买入' : '卖出' }} 
          {{ result.parsed_order.amount }} 
          {{ result.parsed_order.amount_type === 'quote' ? 'USDT' : result.parsed_order.symbol.replace('USDT', '') }}
          {{ result.parsed_order.symbol }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrderResponse } from '../api'

defineProps<{
  result: OrderResponse
}>()
</script>
