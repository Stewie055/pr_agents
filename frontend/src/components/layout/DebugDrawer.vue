<script setup>
defineProps({
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle'])
</script>

<template>
  <div class="debug-drawer" :class="{ open }">
    <button class="drawer-handle" data-testid="debug-drawer-toggle" @click="emit('toggle')">
      {{ open ? 'Hide Debug' : 'Show Debug' }}
    </button>
    <div v-if="open" class="drawer-body">
      <slot />
    </div>
  </div>
</template>
