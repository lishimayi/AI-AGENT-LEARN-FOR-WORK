<script setup lang="ts">
import AgentChat from './components/AgentChat.vue'
</script>

<template>
  <div class="min-h-screen bg-gray-100">
    <!-- 头部 -->
    <header class="bg-white shadow-sm">
      <div class="max-w-2xl mx-auto px-4 py-4">
        <h1 class="text-xl font-bold text-gray-800">交易Agent</h1>
        <p class="text-sm text-gray-500 mt-1">用自然语言下单，由 AI 帮你执行</p>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="max-w-2xl mx-auto px-4 py-6">
      <div class="bg-white rounded-lg shadow-sm overflow-hidden" style="height: 640px;">
        <AgentChat />
      </div>

      <!-- 使用提示 -->
      <div class="mt-6 bg-white rounded-lg p-4 border border-gray-200">
        <h3 class="font-medium text-gray-700 mb-2">使用示例</h3>
        <ul class="text-sm text-gray-600 space-y-1">
          <li>• "帮我买100美元的BTC"</li>
          <li>• "买入0.5个以太坊"</li>
          <li>• "在50000美元价格买入比特币"</li>
          <li>• "如果BTC跌到45000就卖掉0.1个"</li>
          <li>• "我的USDT余额是多少？"</li>
        </ul>
      </div>
    </main>

    <!-- 底部 -->
    <footer class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 py-3">
      <div class="max-w-2xl mx-auto px-4 text-center text-xs text-gray-400">
        注意：仅使用测试网，请勿用于真实交易
      </div>
    </footer>
  </div>
</template>