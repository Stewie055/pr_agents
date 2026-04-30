import { ChatPanel } from './components/ChatPanel'
import { DebugDrawer } from './components/DebugDrawer'
import { SourcePanel } from './components/SourcePanel'
import { Workbench } from './components/Workbench'
import { useAgentWorkspace } from './hooks/useAgentWorkspace'

export default function App() {
  const workspace = useAgentWorkspace()

  return (
    <div className="app-shell" data-testid="app-shell">
      <SourcePanel
        sources={workspace.sources}
        selectedSourceId={workspace.selectedSourceId}
        modelMode={workspace.modelMode}
        busy={workspace.busy}
        canCancel={workspace.canCancel}
        onSelectSource={workspace.onSelectSource}
        onModelModeChange={workspace.onModelModeChange}
        onUploadCsv={workspace.onUploadCsv}
        onRegisterSql={workspace.onRegisterSql}
        onCancelTask={workspace.onCancelTask}
      />

      <ChatPanel
        messages={workspace.messages}
        liveAssistant={workspace.liveAssistant}
        steps={workspace.toolSteps}
        statusText={workspace.statusText}
        prompt={workspace.prompt}
        busy={workspace.busy}
        quickPrompts={workspace.quickPrompts}
        onPromptChange={workspace.onPromptChange}
        onSend={workspace.onSend}
        onQuickPrompt={workspace.onQuickPrompt}
      />

      <Workbench
        run={workspace.run}
        taskDetail={workspace.taskDetail}
        reportPreview={workspace.reportPreview}
        chartUrl={workspace.chartUrl}
        busy={workspace.busy}
      />

      <DebugDrawer
        open={workspace.debugOpen}
        onToggle={workspace.toggleDebug}
        promptSnapshot={workspace.promptSnapshot}
        memorySnapshot={workspace.memorySnapshot}
        runMetadata={workspace.runMetadata}
        toolCalls={workspace.toolSteps}
      />
    </div>
  )
}
