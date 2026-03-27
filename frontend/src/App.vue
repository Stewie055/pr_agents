<script setup>
import { computed, onMounted, ref } from 'vue'

const sessionId = ref(null)
const sessions = ref([])
const sessionData = ref({ session_id: '', messages: [], tasks: [], runs: [] })
const liveRun = ref(null)
const liveAssistant = ref(null)
const status = ref('Creating session...')
const prompt = ref('')
const activeStream = ref(null)
const assistantChunkQueue = ref([])
const assistantSawDelta = ref(false)

let assistantFlushTimer = null
let assistantCompletionMessage = null
let assistantCompletionResolver = null
let assistantCompletionPromise = Promise.resolve()
let assistantReleaseAt = 0

const STORAGE_KEY = 'pr_agents_vue_sessions'
const ACTIVE_SESSION_KEY = 'pr_agents_vue_active_session'

function truncate(value, size) {
  if (!value) return 'New conversation'
  return value.length > size ? `${value.slice(0, size - 1)}…` : value
}

function loadStoredSessions() {
  try {
    sessions.value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    sessions.value = []
  }
}

function saveStoredSessions() {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value))
}

function saveActiveSession() {
  if (sessionId.value) window.localStorage.setItem(ACTIVE_SESSION_KEY, sessionId.value)
}

function deriveTitle(messages) {
  const firstUser = (messages || []).find((message) => message.role === 'user')
  return firstUser ? truncate(firstUser.content, 42) : 'New conversation'
}

function upsertSessionMeta(id, title) {
  const existing = sessions.value.find((item) => item.session_id === id)
  if (existing) {
    existing.title = title || existing.title
  } else {
    sessions.value.unshift({ session_id: id, title: title || 'New conversation' })
  }
  saveStoredSessions()
}

const sessionTitle = computed(() => {
  return sessionId.value ? `${deriveTitle(sessionData.value.messages)} · ${sessionId.value}` : 'Agent Workspace'
})

const visibleMessages = computed(() => {
  const base = (sessionData.value.messages || []).filter(
    (message) => !['plan', 'tool_call', 'tool_result'].includes(message.message_type),
  )
  if (liveAssistant.value) {
    base.push({
      message_id: '__live_assistant__',
      role: 'assistant',
      message_type: 'chat',
      content: liveAssistant.value.content || '',
      metadata: { run_id: liveAssistant.value.run_id, live: true },
    })
  }
  return base
})

const runMap = computed(() => {
  const map = {}
  for (const run of sessionData.value.runs || []) map[run.run_id] = run
  if (liveRun.value?.run_id) map[liveRun.value.run_id] = liveRun.value
  return map
})

function getRunForMessage(message) {
  const runId = message?.metadata?.run_id
  return runId ? runMap.value[runId] : null
}

function formatStepObservation(step) {
  if (step?.error_summary && Object.keys(step.error_summary).length) {
    return step.error_summary.message || JSON.stringify(step.error_summary)
  }
  return (
    step?.observation_summary?.summary ||
    step?.observation_summary?.report_summary ||
    step?.observation_summary?.task_status ||
    step?.tool_name ||
    ''
  )
}

function renderStatusText(next) {
  status.value = next
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
  }, 120)
}

function queueAssistantChunk(runId, chunk) {
  ensureLiveAssistant(runId)
  assistantChunkQueue.value.push(chunk)
  ensureAssistantFlusher()
}

