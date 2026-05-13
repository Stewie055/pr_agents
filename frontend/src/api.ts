export type DiagnosticCase = {
  id: string;
  title: string;
  equipment_type: string;
  status: string;
};

export type AgentMessage = {
  id: string;
  case_id?: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  metadata?: Record<string, unknown>;
};

export type Artifact = {
  id: string;
  kind: string;
  title: string;
  summary: string;
  data: Record<string, unknown>;
};

export type ToolTrace = {
  id: string;
  tool_name: string;
  status: string;
  result_summary: string;
};

export type EvidenceItem = {
  id: string;
  title: string;
  evidence_type?: string;
  type?: string;
  summary: string;
  data?: Record<string, unknown>;
  source_artifact_id?: string | null;
  created_at?: string;
};

export type TaskRecord = {
  id: string;
  case_id?: string | null;
  name: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled" | "interrupted";
  payload?: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error?: string | null;
  artifact_ids?: string[];
  evidence_ids?: string[];
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type AgentStep = {
  id: string;
  step_index: number;
  phase: string;
  tool_calls?: Array<Record<string, unknown>>;
  observations?: Array<Record<string, unknown>>;
  llm_metadata?: Record<string, unknown>;
  stop_reason?: string | null;
  duration_ms?: number;
};

export type AgentContinuation = {
  id: string;
  case_id: string;
  status: "waiting_task" | "running" | "completed" | "failed";
  pending_task_ids: string[];
  step_count: number;
  result_message_id?: string | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type LLMAuditEvent = {
  id: string;
  provider: string;
  model: string;
  request: Record<string, unknown>;
  response_summary?: {
    stream?: boolean;
    chunk_count?: number;
    finish_reason?: string | null;
    content?: string;
    reasoning_content?: string;
    tool_calls?: Array<{ id?: string; name?: string; arguments?: string }>;
  } | null;
  response?: Record<string, unknown> | null;
  error?: string | null;
  duration_ms: number;
  created_at: string;
};

export type CaseTrace = {
  case: DiagnosticCase;
  messages: AgentMessage[];
  agent_steps: AgentStep[];
  agent_continuations?: AgentContinuation[];
  tool_traces: ToolTrace[];
  llm_audit_events: LLMAuditEvent[];
  artifacts: Array<{ id: string; kind: string; title: string; summary: string; created_at: string }>;
  evidence: Array<{ id: string; type: string; title: string; summary: string; created_at: string }>;
};

export type CaseSnapshot = {
  case: DiagnosticCase;
  datasets: Array<{ id: string; filename: string }>;
  messages: AgentMessage[];
  artifacts: Artifact[];
  evidence?: EvidenceItem[];
  tasks?: TaskRecord[];
  tool_traces: ToolTrace[];
  agent_steps?: AgentStep[];
  agent_continuations?: AgentContinuation[];
};

export type StreamEvent =
  | { event: "started"; data: { message?: string } }
  | { event: "route"; data: { intent: string; requires_dataset?: boolean; user_goal?: string; reason?: string } }
  | { event: "tool_start"; data: { tool_name: string } }
  | {
      event: "tool_result";
      data: { tool_name: string; summary: string; error?: string; artifact_ids?: string[]; evidence_ids?: string[]; task_ids?: string[] };
    }
  | { event: "artifact_created"; data: { artifact: Artifact } }
  | { event: "message_delta"; data: { delta: string } }
  | { event: "final"; data: { message: AgentMessage; summary: string; artifacts: Artifact[]; tool_traces: ToolTrace[] } }
  | { event: "error"; data: { detail: string; status_code?: number } };

const jsonHeaders = { "Content-Type": "application/json" };

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Keep the status fallback when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function createCase(title: string): Promise<DiagnosticCase> {
  const response = await fetch("/api/cases", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ title })
  });
  return parseResponse<DiagnosticCase>(response);
}

export async function getCase(caseId: string): Promise<CaseSnapshot> {
  const response = await fetch(`/api/cases/${caseId}`);
  return parseResponse<CaseSnapshot>(response);
}

export async function listTasks(caseId?: string): Promise<TaskRecord[]> {
  const query = caseId ? `?case_id=${encodeURIComponent(caseId)}` : "";
  const response = await fetch(`/api/tasks${query}`);
  const payload = await parseResponse<{ tasks: TaskRecord[] }>(response);
  return payload.tasks;
}

export async function cancelTask(taskId: string): Promise<TaskRecord> {
  const response = await fetch(`/api/tasks/${taskId}/cancel`, { method: "POST" });
  return parseResponse<TaskRecord>(response);
}

export async function uploadDataset(caseId: string, file: File): Promise<{ id: string; filename: string }> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`/api/cases/${caseId}/files`, {
    method: "POST",
    body
  });
  return parseResponse<{ id: string; filename: string }>(response);
}

export async function sendMessage(caseId: string, content: string, datasetId?: string) {
  const response = await fetch(`/api/cases/${caseId}/messages`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ content, dataset_id: datasetId })
  });
  return parseResponse<{
    message: AgentMessage;
    artifacts: Artifact[];
    tool_traces: ToolTrace[];
  }>(response);
}

export async function streamMessage(
  caseId: string,
  content: string,
  datasetId: string | undefined,
  onEvent: (event: StreamEvent) => void
): Promise<void> {
  const response = await fetch(`/api/cases/${caseId}/messages/stream`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ content, dataset_id: datasetId })
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Streaming response is not readable");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseSseBlock(block);
      if (parsed) {
        onEvent(parsed);
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
  buffer += decoder.decode();
  const parsed = parseSseBlock(buffer.trim());
  if (parsed) {
    onEvent(parsed);
  }
}

function parseSseBlock(block: string): StreamEvent | null {
  if (!block) {
    return null;
  }
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (!dataLines.length) {
    return null;
  }
  return { event, data: JSON.parse(dataLines.join("\n")) } as StreamEvent;
}

export async function getCaseTrace(caseId: string): Promise<CaseTrace> {
  const response = await fetch(`/api/cases/${caseId}/trace`);
  return parseResponse<CaseTrace>(response);
}

export async function exportCaseTrace(caseId: string): Promise<Blob> {
  const response = await fetch(`/api/cases/${caseId}/trace/export`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.blob();
}

export function artifactFileUrl(artifactId: string): string {
  return `/api/artifacts/${artifactId}/file`;
}
