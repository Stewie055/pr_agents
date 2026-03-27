<script setup>
defineProps({
  summary: { type: Object, required: true },
})
</script>

<template>
  <section class="panel-card">
    <div class="eyebrow">{{ summary.title }}</div>
    <p class="query-summary">{{ summary.content }}</p>
    <div v-if="summary.attachments?.length" class="attachment-list">
      <span v-for="attachment in summary.attachments" :key="attachment" class="attachment-chip">{{ attachment }}</span>
    </div>
  </section>
</template>
