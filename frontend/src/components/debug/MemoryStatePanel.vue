<script setup>
defineProps({
  memory: { type: Object, required: true },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle'])
</script>

<template>
  <details class="debug-panel" :open="open" @toggle="emit('toggle')">
    <summary>Memory State</summary>
    <div class="debug-item">
      <div><strong>Factory</strong>: {{ memory.currentFactory }}</div>
      <div><strong>Focus</strong>: {{ memory.currentFocus }}</div>
      <div><strong>Confirmed Issues</strong>: {{ memory.confirmedIssues.join(' | ') || 'None' }}</div>
      <div><strong>Tentative Conclusions</strong>: {{ memory.tentativeConclusions.join(' | ') || 'None' }}</div>
      <div><strong>Latest Task Summary</strong>: {{ JSON.stringify(memory.latestTaskSummary) }}</div>
    </div>
  </details>
</template>
