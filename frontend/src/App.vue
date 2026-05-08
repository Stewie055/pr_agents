<script setup lang="ts">
import { computed, ref } from "vue";
import { createCase, getCase, sendMessage, uploadDataset, type Artifact, type CaseSnapshot } from "./api";

const caseTitle = ref("设备性能异常诊断案例");
const message = ref("请分析这份设备性能数据，给出诊断、证据和建议。");
const loading = ref(false);
const error = ref("");
const snapshot = ref<CaseSnapshot | null>(null);

const activeDatasetId = computed(() => snapshot.value?.datasets.at(-1)?.id);
const artifacts = computed<Artifact[]>(() => snapshot.value?.artifacts ?? []);
const report = computed(() => artifacts.value.find((item) => item.kind === "report"));

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
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Agent 调用失败";
  } finally {
    loading.value = false;
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
        <span>{{ snapshot.datasets.length }} 个数据集</span>
      </section>
    </aside>

    <section class="chat">
      <header>
        <p class="eyebrow">Agent</p>
        <h2>辅助诊断对话</h2>
      </header>

      <div class="messages">
        <article v-for="item in snapshot?.messages ?? []" :key="item.id" :class="['message', item.role]">
          <strong>{{ item.role }}</strong>
          <p>{{ item.content }}</p>
        </article>
      </div>

      <div class="composer">
        <textarea v-model="message" rows="4" />
        <button :disabled="loading" @click="handleSend">发送并诊断</button>
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
