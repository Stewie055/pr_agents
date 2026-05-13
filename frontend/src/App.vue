<script setup lang="ts">
import { computed } from "vue";
import CaseSidebar from "./components/CaseSidebar.vue";
import ChatPanel from "./components/ChatPanel.vue";
import TraceDebugView from "./components/TraceDebugView.vue";
import WorkspacePanel from "./components/WorkspacePanel.vue";
import { useCaseSession } from "./composables/useCaseSession";

const session = useCaseSession();

const traceSteps = computed(() => session.trace.value?.agent_steps ?? session.snapshot.value?.agent_steps ?? []);
const llmEvents = computed(() => session.trace.value?.llm_audit_events ?? []);

async function upload(file: File) {
  await session.uploadFile(file);
}
</script>

<template>
  <TraceDebugView
    v-if="session.debugMode.value"
    :snapshot-exists="Boolean(session.snapshot.value)"
    :trace="session.trace.value"
    :fallback-steps="traceSteps"
    :llm-events="llmEvents"
    :loading="session.traceLoading.value"
    @close="session.closeTraceDebug"
    @refresh="session.loadTrace"
    @download="session.downloadTrace"
  />

  <main v-else class="workspace">
    <CaseSidebar
      v-model:case-title="session.caseTitle.value"
      :loading="session.loading.value"
      :upload-loading="session.uploadLoading.value"
      :case-title-text="session.snapshot.value?.case.title"
      :equipment-type="session.snapshot.value?.case.equipment_type"
      :case-state-text="session.caseStateText.value"
      :has-case="Boolean(session.snapshot.value)"
      @create="session.createNewCase"
      @upload="upload"
      @debug="session.openTraceDebug"
    />

    <ChatPanel
      v-model:draft-message="session.draftMessage.value"
      :messages="session.displayMessages.value"
      :loading="session.loading.value"
      :has-dataset="session.hasDataset.value"
      :case-state-text="session.caseStateText.value"
      :progress-items="session.progressItems.value"
      :error="session.error.value"
      @send="session.sendCurrentMessage()"
    />

    <WorkspacePanel
      :artifacts="session.snapshot.value?.artifacts ?? []"
      :evidence="session.snapshot.value?.evidence ?? []"
      :tasks="session.tasks.value"
      :report-loading="session.reportLoading.value"
      :has-dataset="session.hasDataset.value"
      @cancel-task="session.cancelTaskById"
      @generate-report="session.generateReport"
    />
  </main>
</template>
