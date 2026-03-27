<script setup>
defineProps({
  controls: { type: Object, required: true },
  open: { type: Boolean, default: true },
})

const emit = defineEmits(['toggle', 'pause', 'resume', 'rerun', 'modify'])
</script>

<template>
  <details class="debug-panel" :open="open" @toggle="emit('toggle')">
    <summary>Execution Controls</summary>
    <div class="control-list">
      <button class="control-button" data-testid="control-pause" @click="emit('pause')">Pause</button>
      <button class="control-button" data-testid="control-resume" @click="emit('resume')">Resume</button>
      <button class="control-button" data-testid="control-rerun" @click="emit('rerun')">Rerun Step</button>
      <button class="control-button warning" data-testid="control-modify" @click="emit('modify')">Modify State</button>
    </div>
    <p class="debug-empty">Run controls are connected to the backend control skeleton. Current paused={{ controls.paused }}, modified={{ controls.modified }}</p>
  </details>
</template>
