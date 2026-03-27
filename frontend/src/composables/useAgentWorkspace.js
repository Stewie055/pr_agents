import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import {
  buildFlowNodes,
  buildRecommendedActions,
  createEmptyArtifactState,
  createEmptyExecutionState,
  createEmptyProcessState,
  createEmptyStatusBarState,
  formatElapsedTime,
  inferStageIdFromTool,
} from '../mocks/workspaceDemoState'

const STORAGE_KEY = 'pr_agents_vue_sessions'
const ACTIVE_SESSION_KEY = 'pr_agents_vue_active_session'

function truncate(value, size) {
  if (!value) return 'New conversation'
  return value.length > size ? `${value.slice(0, size - 1)}…` : value
}

function readStorage(key, fallback) {
  try {
    return JSON.parse(window.localStorage.getItem(key) || JSON.stringify(fallback))
  } catch {
    return fallback
  }
}

function summarizeMessages(messages) {
  const firstUser = (messages || []).find((message) => message.role === 'user')
  return firstUser ? truncate(firstUser.content, 48) : 'New conversation'
}

function deriveInsightBullets(detail) {
  const insights = detail?.result?.analysis?.insights || []
  if (insights.length) return insights
  const summary = detail?.result?.analysis?.summary
  return summary ? [summary] : []
}

