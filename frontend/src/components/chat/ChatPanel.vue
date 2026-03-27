<script setup>
import InputQueryCard from './InputQueryCard.vue'
import MessageComposer from './MessageComposer.vue'
import ProjectHeader from './ProjectHeader.vue'
import ChatMessageList from './ChatMessageList.vue'

defineProps({
  projectTitle: { type: String, required: true },
  mode: { type: String, required: true },
  querySummary: { type: Object, required: true },
  messages: { type: Array, default: () => [] },
  prompt: { type: String, default: '' },
  status: { type: String, default: 'Ready.' },
  attachments: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:prompt', 'send', 'files'])
</script>

<template>
  <div class="chat-panel">
    <ProjectHeader :title="projectTitle" :mode="mode" />
    <InputQueryCard :summary="querySummary" />
    <ChatMessageList :messages="messages" />
    <MessageComposer
      :prompt="prompt"
      :status="status"
      :attachments="attachments"
      @update:prompt="emit('update:prompt', $event)"
      @send="emit('send')"
      @files="emit('files', $event)"
    />
  </div>
</template>
