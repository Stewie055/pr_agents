<script setup>
defineProps({
  items: { type: Array, default: () => [] },
})
</script>

<template>
  <details class="artifact-card" open>
    <summary>
      <span>Diagnosis Summary</span>
      <span>{{ items.length ? `${items.length} findings` : 'pending' }}</span>
    </summary>
    <ul v-if="items.length" class="summary-list">
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
    <div v-else class="artifact-empty">The agent will summarize metrics, anomalies, and likely causes here.</div>
  </details>
</template>
