<script setup lang="ts">
import { computed, ref } from "vue";
import { artifactFileUrl, type Artifact } from "../api";

const props = defineProps<{ charts: Artifact[] }>();
const selectedChartIndex = ref(0);
const activeChart = computed(() => props.charts[Math.min(selectedChartIndex.value, Math.max(props.charts.length - 1, 0))]);
const fullscreen = ref(false);

function selectChart(index: number) {
  selectedChartIndex.value = index;
}
</script>

<template>
  <section class="chart-gallery">
    <div class="section-title">
      <h3>图表</h3>
      <span>{{ charts.length }} 张</span>
    </div>
    <div v-if="activeChart" class="chart-viewer">
      <img :src="artifactFileUrl(activeChart.id)" :alt="activeChart.title" />
      <div class="chart-caption">
        <div>
          <strong>{{ activeChart.title }}</strong>
          <p>{{ activeChart.summary }}</p>
        </div>
        <div class="chart-actions">
          <button type="button" @click="fullscreen = true">全屏</button>
          <a :href="artifactFileUrl(activeChart.id)" download>下载</a>
        </div>
      </div>
    </div>
    <div v-if="charts.length > 1" class="chart-strip">
      <button
        v-for="(chart, index) in charts"
        :key="chart.id"
        :class="{ active: index === selectedChartIndex }"
        type="button"
        @click="selectChart(index)"
      >
        <img :src="artifactFileUrl(chart.id)" :alt="chart.title" />
        <span>{{ chart.data.display_group || "Chart" }}</span>
        <strong>{{ chart.title }}</strong>
      </button>
    </div>
    <p v-if="!charts.length" class="empty-trace">暂无可视化图表。完成趋势分析后会在这里展示 Matplotlib 图片。</p>

    <div v-if="fullscreen && activeChart" class="lightbox" @click.self="fullscreen = false">
      <button class="lightbox-close" type="button" @click="fullscreen = false">关闭</button>
      <img :src="artifactFileUrl(activeChart.id)" :alt="activeChart.title" />
    </div>
  </section>
</template>
