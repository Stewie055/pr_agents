import type {
  AgentMessageStartResponse,
  AgentSourceRecord,
  AgentSessionResponse,
  TaskDetailResponse,
  UploadedFileSourceResponse,
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
  modelMode?: 'fake' | 'llm',
): Promise<AgentMessageStartResponse> {
  return readJson(
    await fetch(`/api/v1/agent/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, source_id: sourceId || undefined, model_mode: modelMode }),
    }),
  )
}

export async function uploadCsvSource(
  sessionId: string,
  file: File,
  businessCode = 'file_analysis',
): Promise<UploadedFileSourceResponse> {
  const body = new FormData()
  body.append('file', file)
  body.append('business_code', businessCode)
  return readJson(
    await fetch(`/api/v1/agent/sessions/${sessionId}/sources/csv-upload`, {
      method: 'POST',
      body,
    }),
  )
}

export async function registerSqlSource(
  sessionId: string,
  queryName: string,
  sql: string,
  businessCode = 'db_analysis',
): Promise<AgentSourceRecord> {
  return readJson(
    await fetch(`/api/v1/agent/sessions/${sessionId}/sources/database`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query_name: queryName,
        sql,
        business_code: businessCode,
        source_profile: { simulated: true },
      }),
    }),
  )
}

export async function cancelTask(taskId: string): Promise<{ task_id: string; status: string; cancelled: boolean; message: string }> {
  return readJson(await fetch(`/api/v1/tasks/${taskId}/cancel`, { method: 'POST' }))
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
