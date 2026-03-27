<script setup>
defineProps({
  drawerOpen: { type: Boolean, default: false },
})
</script>

<template>
  <div class="workspace-shell" :class="{ 'debug-open': drawerOpen }">
    <aside class="chat-column">
      <slot name="chat" />
    </aside>
    <section class="workbench-column">
      <slot name="workbench" />
    </section>
    <aside class="debug-column">
      <slot name="debug" />
    </aside>
    <footer class="status-column">
      <slot name="status" />
    </footer>
  </div>
</template>
