<script setup>
const props = defineProps({
  prompt: { type: String, default: '' },
  status: { type: String, default: 'Ready.' },
  attachments: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:prompt', 'send', 'files'])

function onFilesChange(event) {
  emit('files', Array.from(event.target.files || []))
}
</script>

<template>
  <section class="composer-card">
    <div class="composer-header">
      <div>
        <div class="eyebrow">Message</div>
        <p class="composer-copy">Use natural language to launch a diagnostic run. Attachments are kept as local mock input in this demo.</p>
      </div>
      <label class="upload-button">
        Attach File
        <input type="file" multiple @change="onFilesChange" />
      </label>
    </div>

    <div v-if="attachments.length" class="attachment-list">
      <span v-for="attachment in attachments" :key="attachment.name" class="attachment-chip">{{ attachment.name }}</span>
    </div>

    <textarea
      :value="prompt"
      data-testid="prompt"
      class="composer-input"
      @input="emit('update:prompt', $event.target.value)"
      @keydown.enter.exact.prevent="emit('send')"
    />

    <div class="composer-footer">
      <div class="composer-status" data-testid="status">{{ status }}</div>
      <button class="send-button" :disabled="!prompt.trim()" data-testid="send-message" @click="emit('send')">Send</button>
    </div>
  </section>
</template>
