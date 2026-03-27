export const FLOW_STAGES = [
  { id: 'load-data', label: 'Load Data' },
  { id: 'analyze-metrics', label: 'Analyze Metrics' },
  { id: 'identify-issues', label: 'Identify Issues' },
  { id: 'generate-report', label: 'Generate Report' },
]

export function createEmptyArtifactState() {
  return {
    charts: [],
    diagnosisSummary: [],
    recommendedActions: [],
    reportPreview: {
      title: 'Report Preview',
      content: '',
      outline: [],
    },
  }
}

export function createEmptyProcessState() {
  return {
    currentStageId: null,
    taskLogs: [],
    latestTool: '',
    flowNodes: FLOW_STAGES.map((stage) => ({
      ...stage,
      status: 'not_started',
    })),
  }
}

export function createEmptyStatusBarState() {
  return {
    runningStep: 'Idle',
    activeTool: 'None',
    status: 'Idle',
    elapsedTime: '00:00',
    stepCount: '0 / 0',
  }
}

export function createEmptyExecutionState() {
  return {
    paused: false,
    overrideState: null,
    modified: false,
  }
}

export function formatElapsedTime(startedAt) {
  if (!startedAt) return '00:00'
  const elapsedMs = Date.now() - startedAt
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000))
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
}

export function classifyPriority(index) {
  if (index === 0) return 'High Priority'
  if (index === 1) return 'Medium Priority'
  return 'Low Priority'
}

export function buildRecommendedActions(detail) {
  const summary = detail?.result?.analysis?.summary || detail?.task?.objective || 'Review the latest analysis output.'
  return [
    {
      id: 'action-high',
      priority: classifyPriority(0),
      title: 'Validate anomaly source',
      description: `${summary} Confirm the highest-impact issue against line-side context.`,
    },
    {
      id: 'action-medium',
      priority: classifyPriority(1),
      title: 'Schedule follow-up inspection',
      description: 'Collect the next cycle of metrics and compare against the current diagnosis output.',
    },
    {
      id: 'action-low',
      priority: classifyPriority(2),
      title: 'Archive report draft',
      description: 'Attach the generated report preview to the shift handover or engineering review package.',
    },
  ]
}

export function inferStageIdFromTool(toolName = '') {
  if (toolName === 'load_latest_report') return 'generate-report'
  if (toolName === 'summarize_report') return 'generate-report'
  if (toolName === 'run_file_analysis_workflow' || toolName === 'run_db_analysis_workflow') return 'analyze-metrics'
  return 'load-data'
}

export function buildFlowNodes(processState, workspaceState) {
  const currentIndex = FLOW_STAGES.findIndex((stage) => stage.id === processState.currentStageId)
  return FLOW_STAGES.map((stage, index) => {
    let status = 'not_started'
    if (workspaceState === 'completed') {
      status = 'completed'
    } else if (workspaceState === 'error' && index === currentIndex) {
      status = 'failed'
    } else if (currentIndex >= 0 && index < currentIndex) {
      status = 'completed'
    } else if (currentIndex >= 0 && index === currentIndex) {
      status = workspaceState === 'paused' ? 'paused' : 'running'
    }
    return { ...stage, status }
  })
}
