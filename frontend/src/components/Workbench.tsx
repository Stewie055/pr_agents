import type { AgentRun, TaskDetailResponse } from '../types'

interface WorkbenchProps {
  run: AgentRun | null
  taskDetail: TaskDetailResponse | null
  reportPreview: string
  chartUrl: string | null
  busy: boolean
}

export function Workbench({
  run,
  taskDetail,
  reportPreview,
  chartUrl,
  busy,
}: WorkbenchProps) {
  const metrics = taskDetail?.result?.analysis?.metrics ?? []
  const dataset = taskDetail?.result?.dataset

  return (
    <section className="workbench">
      <div className="workbench-header">
        <div>
          <p className="eyebrow">Workbench</p>
          <h2>Current Run Output</h2>
        </div>
        <p className="workbench-copy">
          Notebook-style execution output for the active run. Chat stays concise; artifacts land here.
        </p>
      </div>

      {!run ? (
        <div className="empty-workbench" data-testid="workbench-empty">
          <h3>Ready for a diagnostic run</h3>
          <p>
            The first tool-backed request will create a run overview, step timeline, metrics table,
            chart preview, and report preview here.
          </p>
        </div>
      ) : (
        <div className="workbench-stack">
          <section className="workbench-card" data-testid="run-overview">
            <div className="card-head">
              <h3>Run Overview</h3>
              <span className={`status-pill ${run.status === 'failed' ? 'danger' : 'neutral'}`}>
                {busy && run.status === 'running' ? 'running' : run.status}
              </span>
            </div>
            <p>{run.goal}</p>
            <dl className="definition-grid">
              <div>
                <dt>Summary</dt>
                <dd>{run.summary || 'In progress'}</dd>
              </div>
              <div>
                <dt>Intent Mode</dt>
                <dd>{run.intent_mode}</dd>
              </div>
              <div>
                <dt>Model Used</dt>
                <dd>{String(run.metadata.model_mode_used || run.intent_mode)}</dd>
              </div>
            </dl>
            {run.metadata.used_fallback ? (
              <p className="muted-copy">
                Primary model failed and the run fell back to fake mode.
              </p>
            ) : null}
          </section>

          <section className="workbench-card" data-testid="step-timeline">
            <div className="card-head">
              <h3>Tool Timeline</h3>
              <span>{run.steps.length} step(s)</span>
            </div>
            {run.steps.length === 0 ? (
              <p className="muted-copy">No tool has been called yet.</p>
            ) : (
              <div className="step-list">
                {run.steps.map((step) => (
                  <article key={step.step_id} className="step-card">
                    <div className="card-head">
                      <strong>{step.title}</strong>
                      <span className={`status-pill ${step.status === 'failed' ? 'danger' : step.status === 'succeeded' ? 'success' : 'neutral'}`}>
                        {step.status}
                      </span>
                    </div>
                    <p className="step-meta">{step.tool_name}</p>
                    <pre>{JSON.stringify(step.observation_summary, null, 2)}</pre>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="workbench-card" data-testid="metrics-table">
            <div className="card-head">
              <h3>Metrics Table</h3>
              <span>{metrics.length} metric(s)</span>
            </div>
            {metrics.length === 0 ? (
              <p className="muted-copy">Metrics will appear after the first analysis task completes.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Value</th>
                    <th>Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((metric) => (
                    <tr key={metric.name}>
                      <td>{metric.name}</td>
                      <td>{metric.value}</td>
                      <td>{metric.unit || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {dataset ? (
              <div className="dataset-meta">
                <span>Rows: {dataset.row_count}</span>
                <span>Columns: {dataset.columns.join(', ') || 'n/a'}</span>
              </div>
            ) : null}
          </section>

          <section className="workbench-card" data-testid="chart-preview">
            <div className="card-head">
              <h3>Chart Preview</h3>
              <span>{taskDetail?.result?.chart?.chart_type || 'pending'}</span>
            </div>
            {chartUrl ? (
              <img alt="Chart preview" className="chart-preview" src={chartUrl} />
            ) : (
              <p className="muted-copy">Chart output will appear here once the tool emits an artifact.</p>
            )}
          </section>

          <section className="workbench-card" data-testid="report-preview">
            <div className="card-head">
              <h3>Report Preview</h3>
              <span>{taskDetail?.result?.report?.title || 'pending'}</span>
            </div>
            <pre className="report-preview">{reportPreview || 'Report preview will appear here.'}</pre>
          </section>
        </div>
      )}
    </section>
  )
}
