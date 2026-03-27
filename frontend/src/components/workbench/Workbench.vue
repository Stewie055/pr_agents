<script setup>
import ChartArtifactCard from './ChartArtifactCard.vue'
import CurrentStepCard from './CurrentStepCard.vue'
import DiagnosisSummaryCard from './DiagnosisSummaryCard.vue'
import FlowGraphCard from './FlowGraphCard.vue'
import RecommendedActionsCard from './RecommendedActionsCard.vue'
import ReportPreviewCard from './ReportPreviewCard.vue'
import TaskLogCard from './TaskLogCard.vue'

defineProps({
  workspaceState: { type: String, required: true },
  processState: { type: Object, required: true },
  currentStep: { type: Object, required: true },
  artifactState: { type: Object, required: true },
  liveRun: { type: Object, default: null },
})
</script>

<template>
  <div class="workbench" data-testid="workbench">
    <header class="workbench-header">
      <div>
        <div class="eyebrow">Workbench</div>
        <h2>Diagnostic Flow & Artifacts</h2>
        <p>Track the execution path and inspect structured outputs as the agent progresses.</p>
      </div>
      <span class="workspace-state-pill" :data-state="workspaceState" data-testid="workspace-state">{{ workspaceState }}</span>
    </header>

    <div v-if="workspaceState === 'empty'" class="empty-card workbench-empty" data-testid="workbench-empty">
      <h3>Start a diagnostic task</h3>
      <p>Use the chat panel to ask for file analysis, database analysis, report review, or follow-up diagnosis work.</p>
    </div>

    <div v-else class="workbench-grid">
      <section class="process-column">
        <FlowGraphCard :nodes="processState.flowNodes" />
        <CurrentStepCard :step="currentStep" />
        <TaskLogCard :logs="processState.taskLogs" />

        <details v-if="liveRun?.steps?.length" class="workbench-card" open data-testid="live-run">
          <summary>
            <span>Task in progress</span>
            <span>{{ liveRun.status }}</span>
          </summary>
          <div class="task-log-list">
            <div v-for="step in liveRun.steps" :key="step.step_id" class="task-log-item" :data-level="step.status">
              <span class="task-log-time">step {{ step.step_index + 1 }}</span>
              <span class="task-log-message">{{ step.title }} · {{ step.status }}</span>
            </div>
          </div>
        </details>
      </section>

      <section class="artifact-column">
        <ChartArtifactCard :charts="artifactState.charts" />
        <DiagnosisSummaryCard :items="artifactState.diagnosisSummary" />
        <RecommendedActionsCard :actions="artifactState.recommendedActions" />
        <ReportPreviewCard :report="artifactState.reportPreview" />
      </section>
    </div>
  </div>
</template>
