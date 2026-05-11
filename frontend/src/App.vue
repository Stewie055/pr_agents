<script setup lang="ts">
import { computed, ref } from "vue";
import {
  createCase,
  exportCaseTrace,
  getCase,
  getCaseTrace,
  sendMessage,
  uploadDataset,
  type Artifact,
  type CaseSnapshot,
  type CaseTrace
} from "./api";

const caseTitle = ref("设备性能异常诊断案例");
const message = ref("请分析这份设备性能数据，给出诊断、证据和建议。");
const loading = ref(false);
const traceLoading = ref(false);
const error = ref("");
const snapshot = ref<CaseSnapshot | null>(null);
const trace = ref<CaseTrace | null>(null);

const activeDatasetId = computed(() => snapshot.value?.datasets.at(-1)?.id);
const latestDatasetName = computed(() => snapshot.value?.datasets.at(-1)?.filename);
const hasDataset = computed(() => Boolean(activeDatasetId.value));
const artifacts = computed<Artifact[]>(() => snapshot.value?.artifacts ?? []);
const report = computed(() => artifacts.value.find((item) => item.kind === "report"));
const traceSteps = computed(() => trace.value?.agent_steps ?? snapshot.value?.agent_steps ?? []);
const llmEvents = computed(() => trace.value?.llm_audit_events ?? []);
const sendButtonText = computed(() => (loading.value ? (hasDataset.value ? "正在分析..." : "正在回复...") : hasDataset.value ? "发送并分析" : "发送"));
const caseStateText = computed(() => {
  if (!snapshot.value) {
    return "尚未创建案例";
  }
  if (hasDataset.value) {
    return `数据已就绪：${latestDatasetName.value}`;
  }
  return "等待上传设备性能 CSV";
});

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderMarkdown(value: string) {
  let html = escapeHtml(value);
  html = html.replace(/^### (.*)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.*)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.*)$/gm, "<h2>$1</h2>");
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/^- (.*)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  return html.replace(/\n/g, "<br />");
}

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

async function ensureCase() {
  if (snapshot.value) {
    return snapshot.value.case.id;
  }
  const diagnosticCase = await createCase(caseTitle.value);
  snapshot.value = await getCase(diagnosticCase.id);
  return diagnosticCase.id;
}

async function handleCreateCase() {
  loading.value = true;
  error.value = "";
  try {
    const diagnosticCase = await createCase(caseTitle.value);
    snapshot.value = await getCase(diagnosticCase.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "创建案例失败";
  } finally {
    loading.value = false;
  }
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) {
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const caseId = await ensureCase();
    await uploadDataset(caseId, file);
    snapshot.value = await getCase(caseId);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "上传失败";
  } finally {
    loading.value = false;
    input.value = "";
  }
}

async function handleSend() {
  if (!message.value.trim()) {
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const caseId = await ensureCase();
    await sendMessage(caseId, message.value, activeDatasetId.value);
    snapshot.value = await getCase(caseId);
    trace.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Agent 调用失败";
  } finally {
    loading.value = false;
  }
}

async function loadTrace() {
  if (!snapshot.value) {
    return;
  }
  traceLoading.value = true;
  error.value = "";
  try {
    trace.value = await getCaseTrace(snapshot.value.case.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载 Trace 失败";
  } finally {
    traceLoading.value = false;
  }
}

async function downloadTrace() {
  if (!snapshot.value) {
    return;
  }
  traceLoading.value = true;
  error.value = "";
  try {
    const blob = await exportCaseTrace(snapshot.value.case.id);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "agent-trace.json";
    link.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "导出 Trace 失败";
  } finally {
    traceLoading.value = false;
  }
}
</script>

<template>
  <main class="workspace">
    <aside class="sidebar">
      <div>
        <p class="eyebrow">Diagnostic Case</p>
        <h1>半导体设备性能诊断</h1>
      </div>

      <label class="field">
        <span>案例名称</span>
        <input v-model="caseTitle" />
      </label>

      <button :disabled="loading" @click="handleCreateCase">新建案例</button>

      <label class="upload">
        <span>上传性能 CSV</span>
        <input type="file" accept=".csv,text/csv" @change="handleUpload" />
      </label>

      <section v-if="snapshot" class="case-meta">
        <strong>{{ snapshot.case.title }}</strong>
        <span>{{ snapshot.case.equipment_type }}</span>
        <span>{{ caseStateText }}</span>
      </section>
    </aside>

    <section class="chat">
      <header>
        <p class="eyebrow">Agent</p>
        <h2>辅助诊断对话</h2>
        <p class="state-line">{{ caseStateText }}</p>
      </header>

      <div class="messages">
        <article v-for="item in snapshot?.messages ?? []" :key="item.id" :class="['message', item.role]">
          <strong>{{ item.role }}</strong>
          <div class="message-content" v-html="renderMarkdown(item.content)" />
        </article>
      </div>

      <div class="composer">
        <textarea v-model="message" rows="4" />
        <button :disabled="loading" @click="handleSend">{{ sendButtonText }}</button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <aside class="artifacts">
      <header>
        <p class="eyebrow">Evidence</p>
        <h2>证据与报告</h2>
      </header>

      <section class="tool-trace">
        <h3>工具轨迹</h3>
        <ol>
          <li v-for="trace in snapshot?.tool_traces ?? []" :key="trace.id">
            <strong>{{ trace.tool_name }}</strong>
            <span>{{ trace.status }}</span>
            <p>{{ trace.result_summary }}</p>
          </li>
        </ol>
      </section>

      <section class="trace-debug">
        <div class="trace-debug-header">
          <h3>Trace 调试台</h3>
          <div>
            <button :disabled="!snapshot || traceLoading" @click="loadTrace">{{ traceLoading ? "加载中..." : "刷新" }}</button>
            <button :disabled="!snapshot || traceLoading" @click="downloadTrace">导出 JSON</button>
          </div>
        </div>

        <ol v-if="traceSteps.length" class="trace-timeline">
          <li v-for="step in traceSteps" :key="step.id">
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

        <details v-if="llmEvents.length" class="llm-events">
          <summary>LLM 调用 {{ llmEvents.length }} 次</summary>
          <article v-for="event in llmEvents" :key="event.id">
            <strong>{{ event.provider }} / {{ event.model }}</strong>
            <span>{{ event.duration_ms }} ms</span>
            <p v-if="event.error">{{ event.error }}</p>
            <details>
              <summary>request / response</summary>
              <pre>{{ formatJson({ request: event.request, response: event.response }) }}</pre>
            </details>
          </article>
        </details>
      </section>

      <section>
        <h3>Artifacts</h3>
        <article v-for="artifact in artifacts" :key="artifact.id" class="artifact">
          <span>{{ artifact.kind }}</span>
          <strong>{{ artifact.title }}</strong>
          <p>{{ artifact.summary }}</p>
        </article>
      </section>

      <section v-if="report" class="report">
        <h3>报告草稿</h3>
        <article v-for="section in (report.data.sections as Array<{ heading: string; body: string }> || [])" :key="section.heading">
          <strong>{{ section.heading }}</strong>
          <p>{{ section.body }}</p>
        </article>
      </section>
    </aside>
  </main>
</template>
