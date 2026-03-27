<script setup>
defineProps({
  messages: { type: Array, default: () => [] },
})
</script>

<template>
  <section class="chat-message-list" data-testid="messages">
    <div v-if="!messages.length" class="empty-card">
      <h3>No diagnostic run yet</h3>
      <p>Use a guided prompt or ask the agent to inspect metrics, identify faults, and prepare a report draft.</p>
    </div>
    <article
      v-for="message in messages"
      :key="message.message_id"
      class="chat-message"
      :class="message.role"
      :data-testid="message.metadata?.live ? 'live-assistant' : `message-${message.role}`"
    >
      <div class="message-role">{{ message.role === 'user' ? 'Operator' : 'Agent' }}</div>
      <div class="message-text">{{ message.content }}</div>
    </article>
  </section>
</template>