function chunkAssistantMessage(message, size = 16) {
  const chunks = []
  const text = message || ''
  for (let index = 0; index < text.length; index += size) {
    chunks.push(text.slice(index, index + size))
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
  activeStream.value?.abort?.()
  activeStream.value = null
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
  upsertSessionMeta(sessionId.value, deriveTitle(payload.messages))
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
  sessionData.value.messages = [
    ...(sessionData.value.messages || []),
    { message_id: `local-${Date.now()}`, role: 'user', message_type: 'chat', content: trimmed, metadata: {} },
  ]
  renderStatusText('Queued...')
  const response = await fetch(`/api/v1/agent/sessions/${sessionId.value}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: trimmed }),
  })
  const payload = await response.json()
  prompt.value = ''
  const controller = new AbortController()
  activeStream.value = controller

  const finalize = async (label, nextStatus) => {
    if (liveRun.value) liveRun.value.status = nextStatus
    await assistantCompletionPromise
    if (liveAssistant.value?.content) {
      await new Promise((resolve) => window.setTimeout(resolve, 1500))
    }
    closeStream()
    await refreshSession()
    liveRun.value = null
    liveAssistant.value = null
    renderStatusText(label)
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
      renderStatusText('Tool returned.')
      return
    }
    if (eventName === 'step_completed') {
      updateLiveStep(payload.data.step_id, (step) => {
        step.status = 'succeeded'
        step.observation_summary = { summary: payload.data.summary || step.observation_summary.summary || '' }
      })
      renderStatusText('Step completed.')
      return
    }
    if (eventName === 'step_failed') {
      updateLiveStep(payload.data.step_id, (step) => {
        step.status = 'failed'
        step.error_summary = { message: payload.data.message }
      })
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
      renderStatusText('Reply received.')
      return
    }
    if (eventName === 'run_completed') {
      await finalize('Completed.', 'succeeded')
      return
    }
    if (eventName === 'run_failed') {
      await finalize('Failed.', 'failed')
      return
    }
    if (eventName === 'keepalive') {
      if (activeStream.value === controller) {
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
</script>

<template>
  <div class="app">
    <aside class="sidebar">
      <section class="brand">
        <h1>pr_agents</h1>
        <p>Vue chat workspace for the agent demo.</p>
      </section>

      <div class="actions">
        <button class="button primary" @click="createSession">New chat</button>
        <button class="button ghost" @click="startFileDemo">Run File Demo</button>
        <button class="button ghost" @click="startDbDemo">Run DB Demo</button>
      </div>

      <section>
        <div class="panel-subtitle">Conversations</div>
        <div class="session-list">
          <button
            v-for="item in sessions"
            :key="item.session_id"
            class="session-item"
            :class="{ active: item.session_id === sessionId }"
            @click="sessionId = item.session_id; saveActiveSession(); refreshSession()"
          >
            <span class="session-name">{{ truncate(item.title || 'New conversation', 30) }}</span>
            <span class="session-meta">{{ item.session_id }}</span>
          </button>
        </div>
      </section>
    </aside>

    <main class="main">
      <header class="topbar">
        <h2>Agent Workspace</h2>
        <p>{{ sessionTitle }}</p>
        <div class="mode">Intent mode: <strong>{{ sessionData.runs?.[0]?.intent_mode || 'llm' }}</strong></div>
      </header>

      <section class="conversation">
        <div class="conversation-inner" data-testid="messages">
          <div v-if="visibleMessages.length === 0" class="empty">
            Start with <strong>Run File Demo</strong> or <strong>Run DB Demo</strong>.
          </div>

          <div
            v-for="message in visibleMessages"
            :key="message.message_id"
            class="message-row"
            :class="message.role"
          >
            <article class="message-card" :data-testid="message.metadata?.live ? 'live-assistant' : `message-${message.role}`">
              <div class="message-label">{{ message.role === 'user' ? 'You' : 'Agent' }}</div>
              <div class="message-content">{{ message.content }}</div>
            </article>

            <details
              v-if="message.role === 'assistant' && getRunForMessage(message)?.steps?.length"
              class="detail-card"
            >
              <summary>
                <span>Task details</span>
                <span>{{ getRunForMessage(message).status }} · {{ getRunForMessage(message).summary }}</span>
              </summary>
              <div class="detail-body">
                <div class="detail-line">Goal: {{ getRunForMessage(message).goal }}</div>
                <div class="detail-line">Status: {{ getRunForMessage(message).status }}</div>
                <div class="step-list">
                  <div
                    v-for="step in getRunForMessage(message).steps"
                    :key="step.step_id"
                    class="step-item"
                  >
                    <div class="step-head">
                      <span class="step-title">{{ step.title }}</span>
                      <span class="step-status">{{ step.status }}</span>
                    </div>
                    <div class="step-body">{{ formatStepObservation(step) }}</div>
                  </div>
                  <div v-if="message.metadata?.report_preview" class="step-item">
                    <div class="step-head">
                      <span class="step-title">Report preview</span>
                      <span class="step-status">artifact</span>
                    </div>
                    <div class="step-body">{{ message.metadata.report_preview }}</div>
                  </div>
                </div>
              </div>
            </details>
          </div>

          <div v-if="liveRun?.steps?.length" class="message-row tool">
            <section class="run-card live-run-card" data-testid="live-run">
              <div class="run-head">
                <span class="run-title">Task in progress</span>
                <span class="run-status">{{ liveRun.status }}</span>
              </div>
              <div class="run-summary">{{ liveRun.goal }}</div>
              <div class="step-list">
                <div v-for="step in liveRun.steps" :key="step.step_id" class="step-item">
                  <div class="step-head">
                    <span class="step-title">{{ step.title }}</span>
                    <span class="step-status">{{ step.status }}</span>
                  </div>
                  <div class="step-body">{{ formatStepObservation(step) }}</div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </section>

      <footer class="composer-shell">
        <div class="composer">
          <p class="panel-subtitle">Try a file demo, a database demo, or ask for the latest report.</p>
          <textarea v-model="prompt" data-testid="prompt" @keydown.enter.exact.prevent="sendMessage(prompt)" />
          <div class="composer-footer">
            <div>
              <div class="quick-actions">
                <button class="chip" @click="startFileDemo">Run File Demo</button>
                <button class="chip" @click="startDbDemo">Run DB Demo</button>
                <button class="chip" @click="showLatestReport">Show latest report</button>
                <button class="chip" @click="summarizeReport">Summarize report</button>
              </div>
              <div class="status" data-testid="status">{{ status }}</div>
            </div>
            <button class="send-button" :disabled="!prompt.trim()" data-testid="send-message" @click="sendMessage(prompt)">
              Send
            </button>
          </div>
        </div>
      </footer>
    </main>
  </div>
</template>
