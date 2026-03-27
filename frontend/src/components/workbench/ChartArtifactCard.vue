<script setup>
defineProps({
  charts: { type: Array, default: () => [] },
})
</script>

<template>
  <details class="artifact-card" open>
    <summary>
      <span>Fault Analysis Chart</span>
      <span>{{ charts.length ? `${charts.length} ready` : 'pending' }}</span>
    </summary>
    <div v-if="charts.length" class="chart-grid">
      <article v-for="chart in charts" :key="chart.id" class="chart-preview">
        <div class="chart-canvas">
          <span>{{ chart.chartType }}</span>
        </div>
        <div class="chart-meta">
          <strong>{{ chart.title }}</strong>
          <span>Artifact: {{ chart.artifactId }}</span>
        </div>
      </article>
    </div>
    <div v-else class="artifact-empty">Chart output will appear here as soon as the analysis workflow returns the first artifact.</div>
  </details>
</template>
