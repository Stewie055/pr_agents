<script setup lang="ts">
import type { Artifact, EvidenceItem } from "../api";

const props = defineProps<{
  diagnosis?: Artifact;
  evidence: EvidenceItem[];
}>();

function listValue(key: string): string[] {
  const value = props.diagnosis?.data?.[key];
  return Array.isArray(value) ? value.map(String) : [];
}
</script>

<template>
  <section class="diagnosis-summary">
    <div class="section-title">
      <h3>诊断概览</h3>
      <span>{{ diagnosis?.data?.risk_level || "draft" }}</span>
    </div>
    <div v-if="diagnosis" class="diagnosis-card">
      <strong>{{ diagnosis.title }}</strong>
      <p>{{ diagnosis.summary }}</p>
      <dl>
        <div>
          <dt>风险等级</dt>
          <dd>{{ diagnosis.data.risk_level || "-" }}</dd>
        </div>
        <div>
          <dt>置信度</dt>
          <dd>{{ diagnosis.data.confidence ?? "-" }}</dd>
        </div>
      </dl>
      <h4>可能原因</h4>
      <ul>
        <li v-for="item in listValue('possible_causes')" :key="item">{{ item }}</li>
      </ul>
      <h4>建议动作</h4>
      <ul>
        <li v-for="item in listValue('recommendations')" :key="item">{{ item }}</li>
      </ul>
    </div>
    <p v-else class="empty-trace">暂无诊断结论。上传数据并开始分析后会在这里汇总结果。</p>

    <div class="evidence-list">
      <h3>关键证据</h3>
      <article v-for="item in evidence" :key="item.id">
        <strong>{{ item.title }}</strong>
        <p>{{ item.summary }}</p>
      </article>
      <p v-if="!evidence.length" class="empty-trace">暂无证据。</p>
    </div>
  </section>
</template>
