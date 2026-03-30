export type TaskStatus = 'pending' | 'running' | 'succeeded' | 'failed'
export type AgentRunStatus = 'planned' | 'running' | 'succeeded' | 'failed'
export type AgentStepStatus = 'pending' | 'running' | 'succeeded' | 'failed'
export type MessageRole = 'user' | 'assistant' | 'tool'
export type AgentSourceType = 'file' | 'database'

export interface ArtifactRef {
  artifact_id: string
  artifact_type: 'dataset' | 'chart' | 'report'
  uri: string
  metadata: Record<string, unknown>
}

export interface DatasetRef {
  dataset_id: string
  source_type: string
  source_uri: string
  columns: string[]
  row_count: number
  artifact?: ArtifactRef | null
  metadata: Record<string, unknown>
}

export interface MetricResult {
  name: string
  value: string | number
  unit?: string | null
}

export interface AnalysisResult {
  summary: string
  metrics: MetricResult[]
  insights: string[]
  dataset_id?: string | null
  metadata: Record<string, unknown>
}

export interface ChartArtifact {
  chart_id: string
  title: string
  chart_type: string
  artifact: ArtifactRef
  config: Record<string, unknown>
}

export interface ReportArtifact {
  report_id: string
  title: string
  artifact: ArtifactRef
  sections: string[]
  summary: string
}

export interface WorkflowResult {
  dataset?: DatasetRef | null
  analysis?: AnalysisResult | null
  chart?: ChartArtifact | null
  report?: ReportArtifact | null
  artifacts: ArtifactRef[]
}

export interface TaskRecord {
  task_id: string
  session_id: string
  task_type: string
  status: TaskStatus
  objective: string
  input_summary: Record<string, unknown>
  result_summary: Record<string, unknown>
  error_summary: Record<string, unknown>
  created_at: string
  updated_at: string
  completed_at?: string | null
}

export interface ArtifactRecord {
  artifact_id: string
  task_id: string
  artifact_type: 'dataset' | 'chart' | 'report'
  uri: string
  filename: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface TaskDetailResponse {
  task: TaskRecord
  artifacts: ArtifactRecord[]
  result?: WorkflowResult | null
}

export interface AgentMessage {
  message_id: string
  session_id: string
  role: MessageRole
  message_type: string
  content: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface AgentPlanStep {
  step_id: string
  run_id: string
  step_index: number
  title: string
  tool_name: string
  status: AgentStepStatus
  inputs_summary: Record<string, unknown>
  observation_summary: Record<string, unknown>
  error_summary: Record<string, unknown>
  task_id?: string | null
  artifact_ids: string[]
  created_at: string
  updated_at: string
}

export interface AgentRun {
  run_id: string
  session_id: string
  goal: string
  status: AgentRunStatus
  summary: string
  intent_mode: string
  metadata: Record<string, unknown>
  steps: AgentPlanStep[]
  created_at: string
  updated_at: string
}

export interface AgentSourceRecord {
  source_id: string
  session_id: string
  source_type: AgentSourceType
  name: string
  payload: Record<string, unknown>
  metadata: Record<string, unknown>
  created_at: string
}

export interface AgentSessionResponse {
  session_id: string
  messages: AgentMessage[]
  tasks: TaskRecord[]
  runs: AgentRun[]
  sources: AgentSourceRecord[]
}

export interface AgentMessageStartResponse {
  session_id: string
  run_id: string
  message_id: string
  stream_url: string
}

export interface AgentStreamEnvelope {
  event: string
  session_id: string
  run_id: string
  data: Record<string, any>
  timestamp: string
}

export interface LiveAssistant {
  runId: string
  content: string
}

export interface QuickPrompt {
  label: string
  prompt: string
  demoCode?: string
}
