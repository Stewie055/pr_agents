<script setup>
defineProps({
  actions: { type: Array, default: () => [] },
})
</script>

<template>
  <details class="artifact-card" open>
    <summary>
      <span>Recommended Actions</span>
      <span>{{ actions.length ? `${actions.length} actions` : 'pending' }}</span>
    </summary>
    <div v-if="actions.length" class="recommendation-list">
      <article v-for="action in actions" :key="action.id" class="recommendation-item">
        <span class="priority-pill" :data-priority="action.priority">{{ action.priority }}</span>
        <strong>{{ action.title }}</strong>
        <p>{{ action.description }}</p>
      </article>
    </div>
    <div v-else class="artifact-empty">Prioritized mitigation steps will appear here as the diagnosis stabilizes.</div>
  </details>
</template>
