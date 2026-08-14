<template>
  <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
    <div class="flex items-center gap-2 mb-3">
      <span class="text-blue-600">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
        </svg>
      </span>
      <span class="font-medium text-blue-800">订单预览</span>
    </div>

    <div class="space-y-2 text-sm">
      <div class="flex items-center gap-4">
        <span class="text-gray-600 w-20">操作:</span>
        <span :class="parsedOrder.action === 'buy' ? 'text-green-600' : 'text-red-600'" class="font-semibold">
          {{ parsedOrder.action === 'buy' ? '买入' : '卖出' }}
        </span>
      </div>

      <div class="flex items-center gap-4">
        <span class="text-gray-600 w-20">交易对:</span>
        <span class="font-mono font-semibold">{{ parsedOrder.symbol }}</span>
      </div>

      <div class="flex items-center gap-4">
        <span class="text-gray-600 w-20">数量:</span>
        <span class="font-semibold">
          {{ parsedOrder.amount }} {{ parsedOrder.amount_type === 'quote' ? 'USDT' : parsedOrder.symbol.replace('USDT', '') }}
        </span>
      </div>

      <div class="flex items-center gap-4">
        <span class="text-gray-600 w-20">订单类型:</span>
        <span class="px-2 py-0.5 rounded text-xs font-medium"
          :class="parsedOrder.order_type === 'market' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'">
          {{ parsedOrder.order_type === 'market' ? '市价单' : '限价单' }}
        </span>
      </div>

      <div v-if="parsedOrder.price" class="flex items-center gap-4">
        <span class="text-gray-600 w-20">价格:</span>
        <span class="font-semibold">${{ parsedOrder.price }}</span>
      </div>

      <div v-if="parsedOrder.stop_price" class="flex items-center gap-4">
        <span class="text-gray-600 w-20">止损价:</span>
        <span class="font-semibold text-orange-600">${{ parsedOrder.stop_price }}</span>
      </div>
    </div>

    <div v-if="parsedOrder.reasoning" class="mt-3 pt-3 border-t border-blue-200">
      <p class="text-sm text-gray-600 italic">"{{ parsedOrder.reasoning }}"</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ParsedOrder } from '../api'

defineProps<{
  parsedOrder: ParsedOrder
}>()
</script>
