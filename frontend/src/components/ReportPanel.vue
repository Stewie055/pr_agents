<script setup lang="ts">
import { artifactFileUrl, type Artifact } from "../api";

defineProps<{
  report?: Artifact;
  sections: Array<{ heading: string; body: string }>;
  loading: boolean;
  disabled: boolean;
}>();

const emit = defineEmits<{ generate: [] }>();
</script>

<template>
  <section class="report">
    <div class="section-title">
      <h3>PPT 报告</h3>
      <button :disabled="loading || disabled" type="button" @click="emit('generate')">
        {{ loading ? "生成中..." : report ? "重新生成" : "生成 PPT" }}
      </button>
    </div>
    <div v-if="report" class="report-download">
      <strong>{{ report.title }}</strong>
      <p>{{ report.summary }}</p>
      <a :href="artifactFileUrl(report.id)" download>下载 PPTX</a>
    </div>
    <article v-for="section in sections" :key="section.heading">
      <strong>{{ section.heading }}</strong>
      <p>{{ section.body }}</p>
    </article>
    <p v-if="!report" class="empty-trace">暂无 PPT 报告。完成分析后可生成工程师审阅版报告。</p>
  </section>
</template>
