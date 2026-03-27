<script setup>
defineProps({
  status: { type: Object, required: true },
})
</script>

<template>
  <section class="global-status-bar" :data-state="status.status?.toLowerCase()" data-testid="global-status">
    <div class="status-pill">
      <span class="status-label">Running Step</span>
      <strong>{{ status.runningStep }}</strong>
    </div>
    <div class="status-pill">
      <span class="status-label">Tool</span>
      <strong>{{ status.activeTool }}</strong>
    </div>
    <div class="status-pill">
      <span class="status-label">Status</span>
      <strong>{{ status.status }}</strong>
    </div>
    <div class="status-pill">
      <span class="status-label">Elapsed</span>
      <strong>{{ status.elapsedTime }}</strong>
    </div>
    <div class="status-pill">
      <span class="status-label">Steps</span>
      <strong>{{ status.stepCount }}</strong>
    </div>
  </section>
</template>
