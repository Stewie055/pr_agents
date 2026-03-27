<script setup>
defineProps({
  step: { type: Object, required: true },
})
</script>

<template>
  <details class="workbench-card" open>
    <summary>
      <span>Current Step</span>
      <span>{{ step.status }}</span>
    </summary>
    <div class="detail-grid">
      <div>
        <div class="eyebrow">Step</div>
        <p>{{ step.title }}</p>
      </div>
      <div>
        <div class="eyebrow">Tool</div>
        <p>{{ step.tool || 'N/A' }}</p>
      </div>
      <div class="detail-span">
        <div class="eyebrow">Summary</div>
        <p>{{ step.summary }}</p>
      </div>
    </div>
  </details>
</template>
