import type { AgentSourceRecord } from '../types'

interface SourcePanelProps {
  sources: AgentSourceRecord[]
  selectedSourceId: string | null
  modelMode: 'fake' | 'llm'
  busy: boolean
  onSelectSource: (sourceId: string) => void
  onModelModeChange: (mode: 'fake' | 'llm') => void
  onUploadCsv: (file: File) => void
  onRegisterSql: (queryName: string, sql: string) => void
  onCancelTask: () => void
  canCancel: boolean
}

function sourceLabel(source: AgentSourceRecord): string {
  return source.source_type === 'sql_query' || source.source_type === 'database' ? 'SQL' : 'CSV'
}

export function SourcePanel({
  sources,
  selectedSourceId,
  modelMode,
  busy,
  onSelectSource,
  onModelModeChange,
  onUploadCsv,
  onRegisterSql,
  onCancelTask,
  canCancel,
}: SourcePanelProps) {
  return (
    <aside className="source-panel">
      <div className="panel-card project-card">
        <p className="eyebrow">Analysis Lab</p>
        <h1>数据工作台</h1>
        <p className="panel-copy">Source first. Agent second.</p>
      </div>

      <div className="panel-card source-card">
        <div className="section-heading">
          <h2>Sources</h2>
          <span className="status-pill neutral">{sources.length} source(s)</span>
        </div>
        <label className="upload-drop">
          <span>CSV</span>
          <input
            aria-label="Upload CSV"
            type="file"
            accept=".csv,text/csv"
            disabled={busy}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0]
              if (file) onUploadCsv(file)
              event.currentTarget.value = ''
            }}
          />
        </label>

        <form
          className="sql-form"
          onSubmit={(event) => {
            event.preventDefault()
            const form = new FormData(event.currentTarget)
            const queryName = String(form.get('queryName') || 'lab_query')
            const sql = String(form.get('sql') || '').trim()
            if (sql) onRegisterSql(queryName, sql)
            event.currentTarget.reset()
          }}
        >
          <input name="queryName" placeholder="SQL source name" defaultValue="lab_query" />
          <textarea name="sql" rows={3} placeholder="select * from experiment_table" />
          <button className="ghost-button compact" type="submit" disabled={busy}>
            Add SQL
          </button>
        </form>

        <div className="source-list">
          {sources.map((source) => (
            <button
              key={source.source_id}
              className={`source-item ${selectedSourceId === source.source_id ? 'selected' : ''}`}
              type="button"
              onClick={() => onSelectSource(source.source_id)}
            >
              <span>{sourceLabel(source)}</span>
              <strong>{source.name}</strong>
              <small>{String(source.metadata.business_code || 'analysis')}</small>
            </button>
          ))}
        </div>
      </div>

      <div className="panel-card source-card">
        <div className="section-heading">
          <h2>Runtime</h2>
        </div>
        <div className="mode-toggle">
          <button
            className={modelMode === 'fake' ? 'selected' : ''}
            type="button"
            onClick={() => onModelModeChange('fake')}
          >
            Fake
          </button>
          <button
            className={modelMode === 'llm' ? 'selected' : ''}
            type="button"
            onClick={() => onModelModeChange('llm')}
          >
            LLM
          </button>
        </div>
        <button className="ghost-button danger-action" type="button" disabled={!canCancel} onClick={onCancelTask}>
          Cancel Task
        </button>
      </div>
    </aside>
  )
}
