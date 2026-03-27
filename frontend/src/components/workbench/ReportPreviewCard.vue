<script setup>
defineProps({
  report: { type: Object, required: true },
})
</script>

<template>
  <details class="artifact-card" open>
    <summary>
      <span>Report Preview</span>
      <span>{{ report.content ? 'ready' : 'drafting' }}</span>
    </summary>
    <div class="report-preview">
      <strong>{{ report.title }}</strong>
      <div v-if="report.outline?.length" class="outline-list">
        <span v-for="section in report.outline" :key="section" class="outline-chip">{{ section }}</span>
      </div>
      <pre class="report-content">{{ report.content || 'The report draft will stream in here when the workflow reaches the report stage.' }}</pre>
    </div>
  </details>
</template>
