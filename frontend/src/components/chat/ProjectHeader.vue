<script setup>
defineProps({
  title: { type: String, required: true },
  mode: { type: String, default: 'llm' },
})
</script>

<template>
  <section class="panel-card">
    <div class="eyebrow">Project</div>
    <h1 class="panel-title">{{ title }}</h1>
    <p class="panel-copy">Industrial diagnostic agent workspace with observable execution and artifact-driven outputs.</p>
    <div class="mode-badge">Mode: {{ mode }}</div>
  </section>
</template>
