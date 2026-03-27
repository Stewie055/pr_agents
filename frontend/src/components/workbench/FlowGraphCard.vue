<script setup>
defineProps({
  nodes: { type: Array, default: () => [] },
})
</script>

<template>
  <details class="workbench-card" open>
    <summary>
      <span>Flow Graph</span>
      <span>{{ nodes.length }} stages</span>
    </summary>
    <div class="flow-graph">
      <div v-for="node in nodes" :key="node.id" class="flow-node" :data-status="node.status">
        <div class="flow-node-dot" />
        <div class="flow-node-copy">
          <strong>{{ node.label }}</strong>
          <span>{{ node.status.replace('_', ' ') }}</span>
        </div>
      </div>
    </div>
  </details>
</template>
