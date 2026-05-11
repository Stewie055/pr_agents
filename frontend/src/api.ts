export type DiagnosticCase = {
  id: string;
  title: string;
  equipment_type: string;
  status: string;
};

export type AgentMessage = {
  id: string;
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

export type LLMAuditEvent = {
  id: string;
  provider: string;
  model: string;
  request: Record<string, unknown>;
  response?: Record<string, unknown> | null;
  error?: string | null;
  duration_ms: number;
  created_at: string;
};

export type CaseTrace = {
  case: DiagnosticCase;
  messages: AgentMessage[];
  agent_steps: AgentStep[];
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
  tool_traces: ToolTrace[];
  agent_steps?: AgentStep[];
};

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
