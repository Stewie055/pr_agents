import { useEffect, useMemo, useRef, useState } from 'react'
import {
  createSession,
  getArtifactRawUrl,
  getArtifactText,
  getSession,
  getTask,
  registerDemoSource,
  sendMessage,
} from '../api'
import type {
  AgentRun,
  AgentSessionResponse,
  AgentStreamEnvelope,
  LiveAssistant,
  QuickPrompt,
  TaskDetailResponse,
} from '../types'

const SESSION_KEY = 'pr_agents.session_id'

const QUICK_PROMPTS: QuickPrompt[] = [
  {
    label: 'Run File Demo',
    prompt: 'Please use A_DEMO file data to generate a scientific plot and report.',
    demoCode: 'a_demo_file',
  },
  {
    label: 'Run DB Demo',
    prompt: 'Please use database data to generate a scientific plot and report for A_DEMO.',
    demoCode: 'a_demo_db',
  },
  {
    label: 'Show Latest Report',
    prompt: 'Show me the report again.',
  },
  {
    label: 'Summarize Report',
    prompt: 'Please summarize the report key points.',
  },
]

function getLatestTaskId(run: AgentRun | null): string | null {
  if (!run) {
    return null
  }
  const stepsWithTask = [...run.steps].reverse().find((step) => Boolean(step.task_id))
  return stepsWithTask?.task_id || null
}

