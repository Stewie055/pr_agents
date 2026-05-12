<script setup lang="ts">
import { computed, ref } from "vue";
import type { Artifact, EvidenceItem } from "../api";
import ChartGallery from "./ChartGallery.vue";
import DiagnosisSummary from "./DiagnosisSummary.vue";
import ReportPanel from "./ReportPanel.vue";

const props = defineProps<{
  artifacts: Artifact[];
  evidence: EvidenceItem[];
  reportLoading: boolean;
  hasDataset: boolean;
}>();

const emit = defineEmits<{ generateReport: [] }>();
const activeTab = ref<"diagnosis" | "charts" | "report">("diagnosis");

const charts = computed(() =>
  props.artifacts
    .filter((item) => item.kind === "chart" && item.data?.render_type === "image")
    .sort((left, right) => Number(left.data?.order ?? 0) - Number(right.data?.order ?? 0))
);
const diagnosis = computed(() => [...props.artifacts].reverse().find((item) => item.kind === "diagnosis"));
const report = computed(() => [...props.artifacts].reverse().find((item) => item.kind === "report"));
const reportSections = computed(() => (report.value?.data?.sections as Array<{ heading: string; body: string }> | undefined) ?? []);
</script>

<template>
  <aside class="workspace-panel">
    <header>
      <p class="eyebrow">Workspace</p>
      <h2>诊断工作台</h2>
    </header>

    <nav class="workspace-tabs" aria-label="Workspace sections">
      <button :class="{ active: activeTab === 'diagnosis' }" type="button" @click="activeTab = 'diagnosis'">概览</button>
      <button :class="{ active: activeTab === 'charts' }" type="button" @click="activeTab = 'charts'">图表</button>
      <button :class="{ active: activeTab === 'report' }" type="button" @click="activeTab = 'report'">报告</button>
    </nav>

    <div class="workspace-panel-body">
      <DiagnosisSummary v-if="activeTab === 'diagnosis'" :diagnosis="diagnosis" :evidence="evidence" />
      <ChartGallery v-else-if="activeTab === 'charts'" :charts="charts" />
      <ReportPanel
        v-else
        :report="report"
        :sections="reportSections"
        :loading="reportLoading"
        :disabled="!hasDataset"
        @generate="emit('generateReport')"
      />
    </div>
  </aside>
</template>
