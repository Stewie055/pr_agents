<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  open: { type: Boolean, default: true },
})

const emit = defineEmits(['toggle'])
</script>

<template>
  <details class="debug-panel" :open="open" @toggle="emit('toggle')">
    <summary>Inspect Tool Calls</summary>
    <div v-if="items.length" class="debug-list">
      <article v-for="item in items" :key="item.stepId" class="debug-item">
        <strong>{{ item.toolName }}</strong>
        <div>Status: {{ item.status }}</div>
        <div>Input: {{ JSON.stringify(item.inputs) }}</div>
        <div>Output: {{ JSON.stringify(item.output) }}</div>
        <div>Duration: {{ item.duration || 'running' }}</div>
      </article>
    </div>
    <p v-else class="debug-empty">No tool calls captured yet.</p>
  </details>
</template>
