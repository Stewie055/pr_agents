<script setup lang="ts">
import type { TaskRecord } from "../api";

defineProps<{ tasks: TaskRecord[] }>();
const emit = defineEmits<{ cancel: [taskId: string] }>();

function taskTitle(task: TaskRecord) {
  if (task.name.includes("build_trend_chart")) {
    return "生成图表";
  }
  if (task.name.includes("generate_report")) {
    return "生成 PPT 报告";
  }
  return task.name;
}

function statusText(status: TaskRecord["status"]) {
  const labels: Record<TaskRecord["status"], string> = {
    pending: "排队中",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
    interrupted: "已中断"
  };
  return labels[status];
}

function canCancel(task: TaskRecord) {
  return task.status === "pending";
}
</script>

<template>
  <section class="task-panel">
    <div class="section-title">
      <h3>任务</h3>
      <span>{{ tasks.length }} 个</span>
    </div>
    <ol v-if="tasks.length" class="task-list">
      <li v-for="task in tasks" :key="task.id" :class="task.status">
        <div>
          <strong>{{ taskTitle(task) }}</strong>
          <small>{{ statusText(task.status) }}</small>
        </div>
        <p v-if="task.error">{{ task.error }}</p>
        <p v-else-if="task.artifact_ids?.length">已生成 {{ task.artifact_ids.length }} 个产物</p>
        <button v-if="canCancel(task)" type="button" @click="emit('cancel', task.id)">取消</button>
      </li>
    </ol>
    <p v-else class="empty-trace">暂无后台任务。</p>
  </section>
</template>
