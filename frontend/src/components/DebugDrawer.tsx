interface DebugDrawerProps {
  open: boolean
  onToggle: () => void
  promptSnapshot: unknown
  memorySnapshot: unknown
  toolCalls: unknown
}

function pretty(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2)
}

export function DebugDrawer({
  open,
  onToggle,
  promptSnapshot,
  memorySnapshot,
  toolCalls,
}: DebugDrawerProps) {
  return (
    <>
      <button className="debug-toggle" type="button" onClick={onToggle}>
        {open ? 'Close Debug' : 'Open Debug'}
      </button>
      <aside className={`debug-drawer ${open ? 'open' : ''}`} data-testid="debug-drawer">
        <div className="debug-drawer-header">
          <div>
            <p className="eyebrow">Debug Drawer</p>
            <h2>Observability</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onToggle}>
            Close
          </button>
        </div>

        <section className="debug-card">
          <h3>Tool Calls</h3>
          <pre>{pretty(toolCalls)}</pre>
        </section>
        <section className="debug-card">
          <h3>Prompt Snapshot</h3>
          <pre>{pretty(promptSnapshot)}</pre>
        </section>
        <section className="debug-card">
          <h3>Memory Snapshot</h3>
          <pre>{pretty(memorySnapshot)}</pre>
        </section>
      </aside>
    </>
  )
}