export function useAgentWorkspace() {
  const sessionId = ref(null)
  const sessions = ref([])
  const sessionData = ref({ session_id: '', messages: [], tasks: [], runs: [] })
  const statusText = ref('Creating session...')
  const prompt = ref('')
  const uploadedFiles = ref([])
  const liveAssistant = ref(null)
  const liveRun = ref(null)
  const liveAssistantController = ref(null)
  const assistantChunkQueue = ref([])
  const assistantSawDelta = ref(false)
  const processState = reactive(createEmptyProcessState())
  const artifactState = reactive(createEmptyArtifactState())
  const statusBar = reactive(createEmptyStatusBarState())
  const executionState = reactive(createEmptyExecutionState())
  const promptSnapshot = reactive({
    taskIntent: '',
    phase: 'Idle',
    instructionSummary: 'Awaiting user input.',
    subGoal: 'No active run.',
  })
  const memorySnapshot = reactive({
    currentFactory: 'Line A / Demo Plant',
    currentFocus: 'Idle',
    confirmedIssues: [],
    tentativeConclusions: [],
    latestTaskSummary: {},
  })
  const toolCalls = ref([])
  const currentRunStartedAt = ref(null)

  let assistantFlushTimer = null
  let assistantCompletionMessage = null
  let assistantCompletionResolver = null
  let assistantCompletionPromise = Promise.resolve()
  let assistantReleaseAt = 0
  let elapsedTimer = null

  const projectTitle = computed(() => {
    const latestRun = sessionData.value.runs?.[0]
    if (latestRun?.metadata?.business_code) return `Diagnostic Run · ${latestRun.metadata.business_code}`
    return 'Industrial Diagnostic Workspace'
  })

  const inputQuerySummary = computed(() => {
    const latestUser = [...(sessionData.value.messages || [])].reverse().find((message) => message.role === 'user')
    return {
      title: latestUser ? 'Current Query' : 'Input Query',
      content: latestUser?.content || 'Start with a natural-language diagnostic request or one of the guided demo prompts.',
      attachments: uploadedFiles.value.map((file) => file.name),
    }
  })

  const visibleMessages = computed(() => {
    const base = (sessionData.value.messages || []).filter(
      (message) => !['plan', 'tool_call', 'tool_result'].includes(message.message_type),
    )
    if (liveAssistant.value) {
      base.push({
        message_id: '__live_assistant__',
        session_id: sessionId.value || '',
        role: 'assistant',
        message_type: 'chat',
        content: liveAssistant.value.content || '',
        metadata: { run_id: liveAssistant.value.run_id, live: true },
      })
    }
    return base
  })

  const currentRun = computed(() => {
    if (liveRun.value) return liveRun.value
    return sessionData.value.runs?.[0] || null
  })

  const workspaceState = computed(() => {
    if (executionState.overrideState) return executionState.overrideState
    const run = currentRun.value
    if (!run) {
      const hasUserInput = (sessionData.value.messages || []).some((message) => message.role === 'user')
      return hasUserInput ? 'completed' : 'empty'
    }
    if (run.status === 'failed') return 'error'
    if (run.status === 'succeeded') return 'completed'
    if (executionState.paused) return 'paused'
    return 'running'
  })

  const sessionTitle = computed(() => {
    return sessionId.value ? `${summarizeMessages(sessionData.value.messages)} · ${sessionId.value}` : 'Diagnostic Workspace'
  })

  const currentStep = computed(() => {
    const steps = currentRun.value?.steps || []
    const active = steps.find((step) => step.status === 'running') || steps.at(-1)
    return active
      ? {
        title: active.title,
        tool: active.tool_name,
        status: workspaceState.value,
        summary:
          active.observation_summary?.summary ||
          active.observation_summary?.report_summary ||
          active.error_summary?.message ||
          'Monitoring task execution.',
      }
      : {
        title: workspaceState.value === 'empty' ? 'Awaiting task' : 'Generating response',
        tool: statusBar.activeTool,
        status: workspaceState.value,
        summary: promptSnapshot.subGoal,
      }
  })

  const chatModeLabel = computed(() => sessionData.value.runs?.[0]?.intent_mode || 'llm')

  const debugPanels = computed(() => ({
    toolCalls: toolCalls.value,
    promptSnapshot,
    memorySnapshot,
    executionState,
  }))

  function renderStatusText(next) {
    statusText.value = next
  }

  function updateElapsed() {
    statusBar.elapsedTime = formatElapsedTime(currentRunStartedAt.value)
  }

  function startElapsedTimer() {
    if (elapsedTimer) window.clearInterval(elapsedTimer)
    updateElapsed()
    elapsedTimer = window.setInterval(updateElapsed, 1000)
  }

  function stopElapsedTimer() {
    if (elapsedTimer) {
      window.clearInterval(elapsedTimer)
      elapsedTimer = null
    }
  }

  function resetProcessArtifacts() {
    Object.assign(processState, createEmptyProcessState())
    Object.assign(artifactState, createEmptyArtifactState())
    Object.assign(statusBar, createEmptyStatusBarState())
    toolCalls.value = []
    promptSnapshot.taskIntent = ''
    promptSnapshot.phase = 'Idle'
    promptSnapshot.instructionSummary = 'Awaiting user input.'
    promptSnapshot.subGoal = 'No active run.'
  }

  function stopAssistantFlusher() {
    if (assistantFlushTimer !== null) {
      window.clearInterval(assistantFlushTimer)
      assistantFlushTimer = null
    }
  }

  function ensureLiveAssistant(runId) {
    if (!liveAssistant.value || liveAssistant.value.run_id !== runId) {
      liveAssistant.value = { run_id: runId, content: '' }
    }
    return liveAssistant.value
  }

  function ensureAssistantFlusher() {
    if (assistantFlushTimer !== null) return
    assistantFlushTimer = window.setInterval(() => {
      if (Date.now() < assistantReleaseAt) return
      if (assistantChunkQueue.value.length) {
        const chunk = assistantChunkQueue.value.shift()
        if (chunk && liveAssistant.value) liveAssistant.value.content += chunk
        return
      }
      if (assistantCompletionMessage !== null) {
        if (liveAssistant.value) liveAssistant.value.content = assistantCompletionMessage
        assistantCompletionMessage = null
        if (assistantCompletionResolver) {
          assistantCompletionResolver()
          assistantCompletionResolver = null
        }
      }
      if (!assistantChunkQueue.value.length && assistantCompletionMessage === null) {
        stopAssistantFlusher()
      }
    }, 100)
  }

  function queueAssistantChunk(runId, chunk) {
    ensureLiveAssistant(runId)
    assistantChunkQueue.value.push(chunk)
    ensureAssistantFlusher()
  }

  function chunkAssistantMessage(message, size = 18) {
    const chunks = []
    for (let index = 0; index < (message || '').length; index += size) {
      chunks.push(message.slice(index, index + size))
    }
    return chunks
  }

  function completeAssistant(runId, message) {
    ensureLiveAssistant(runId)
    if (!assistantSawDelta.value && message) {
      assistantChunkQueue.value.push(...chunkAssistantMessage(message))
    }
    assistantCompletionMessage = message || liveAssistant.value?.content || ''
    assistantCompletionPromise = new Promise((resolve) => {
      assistantCompletionResolver = resolve
    })
    ensureAssistantFlusher()
    return assistantCompletionPromise
  }

  function closeStream() {
    liveAssistantController.value?.abort?.()
    liveAssistantController.value = null
  }

  function upsertSessionMeta(id, title) {
    const existing = sessions.value.find((item) => item.session_id === id)
    if (existing) {
      existing.title = title || existing.title
    } else {
      sessions.value.unshift({ session_id: id, title: title || 'New conversation' })
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value))
  }

  function loadStoredSessions() {
    sessions.value = readStorage(STORAGE_KEY, [])
  }

  function saveActiveSession() {
    if (sessionId.value) window.localStorage.setItem(ACTIVE_SESSION_KEY, sessionId.value)
  }

  function appendTaskLog(message, level = 'info', timestamp = new Date().toISOString()) {
    processState.taskLogs.unshift({
      id: `log-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
      message,
      level,
      timestamp,
    })
  }

  async function hydrateTaskArtifacts(taskId) {
    if (!taskId) return
    const response = await fetch(`/api/v1/tasks/${taskId}`)
    if (!response.ok) return
    const detail = await response.json()

    artifactState.charts = detail.result?.chart
      ? [
        {
          id: detail.result.chart.chart_id,
          title: detail.result.chart.title,
          chartType: detail.result.chart.chart_type,
          artifactId: detail.result.chart.artifact.artifact_id,
        },
      ]
      : []
    artifactState.diagnosisSummary = deriveInsightBullets(detail)
    artifactState.recommendedActions = buildRecommendedActions(detail)
    artifactState.reportPreview.title = detail.result?.report?.title || 'Report Preview'
    artifactState.reportPreview.outline = detail.result?.report?.sections || []
    memorySnapshot.currentFocus = detail.task?.objective || memorySnapshot.currentFocus
    memorySnapshot.latestTaskSummary = detail.task?.result_summary || {}

    const reportArtifactId = detail.result?.report?.artifact?.artifact_id
    if (reportArtifactId) {
      const reportResponse = await fetch(`/api/v1/artifacts/${reportArtifactId}/content`)
      if (reportResponse.ok) {
        artifactState.reportPreview.content = await reportResponse.text()
      }
    }
  }

  function updateFlowStage(stageId, statusLabel) {
    processState.currentStageId = stageId
    processState.flowNodes = buildFlowNodes(processState, statusLabel)
  }

  function updateStatusBar(partial) {
    Object.assign(statusBar, partial)
  }

  function registerToolCall(payload) {
    const existing = toolCalls.value.find((item) => item.stepId === payload.data.step_id)
    if (existing) {
      Object.assign(existing, payload)
      return
    }
    toolCalls.value.unshift({
      stepId: payload.data.step_id,
      toolName: payload.data.tool_name,
      inputs: payload.data.inputs || {},
      output: {},
      status: 'running',
      startedAt: payload.timestamp,
      duration: '',
    })
  }

  function finalizeToolCall(stepId, output, status) {
    const item = toolCalls.value.find((entry) => entry.stepId === stepId)
    if (!item) return
    item.output = output
    item.status = status
    item.duration = item.startedAt ? `${Math.max(1, Math.round((Date.now() - Date.parse(item.startedAt)) / 1000))}s` : ''
  }

  async function createSession() {
    renderStatusText('Creating session...')
    const response = await fetch('/api/v1/agent/sessions', { method: 'POST' })
    const payload = await response.json()
    sessionId.value = payload.session_id
    saveActiveSession()
    upsertSessionMeta(sessionId.value, 'New conversation')
    await refreshSession()
  }

  async function refreshSession() {
    if (!sessionId.value) return
    const response = await fetch(`/api/v1/agent/sessions/${sessionId.value}`)
    const payload = await response.json()
    sessionData.value = payload
    sessionId.value = payload.session_id
    saveActiveSession()
    upsertSessionMeta(sessionId.value, summarizeMessages(payload.messages))
    const latestRun = payload.runs?.[0]
    if (!liveRun.value && latestRun) {
      processState.currentStageId = latestRun.status === 'succeeded' ? 'generate-report' : processState.currentStageId
      processState.flowNodes = buildFlowNodes(processState, workspaceState.value)
    }
    renderStatusText('Ready.')
  }

  function ensureLiveRun(runId) {
    if (!liveRun.value || liveRun.value.run_id !== runId) {
      liveRun.value = {
        run_id: runId,
        goal: '',
        status: 'running',
        summary: '',
        metadata: {},
        steps: [],
      }
    }
    return liveRun.value
  }

  function updateLiveStep(stepId, mutate) {
    if (!liveRun.value?.steps) return
    const step = liveRun.value.steps.find((item) => item.step_id === stepId)
    if (step) mutate(step)
  }

  async function sendMessage(content) {
    const trimmed = (content || '').trim()
    if (!trimmed) return
    if (!sessionId.value) await createSession()
    closeStream()
    liveRun.value = null
    liveAssistant.value = null
    assistantChunkQueue.value = []
    assistantSawDelta.value = false
    assistantCompletionMessage = null
    assistantCompletionResolver = null
    assistantCompletionPromise = Promise.resolve()
    assistantReleaseAt = 0
    stopAssistantFlusher()
    resetProcessArtifacts()
    currentRunStartedAt.value = Date.now()
    startElapsedTimer()
    executionState.overrideState = null
    executionState.modified = false
    sessionData.value.messages = [
      ...(sessionData.value.messages || []),
      { message_id: `local-${Date.now()}`, role: 'user', message_type: 'chat', content: trimmed, metadata: {} },
    ]
    promptSnapshot.taskIntent = trimmed
    promptSnapshot.subGoal = 'Preparing diagnostic run.'
    memorySnapshot.currentFocus = trimmed
    renderStatusText('Queued...')
    const response = await fetch(`/api/v1/agent/sessions/${sessionId.value}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: trimmed }),
    })
    const payload = await response.json()
    prompt.value = ''
    const controller = new AbortController()
    liveAssistantController.value = controller

    const finalize = async (label, nextStatus) => {
      if (liveRun.value) liveRun.value.status = nextStatus
      await assistantCompletionPromise
      if (liveAssistant.value?.content) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
      }
      closeStream()
      await refreshSession()
      liveRun.value = null
      liveAssistant.value = null
      stopElapsedTimer()
      renderStatusText(label)
      updateStatusBar({
        status: nextStatus === 'succeeded' ? 'Completed' : 'Error',
        runningStep: nextStatus === 'succeeded' ? 'Completed' : 'Failed',
      })
    }

    const handleEvent = async (eventName, payload) => {
      if (eventName === 'run_started') {
        liveRun.value = {
          run_id: payload.run_id,
          goal: payload.data.goal,
          status: 'running',
          summary: '',
          metadata: {},
          steps: [],
        }
        updateFlowStage('load-data', 'running')
        appendTaskLog('Loading data context', 'info', payload.timestamp)
        updateStatusBar({
          runningStep: 'Load Data',
          activeTool: 'Waiting for tool',
          status: 'Running',
          stepCount: '0 / 4',
        })
        promptSnapshot.phase = 'Context setup'
        promptSnapshot.instructionSummary = 'Interpret the request and prepare the diagnostic path.'
        promptSnapshot.subGoal = payload.data.goal
        renderStatusText('Starting run...')
        return
      }
      if (eventName === 'step_started') {
        const run = ensureLiveRun(payload.run_id)
        let step = run.steps.find((item) => item.step_id === payload.data.step_id)
        if (!step) {
          step = {
            step_id: payload.data.step_id,
            step_index: payload.data.step_index,
            title: payload.data.title,
            tool_name: payload.data.tool_name,
            status: 'running',
            inputs_summary: {},
            observation_summary: {},
            error_summary: {},
          }
          run.steps.push(step)
        } else {
          step.status = 'running'
        }
        const stageId = inferStageIdFromTool(payload.data.tool_name)
        updateFlowStage(stageId, 'running')
        appendTaskLog(`Running step: ${payload.data.title}`, 'info', payload.timestamp)
        updateStatusBar({
          runningStep: payload.data.title,
          activeTool: payload.data.tool_name,
          status: executionState.paused ? 'Paused' : 'Running',
          stepCount: `${payload.data.step_index + 1} / 4`,
        })
        promptSnapshot.phase = 'Executing tool step'
        promptSnapshot.subGoal = payload.data.title
        renderStatusText('Running step...')
        return
      }
      if (eventName === 'tool_called') {
        const run = ensureLiveRun(payload.run_id)
        let step = run.steps.find((item) => item.step_id === payload.data.step_id)
        if (!step) {
          step = {
            step_id: payload.data.step_id,
            step_index: run.steps.length,
            title: payload.data.tool_name,
            tool_name: payload.data.tool_name,
            status: 'running',
            inputs_summary: payload.data.inputs || {},
            observation_summary: {},
            error_summary: {},
          }
          run.steps.push(step)
        }
        step.status = 'running'
        step.inputs_summary = payload.data.inputs || {}
        step.observation_summary = { summary: `Calling ${payload.data.tool_name}...` }
        registerToolCall(payload)
        appendTaskLog(`Tool called: ${payload.data.tool_name}`, 'info', payload.timestamp)
        updateStatusBar({
          activeTool: payload.data.tool_name,
          status: executionState.paused ? 'Paused' : 'Running',
        })
        renderStatusText('Running tool...')
        return
      }
      if (eventName === 'tool_result') {
        updateLiveStep(payload.data.step_id, (step) => {
          step.observation_summary = {
            summary: step.observation_summary.summary || '',
            task_status: payload.data.status,
            chart_type: payload.data.chart_type,
          }
        })
        finalizeToolCall(payload.data.step_id, payload.data, payload.data.status || 'succeeded')
        if (payload.data.task_id) await hydrateTaskArtifacts(payload.data.task_id)
        updateFlowStage('identify-issues', workspaceState.value === 'error' ? 'error' : 'running')
        appendTaskLog('Analyzing metrics and identifying issues', 'info', payload.timestamp)
        memorySnapshot.confirmedIssues = artifactState.diagnosisSummary.slice(0, 2)
        renderStatusText('Tool returned.')
        return
      }
      if (eventName === 'step_completed') {
        updateLiveStep(payload.data.step_id, (step) => {
          step.status = 'succeeded'
          step.observation_summary = { summary: payload.data.summary || step.observation_summary.summary || '' }
        })
        appendTaskLog(`Completed step: ${payload.data.summary || 'done'}`, 'success', payload.timestamp)
        updateFlowStage('identify-issues', 'running')
        renderStatusText('Step completed.')
        return
      }
      if (eventName === 'step_failed') {
        updateLiveStep(payload.data.step_id, (step) => {
          step.status = 'failed'
          step.error_summary = { message: payload.data.message }
        })
        executionState.overrideState = 'error'
        appendTaskLog(`Step failed: ${payload.data.message}`, 'error', payload.timestamp)
        updateFlowStage(processState.currentStageId || 'identify-issues', 'error')
        updateStatusBar({ status: 'Error', runningStep: 'Failed' })
        renderStatusText('Step failed.')
        return
      }
      if (eventName === 'assistant_started') {
        ensureLiveAssistant(payload.run_id)
        liveAssistant.value.content = ''
        assistantChunkQueue.value = []
        assistantSawDelta.value = false
        assistantCompletionMessage = null
        assistantReleaseAt = Date.now() + 250
        updateFlowStage('generate-report', 'running')
        promptSnapshot.phase = 'Drafting final response'
        promptSnapshot.subGoal = 'Generate concise diagnostic summary for the user.'
        appendTaskLog('Generating summary and report preview', 'info', payload.timestamp)
        renderStatusText('Responding...')
        return
      }
      if (eventName === 'assistant_delta') {
        assistantSawDelta.value = true
        queueAssistantChunk(payload.run_id, payload.data.delta || '')
        renderStatusText('Responding...')
        return
      }
      if (eventName === 'assistant_completed') {
        completeAssistant(payload.run_id, payload.data.message || '')
        memorySnapshot.tentativeConclusions = [payload.data.message || 'Assistant completed the latest response.']
        renderStatusText('Reply received.')
        return
      }
      if (eventName === 'run_completed') {
        updateFlowStage('generate-report', 'completed')
        appendTaskLog('Run completed successfully', 'success', payload.timestamp)
        await finalize('Completed.', 'succeeded')
        return
      }
      if (eventName === 'run_failed') {
        executionState.overrideState = 'error'
        appendTaskLog(payload.data.message || 'Run failed', 'error', payload.timestamp)
        await finalize('Failed.', 'failed')
        return
      }
      if (eventName === 'keepalive') {
        if (liveAssistantController.value === controller) {
          closeStream()
          renderStatusText('Completed.')
        }
      }
    }

    ;(async () => {
      try {
        const streamResponse = await fetch(payload.stream_url, {
          headers: { Accept: 'text/event-stream' },
          signal: controller.signal,
        })
        const reader = streamResponse.body?.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (reader) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const frames = buffer.split('\n\n')
          buffer = frames.pop() || ''
          for (const frame of frames) {
            const lines = frame.split('\n')
            let eventName = ''
            let eventData = ''
            for (const line of lines) {
              if (line.startsWith('event: ')) eventName = line.slice(7)
              if (line.startsWith('data: ')) eventData += line.slice(6)
            }
            if (!eventName || !eventData) continue
            await handleEvent(eventName, JSON.parse(eventData))
          }
        }
      } catch (error) {
        if (error?.name === 'AbortError') return
        closeStream()
        await refreshSession()
        renderStatusText('Stream disconnected.')
      }
    })()
  }

  function onFilesSelected(files) {
    uploadedFiles.value = [...files]
  }

  function startFileDemo() {
    sendMessage('Please use A_DEMO file data to generate a scientific plot and report.')
  }

  function startDbDemo() {
    sendMessage('Please use database data to generate a scientific plot and report for A_DEMO.')
  }

  function showLatestReport() {
    sendMessage('Show me the report again.')
  }

  function summarizeReport() {
    sendMessage('Please summarize the report key points.')
  }

  function pauseRun() {
    executionState.paused = true
    executionState.overrideState = 'paused'
    updateStatusBar({ status: 'Paused' })
    renderStatusText('Paused (mock control).')
  }

  function resumeRun() {
    executionState.paused = false
    executionState.overrideState = null
    updateStatusBar({ status: currentRun.value?.status === 'succeeded' ? 'Completed' : 'Running' })
    renderStatusText('Resumed (mock control).')
  }

  function rerunStep() {
    const latestUser = [...(sessionData.value.messages || [])].reverse().find((message) => message.role === 'user')
    if (latestUser) sendMessage(latestUser.content)
  }

  function modifyState() {
    executionState.modified = !executionState.modified
    executionState.overrideState = executionState.modified ? 'error' : null
    memorySnapshot.tentativeConclusions = executionState.modified
      ? ['Operator adjusted the state manually. Review the previous anomaly verdict before finalizing the report.']
      : []
    updateStatusBar({ status: executionState.modified ? 'Warning' : 'Running' })
    renderStatusText(executionState.modified ? 'State modified (mock).' : 'State reset.')
  }

  onMounted(async () => {
    loadStoredSessions()
    const active = window.localStorage.getItem(ACTIVE_SESSION_KEY)
    if (active && sessions.value.some((item) => item.session_id === active)) {
      sessionId.value = active
      await refreshSession()
    } else {
      await createSession()
    }
  })

  onUnmounted(() => {
    closeStream()
    stopAssistantFlusher()
    stopElapsedTimer()
  })

  return {
    sessionId,
    sessions,
    sessionData,
    statusText,
    prompt,
    uploadedFiles,
    projectTitle,
    sessionTitle,
    inputQuerySummary,
    visibleMessages,
    workspaceState,
    processState,
    artifactState,
    currentStep,
    liveRun,
    debugPanels,
    statusBar,
    chatModeLabel,
    createSession,
    refreshSession,
    sendMessage,
    onFilesSelected,
    startFileDemo,
    startDbDemo,
    showLatestReport,
    summarizeReport,
    pauseRun,
    resumeRun,
    rerunStep,
    modifyState,
    saveActiveSession,
  }
}
