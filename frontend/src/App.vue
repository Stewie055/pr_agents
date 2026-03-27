<script setup>
import AppShell from './components/layout/AppShell.vue'
import ChatPanel from './components/chat/ChatPanel.vue'
import Workbench from './components/workbench/Workbench.vue'
import DebugDrawer from './components/layout/DebugDrawer.vue'
import GlobalStatusBar from './components/layout/GlobalStatusBar.vue'
import ExecutionControlsPanel from './components/debug/ExecutionControlsPanel.vue'
import InspectToolCallsPanel from './components/debug/InspectToolCallsPanel.vue'
import MemoryStatePanel from './components/debug/MemoryStatePanel.vue'
import PromptSnapshotPanel from './components/debug/PromptSnapshotPanel.vue'
import { useAgentWorkspace } from './composables/useAgentWorkspace'
import { useDebugDrawerState } from './composables/useDebugDrawerState'

const workspace = useAgentWorkspace()
const debug = useDebugDrawerState()
</script>

<template>
  <AppShell :drawer-open="debug.state.drawerOpen">
    <template #chat>
      <ChatPanel
        :project-title="workspace.projectTitle"
        :mode="workspace.chatModeLabel"
        :query-summary="workspace.inputQuerySummary"
        :messages="workspace.visibleMessages"
        :prompt="workspace.prompt"
        :status="workspace.statusText"
        :attachments="workspace.uploadedFiles"
        @update:prompt="workspace.prompt = $event"
        @send="workspace.sendMessage(workspace.prompt)"
        @files="workspace.onFilesSelected"
      />
    </template>

    <template #workbench>
      <Workbench
        :workspace-state="workspace.workspaceState"
        :process-state="workspace.processState"
        :current-step="workspace.currentStep"
        :artifact-state="workspace.artifactState"
        :live-run="workspace.liveRun"
      />
    </template>

    <template #debug>
      <DebugDrawer :open="debug.state.drawerOpen" @toggle="debug.toggleDrawer">
        <InspectToolCallsPanel
          :items="workspace.debugPanels.toolCalls"
          :open="debug.state.panels.toolCalls"
          @toggle="debug.togglePanel('toolCalls')"
        />
        <PromptSnapshotPanel
          :snapshot="workspace.debugPanels.promptSnapshot"
          :open="debug.state.panels.promptSnapshot"
          @toggle="debug.togglePanel('promptSnapshot')"
        />
        <MemoryStatePanel
          :memory="workspace.debugPanels.memorySnapshot"
          :open="debug.state.panels.memoryState"
          @toggle="debug.togglePanel('memoryState')"
        />
        <ExecutionControlsPanel
          :controls="workspace.debugPanels.executionState"
          :open="debug.state.panels.executionControls"
          @toggle="debug.togglePanel('executionControls')"
          @pause="workspace.pauseRun"
          @resume="workspace.resumeRun"
          @rerun="workspace.rerunStep"
          @modify="workspace.modifyState"
        />
      </DebugDrawer>
    </template>

    <template #status>
      <GlobalStatusBar :status="workspace.statusBar" />
    </template>
  </AppShell>
</template>
