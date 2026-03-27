<script setup>
defineProps({
  logs: { type: Array, default: () => [] },
})
</script>

<template>
  <details class="workbench-card" open>
    <summary>
      <span>Task Log</span>
      <span>{{ logs.length }} entries</span>
    </summary>
    <div class="task-log-list">
      <div v-for="entry in logs" :key="entry.id" class="task-log-item" :data-level="entry.level">
        <span class="task-log-time">{{ new Date(entry.timestamp).toLocaleTimeString() }}</span>
        <span class="task-log-message">{{ entry.message }}</span>
      </div>
    </div>
  </details>
</template>
