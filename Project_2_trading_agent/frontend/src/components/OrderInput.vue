<template>
  <div class="flex gap-3">
    <input
      v-model="inputText"
      type="text"
      placeholder="输入自然语言指令，如：帮我买100美元的BTC"
      class="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      :disabled="loading"
      @keyup.enter="handleSubmit"
    />
    <button
      @click="handleSubmit"
      :disabled="loading || !inputText.trim()"
      class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
    >
      {{ loading ? '处理中...' : (previewMode ? '预览' : '下单') }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  loading: boolean
  previewMode: boolean
}>()

const emit = defineEmits<{
  submit: [text: string]
}>()

const inputText = ref('')

function handleSubmit() {
  if (inputText.value.trim() && !props.loading) {
    emit('submit', inputText.value)
  }
}
</script>
