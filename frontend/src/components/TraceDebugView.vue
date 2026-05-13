<script setup lang="ts">
import type { AgentStep, CaseTrace, LLMAuditEvent } from "../api";

defineProps<{
  snapshotExists: boolean;
  trace: CaseTrace | null;
  fallbackSteps: AgentStep[];
  loading: boolean;
  llmEvents: LLMAuditEvent[];
}>();

const emit = defineEmits<{
  close: [];
  refresh: [];
  download: [];
}>();

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function toolCallNames(event: LLMAuditEvent) {
  return event.response_summary?.tool_calls?.map((item) => item.name || item.id || "tool").join(", ") ?? "";
}
</script>

<template>
  <main class="debug-workspace">
    <header class="debug-topbar">
      <div>
        <p class="eyebrow">Trace Debug</p>
        <h1>Agent 调试台</h1>
      </div>
      <div class="debug-actions">
        <button @click="emit('close')">返回主界面</button>
        <button :disabled="!snapshotExists || loading" @click="emit('refresh')">{{ loading ? "加载中..." : "刷新 Trace" }}</button>
        <button :disabled="!snapshotExists || loading" @click="emit('download')">导出 JSON</button>
      </div>
    </header>

    <section v-if="!snapshotExists" class="debug-empty">
      <p>请先在主界面创建案例，然后从案例入口打开调试台。</p>
    </section>

    <section v-else class="debug-grid">
      <section class="debug-panel">
        <h2>Agent Steps</h2>
        <ol v-if="(trace?.agent_steps ?? fallbackSteps).length" class="trace-timeline">
          <li v-for="step in trace?.agent_steps ?? fallbackSteps" :key="step.id">
            <strong>{{ step.step_index }} · {{ step.phase }}</strong>
            <span>{{ step.duration_ms ?? 0 }} ms</span>
            <p v-if="step.stop_reason">stop: {{ step.stop_reason }}</p>
            <details v-if="step.tool_calls?.length || step.observations?.length || step.llm_metadata">
              <summary>查看 step JSON</summary>
              <pre>{{ formatJson(step) }}</pre>
            </details>
          </li>
        </ol>
        <p v-else class="empty-trace">暂无 Agent step trace。</p>
      </section>

      <section class="debug-panel">
        <h2>LLM Audit</h2>
        <article v-for="event in llmEvents" :key="event.id" class="llm-event">
          <strong>{{ event.provider }} / {{ event.model }}</strong>
          <span>{{ event.duration_ms }} ms</span>
          <p v-if="event.error">{{ event.error }}</p>
          <section v-else-if="event.response_summary" class="llm-response-summary">
            <p v-if="event.response_summary.content">{{ event.response_summary.content }}</p>
            <p v-else-if="event.response_summary.tool_calls?.length">tool calls: {{ toolCallNames(event) }}</p>
            <small>
              {{ event.response_summary.stream ? `stream · ${event.response_summary.chunk_count ?? 0} chunks` : "non-stream" }}
              <template v-if="event.response_summary.finish_reason"> · {{ event.response_summary.finish_reason }}</template>
            </small>
          </section>
          <details>
            <summary>raw request / response</summary>
            <pre>{{ formatJson({ request: event.request, response_summary: event.response_summary, response: event.response }) }}</pre>
          </details>
        </article>
        <p v-if="!llmEvents.length" class="empty-trace">暂无 LLM 调用记录。</p>
      </section>
    </section>
  </main>
</template>