export function useAgentWorkspace() {
  const [session, setSession] = useState<AgentSessionResponse | null>(null)
  const [prompt, setPrompt] = useState('')
  const [statusText, setStatusText] = useState('Ready.')
  const [busy, setBusy] = useState(false)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [liveRun, setLiveRun] = useState<AgentRun | null>(null)
  const [liveAssistant, setLiveAssistant] = useState<LiveAssistant | null>(null)
  const [taskDetails, setTaskDetails] = useState<Record<string, TaskDetailResponse>>({})
  const [reportPreview, setReportPreview] = useState<Record<string, string>>({})
  const [debugOpen, setDebugOpen] = useState(false)
  const streamRef = useRef<EventSource | null>(null)

  async function refreshSession(sessionId: string) {
    const data = await getSession(sessionId)
    setSession(data)
    return data
  }

  async function ensureSession(): Promise<string> {
    const stored = window.localStorage.getItem(SESSION_KEY)
    if (stored) {
      try {
        await refreshSession(stored)
        return stored
      } catch {
        window.localStorage.removeItem(SESSION_KEY)
      }
    }
    const created = await createSession()
    window.localStorage.setItem(SESSION_KEY, created.session_id)
    await refreshSession(created.session_id)
    return created.session_id
  }

  useEffect(() => {
    void ensureSession()
    return () => {
      streamRef.current?.close()
    }
  }, [])

  async function fetchTaskArtifacts(taskId: string, sessionId: string) {
    const detail = await getTask(taskId)
    setTaskDetails((current) => ({ ...current, [taskId]: detail }))
    const reportArtifactId = detail.result?.report?.artifact?.artifact_id
    if (reportArtifactId) {
      try {
        const preview = await getArtifactText(reportArtifactId, sessionId)
        setReportPreview((current) => ({ ...current, [taskId]: preview }))
      } catch {
        // Ignore preview fetch failures and keep the structured report summary.
      }
    }
  }

  function closeStream() {
    streamRef.current?.close()
    streamRef.current = null
  }

  async function handleSend(content: string, sourceIdOverride?: string | null) {
    const trimmed = content.trim()
    if (!trimmed || busy) {
      return
    }
    const sessionId = session?.session_id || (await ensureSession())
    const latestSourceId =
      sourceIdOverride ?? session?.sources[session.sources.length - 1]?.source_id ?? null
    setBusy(true)
    setStatusText('Submitting prompt...')
    setPrompt('')
    setLiveAssistant(null)
    setLiveRun(null)
    closeStream()

    try {
      const start = await sendMessage(sessionId, trimmed, latestSourceId)
      setActiveRunId(start.run_id)

      const stream = new EventSource(start.stream_url)
      streamRef.current = stream

      stream.addEventListener('run_started', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        setLiveRun({
          run_id: payload.run_id,
          session_id: payload.session_id,
          goal: String(payload.data.goal || ''),
          status: 'running',
          summary: 'Run started.',
          intent_mode: String(payload.data.intent_mode || 'fake'),
          metadata: {
            prompt_snapshot: payload.data.debug?.prompt_snapshot || {},
            memory_snapshot: payload.data.debug?.memory_snapshot || {},
            context_summary: payload.data.debug?.context_summary || {},
            source_id: payload.data.source_id || latestSourceId,
            model_mode_used: payload.data.intent_mode || 'fake',
            used_fallback: false,
          },
          steps: [],
          created_at: payload.timestamp,
          updated_at: payload.timestamp,
        })
        setStatusText('Run started.')
      })

      stream.addEventListener('step_started', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        setLiveRun((current) => {
          if (!current) return current
          return {
            ...current,
            steps: [
              ...current.steps,
              {
                step_id: String(payload.data.step_id),
                run_id: payload.run_id,
                step_index: Number(payload.data.step_index || current.steps.length),
                title: String(payload.data.title || payload.data.tool_name || 'Step'),
                tool_name: String(payload.data.tool_name || 'tool'),
                status: 'running',
                inputs_summary: {},
                observation_summary: {},
                error_summary: {},
                artifact_ids: [],
                created_at: payload.timestamp,
                updated_at: payload.timestamp,
              },
            ],
          }
        })
        setStatusText('Running tool...')
      })

      stream.addEventListener('tool_called', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        setLiveRun((current) => {
          if (!current) return current
          return {
            ...current,
            steps: current.steps.map((step) =>
              step.step_id === payload.data.step_id
                ? {
                    ...step,
                    inputs_summary: payload.data.inputs || {},
                    updated_at: payload.timestamp,
                  }
                : step,
            ),
          }
        })
      })

      stream.addEventListener('tool_result', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        const taskId = payload.data.task_id as string | undefined
        setLiveRun((current) => {
          if (!current) return current
          return {
            ...current,
            steps: current.steps.map((step) =>
              step.step_id === payload.data.step_id
                ? {
                    ...step,
                    observation_summary: payload.data,
                    task_id: taskId || step.task_id,
                    updated_at: payload.timestamp,
                  }
                : step,
            ),
          }
        })
        if (taskId) {
          void fetchTaskArtifacts(taskId, sessionId)
        }
        setStatusText('Tool returned.')
      })

      stream.addEventListener('step_completed', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        const taskId = payload.data.task_id as string | undefined
        setLiveRun((current) => {
          if (!current) return current
          return {
            ...current,
            steps: current.steps.map((step) =>
              step.step_id === payload.data.step_id
                ? {
                    ...step,
                    status: 'succeeded',
                    observation_summary: { ...step.observation_summary, ...payload.data },
                    task_id: taskId || step.task_id,
                    updated_at: payload.timestamp,
                  }
                : step,
            ),
          }
        })
        if (taskId) {
          void fetchTaskArtifacts(taskId, sessionId)
        }
        setStatusText('Step completed.')
      })

      stream.addEventListener('step_failed', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        setLiveRun((current) => {
          if (!current) return current
          return {
            ...current,
            status: 'failed',
            steps: current.steps.map((step) =>
              step.step_id === payload.data.step_id
                ? {
                    ...step,
                    status: 'failed',
                    error_summary: payload.data,
                    updated_at: payload.timestamp,
                  }
                : step,
            ),
          }
        })
        setStatusText('Step failed.')
      })

      stream.addEventListener('model_fallback', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        setLiveRun((current) => {
          if (!current) return current
          return {
            ...current,
            metadata: {
              ...current.metadata,
              model_mode_used: payload.data.active_mode || 'fake',
              used_fallback: true,
              fallback_reason: payload.data.reason || 'model_failure',
            },
          }
        })
        setStatusText('Primary model failed. Falling back to fake mode...')
      })

      stream.addEventListener('assistant_started', () => {
        setLiveAssistant({ runId: start.run_id, content: '' })
        setStatusText('Streaming response...')
      })

      stream.addEventListener('assistant_delta', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        setLiveAssistant((current) => ({
          runId: payload.run_id,
          content: `${current?.content || ''}${String(payload.data.delta || '')}`,
        }))
        setStatusText('Streaming response...')
      })

      stream.addEventListener('assistant_completed', (event) => {
        const payload = JSON.parse(event.data) as AgentStreamEnvelope
        setLiveAssistant({ runId: payload.run_id, content: String(payload.data.message || '') })
        setStatusText('Reply received.')
      })

      async function finalize(status: string) {
        setStatusText(status)
        setBusy(false)
        closeStream()
        const refreshed = await refreshSession(sessionId)
        const finalRun = refreshed.runs.find((item) => item.run_id === start.run_id) || null
        setLiveRun(null)
        setLiveAssistant(null)
        const latestTaskId = getLatestTaskId(finalRun)
        if (latestTaskId) {
          await fetchTaskArtifacts(latestTaskId, sessionId)
        }
      }

      stream.addEventListener('run_completed', () => {
        void finalize('Completed.')
      })

      stream.addEventListener('run_failed', () => {
        void finalize('Failed.')
      })

      stream.onerror = () => {
        void finalize('Stream disconnected.')
      }
    } catch (error) {
      setBusy(false)
      setStatusText(error instanceof Error ? error.message : 'Failed to start run.')
      setPrompt(trimmed)
      closeStream()
    }
  }

  async function handleQuickPrompt(item: QuickPrompt) {
    const nextPrompt = item.prompt
    setPrompt(nextPrompt)
    if (!item.demoCode || busy) {
      return
    }
    const sessionId = session?.session_id || (await ensureSession())
    setBusy(true)
    setStatusText('Preparing demo source...')
    try {
      await registerDemoSource(sessionId, item.demoCode)
      const refreshed = await refreshSession(sessionId)
      const latestSource = refreshed.sources[refreshed.sources.length - 1] || null
      setBusy(false)
      await handleSend(nextPrompt, latestSource?.source_id || null)
    } catch (error) {
      setBusy(false)
      setStatusText(error instanceof Error ? error.message : 'Failed to prepare demo source.')
    }
  }

  const activeRun = useMemo(() => {
    if (liveRun) {
      return liveRun
    }
    if (!session) {
      return null
    }
    return session.runs.find((run) => run.run_id === activeRunId) || session.runs[session.runs.length - 1] || null
  }, [activeRunId, liveRun, session])

  const currentTaskId = getLatestTaskId(activeRun)
  const currentTaskDetail = currentTaskId ? taskDetails[currentTaskId] || null : null
  const currentChartId = currentTaskDetail?.result?.chart?.artifact?.artifact_id || null
  const currentReportPreview =
    (currentTaskId && reportPreview[currentTaskId]) || currentTaskDetail?.result?.report?.summary || ''
  const toolSteps = activeRun?.steps || []
  const messages = session?.messages || []

  useEffect(() => {
    if (currentTaskId && session?.session_id && !taskDetails[currentTaskId]) {
      void fetchTaskArtifacts(currentTaskId, session.session_id)
    }
  }, [currentTaskId, session?.session_id, taskDetails])

  return {
    busy,
    debugOpen,
    liveAssistant,
    messages,
    prompt,
    quickPrompts: QUICK_PROMPTS,
    reportPreview: currentReportPreview,
    run: activeRun,
    sessionId: session?.session_id || null,
    statusText,
    taskDetail: currentTaskDetail,
    toolSteps,
    chartUrl: currentChartId ? getArtifactRawUrl(currentChartId) : null,
    promptSnapshot: activeRun?.metadata?.prompt_snapshot || {},
    memorySnapshot: activeRun?.metadata?.memory_snapshot || {},
    runMetadata: activeRun?.metadata || {},
    onPromptChange: setPrompt,
    onQuickPrompt: (item: QuickPrompt) => void handleQuickPrompt(item),
    onSend: () => void handleSend(prompt),
    toggleDebug: () => setDebugOpen((current) => !current),
  }
}
