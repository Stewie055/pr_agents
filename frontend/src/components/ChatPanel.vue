<script setup lang="ts">
import type { AgentMessage } from "../api";
import type { ProgressItem } from "../composables/useCaseSession";
import MarkdownContent from "./MarkdownContent.vue";

defineProps<{
  messages: AgentMessage[];
  draftMessage: string;
  loading: boolean;
  hasDataset: boolean;
  caseStateText: string;
  progressItems: ProgressItem[];
  error: string;
}>();

const emit = defineEmits<{
  "update:draftMessage": [value: string];
  send: [];
}>();
</script>

<template>
  <section class="chat">
    <header class="chat-header">
      <div>
        <p class="eyebrow">Agent</p>
        <h2>辅助诊断对话</h2>
        <p class="state-line">{{ caseStateText }}</p>
      </div>
      <div v-if="loading" class="stream-badge">实时分析中</div>
    </header>

    <div class="messages" data-testid="messages-scroll">
      <article v-for="item in messages" :key="item.id" :class="['message', item.role]">
        <strong>{{ item.role === "assistant" ? "assistant" : "user" }}</strong>
        <MarkdownContent :content="item.content" />
      </article>
    </div>

    <section v-if="progressItems.length" class="agent-progress" aria-label="Agent progress">
      <ol>
        <li v-for="item in progressItems" :key="item.id" :class="item.status">
          <span>{{ item.label }}</span>
          <small v-if="item.detail">{{ item.detail }}</small>
        </li>
      </ol>
    </section>

    <div class="composer">
      <textarea
        :value="draftMessage"
        rows="4"
        @input="emit('update:draftMessage', ($event.target as HTMLTextAreaElement).value)"
        @keydown.meta.enter.prevent="emit('send')"
        @keydown.ctrl.enter.prevent="emit('send')"
      />
      <button :disabled="loading || !draftMessage.trim()" @click="emit('send')">
        {{ loading ? (hasDataset ? "正在分析..." : "正在回复...") : hasDataset ? "发送并分析" : "发送" }}
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>
