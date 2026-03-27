import { expect, test } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Workbench } from './Workbench'
import type { AgentRun, TaskDetailResponse } from '../types'

const run: AgentRun = {
  run_id: 'run-1',
  session_id: 'session-1',
  goal: 'Analyze demo dataset',
  status: 'running',
  summary: 'Run started.',
  intent_mode: 'fake',
  metadata: {},
  steps: [
    {
      step_id: 'step-1',
      run_id: 'run-1',
      step_index: 0,
      title: 'Run File Analysis',
      tool_name: 'run_file_analysis_workflow',
      status: 'succeeded',
      inputs_summary: {},
      observation_summary: { task_status: 'succeeded' },
      error_summary: {},
      task_id: 'task-1',
      artifact_ids: [],
      created_at: '',
      updated_at: '',
    },
  ],
  created_at: '',
  updated_at: '',
}

const taskDetail: TaskDetailResponse = {
  task: {
    task_id: 'task-1',
    session_id: 'session-1',
    task_type: 'file_analysis',
    status: 'succeeded',
    objective: 'Analyze demo dataset',
    input_summary: {},
    result_summary: {},
    error_summary: {},
    created_at: '',
    updated_at: '',
  },
  artifacts: [],
  result: {
    dataset: {
      dataset_id: 'dataset-1',
      source_type: 'file',
      source_uri: 'demo.csv',
      columns: ['a', 'b'],
      row_count: 2,
      artifact: null,
      metadata: {},
    },
    analysis: {
      summary: 'Analysis completed',
      metrics: [{ name: 'row_count', value: 2, unit: null }],
      insights: [],
      dataset_id: 'dataset-1',
      metadata: {},
    },
    chart: null,
    report: null,
    artifacts: [],
  },
}

test('renders workbench sections for current run output', () => {
  render(
    <Workbench
      run={run}
      taskDetail={taskDetail}
      reportPreview="Report body"
      chartUrl={null}
      busy={true}
    />,
  )

  expect(screen.getByTestId('run-overview')).toBeInTheDocument()
  expect(screen.getByTestId('step-timeline')).toBeInTheDocument()
  expect(screen.getByTestId('metrics-table')).toHaveTextContent('row_count')
  expect(screen.getByTestId('report-preview')).toHaveTextContent('Report body')
})
