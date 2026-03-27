<script setup>
defineProps({
  snapshot: { type: Object, required: true },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle'])
</script>

<template>
  <details class="debug-panel" :open="open" @toggle="emit('toggle')">
    <summary>Prompt Snapshot</summary>
    <div class="debug-item">
      <div><strong>Intent</strong>: {{ snapshot.taskIntent || 'Idle' }}</div>
      <div><strong>Phase</strong>: {{ snapshot.phase }}</div>
      <div><strong>Instruction</strong>: {{ snapshot.instructionSummary }}</div>
      <div><strong>Sub Goal</strong>: {{ snapshot.subGoal }}</div>
    </div>
  </details>
</template>
