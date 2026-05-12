<script setup lang="ts">
defineProps<{
  caseTitle: string;
  loading: boolean;
  uploadLoading: boolean;
  caseTitleText?: string;
  equipmentType?: string;
  caseStateText: string;
  hasCase: boolean;
}>();

const emit = defineEmits<{
  "update:caseTitle": [value: string];
  create: [];
  upload: [file: File];
  debug: [];
}>();

function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) {
    emit("upload", file);
  }
  input.value = "";
}
</script>

<template>
  <aside class="sidebar">
    <div>
      <p class="eyebrow">Diagnostic Case</p>
      <h1>半导体设备性能诊断</h1>
    </div>

    <label class="field">
      <span>案例名称</span>
      <input :value="caseTitle" @input="emit('update:caseTitle', ($event.target as HTMLInputElement).value)" />
    </label>

    <button :disabled="loading" @click="emit('create')">新建案例</button>

    <label class="upload">
      <span>{{ uploadLoading ? "上传中..." : "上传性能 CSV" }}</span>
      <input type="file" accept=".csv,text/csv" :disabled="uploadLoading" @change="handleUpload" />
    </label>

    <section v-if="hasCase" class="case-meta">
      <strong>{{ caseTitleText }}</strong>
      <span>{{ equipmentType }}</span>
      <span>{{ caseStateText }}</span>
      <button class="debug-link" @click="emit('debug')">调试 Trace</button>
    </section>
  </aside>
</template>
