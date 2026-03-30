import type {
  AgentMessageStartResponse,
  AgentSourceRecord,
  AgentSessionResponse,
  TaskDetailResponse,
} from './types'

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function createSession(): Promise<{ session_id: string }> {
  return readJson(await fetch('/api/v1/agent/sessions', { method: 'POST' }))
}

export async function getSession(sessionId: string): Promise<AgentSessionResponse> {
  return readJson(await fetch(`/api/v1/agent/sessions/${sessionId}`))
}

export async function sendMessage(
  sessionId: string,
  content: string,
  sourceId?: string | null,
): Promise<AgentMessageStartResponse> {
  return readJson(
    await fetch(`/api/v1/agent/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, source_id: sourceId || undefined }),
    }),
  )
}

export async function registerDemoSource(
  sessionId: string,
  demoCode: string,
): Promise<AgentSourceRecord> {
  return readJson(
    await fetch(`/api/v1/agent/sessions/${sessionId}/demo-sources/${demoCode}`, {
      method: 'POST',
    }),
  )
}

export async function getTask(taskId: string): Promise<TaskDetailResponse> {
  return readJson(await fetch(`/api/v1/tasks/${taskId}`))
}

export async function getArtifactText(artifactId: string, sessionId?: string): Promise<string> {
  const path = sessionId
    ? `/api/v1/agent/sessions/${sessionId}/artifacts/${artifactId}/content`
    : `/api/v1/artifacts/${artifactId}/content`
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`Artifact request failed with status ${response.status}`)
  }
  return response.text()
}

export function getArtifactRawUrl(artifactId: string, sessionId?: string): string {
  return sessionId
    ? `/api/v1/agent/sessions/${sessionId}/artifacts/${artifactId}/raw`
    : `/api/v1/artifacts/${artifactId}/raw`
}
