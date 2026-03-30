import type { AgentMessage, AgentPlanStep, LiveAssistant, QuickPrompt } from '../types'

interface ChatPanelProps {
  messages: AgentMessage[]
  liveAssistant: LiveAssistant | null
  steps: AgentPlanStep[]
  statusText: string
  prompt: string
  busy: boolean
  quickPrompts: QuickPrompt[]
  onPromptChange: (value: string) => void
  onSend: () => void
  onQuickPrompt: (prompt: string) => void
}

function roleLabel(role: string): string {
  if (role === 'user') return 'You'
  if (role === 'assistant') return 'Agent'
  return 'System'
}

function stepTone(status: string): string {
  if (status === 'failed') return 'danger'
  if (status === 'succeeded') return 'success'
  return 'neutral'
}

export function ChatPanel({
  messages,
  liveAssistant,
  steps,
  statusText,
  prompt,
  busy,
  quickPrompts,
  onPromptChange,
  onSend,
  onQuickPrompt,
}: ChatPanelProps) {
  return (
    <section className="chat-panel">
      <div className="panel-card project-card compact">
        <p className="eyebrow">Diagnostic Agent</p>
        <h1>Single-Agent React Workspace</h1>
        <p className="panel-copy">
          Chat leads. Workbench carries outputs. Debug stays in the drawer.
        </p>
        <div className="context-pill-row">
          <span className="context-pill">PydanticAI React loop</span>
          <span className="context-pill">Single agent</span>
          <span className="context-pill">Current run</span>
        </div>
      </div>

      <div className="panel-card conversation-card">
        <div className="section-heading">
          <h2>Conversation</h2>
          <p data-testid="status">{statusText}</p>
        </div>

        {steps.length > 0 ? (
          <div className="tool-status-strip">
            {steps.map((step) => (
              <span
                key={step.step_id}
                className={`status-pill ${stepTone(step.status)}`}
                data-testid="tool-status-pill"
              >
                {step.tool_name}
              </span>
            ))}
          </div>
        ) : null}

        <div className="message-list">
          {messages.map((message) => (
            <article key={message.message_id} className={`message-bubble ${message.role}`}>
              <p className="message-role">{roleLabel(message.role)}</p>
              <div className="message-content">{message.content}</div>
            </article>
          ))}

          {liveAssistant ? (
            <article className="message-bubble assistant live" data-testid="live-assistant">
              <p className="message-role">Agent</p>
              <div className="message-content">{liveAssistant.content || '...'}</div>
            </article>
          ) : null}
        </div>
      </div>

      <div className="panel-card composer-card">
        <label className="composer-label" htmlFor="prompt">
          Prompt
        </label>
        <div className="composer-quick-prompts">
          {quickPrompts.map((item) => (
            <button
              key={item.label}
              className="ghost-button compact"
              type="button"
              onClick={() => onQuickPrompt(item.prompt)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <textarea
          id="prompt"
          data-testid="prompt"
          className="composer-input"
          rows={4}
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSend()
            }
          }}
          placeholder="Describe the diagnostic task, ask for the latest report, or request a summary."
        />
        <div className="composer-footer">
          <p>Enter to send. Shift+Enter for newline.</p>
          <button
            className="primary-button"
            type="button"
            data-testid="send-message"
            disabled={busy || !prompt.trim()}
            onClick={onSend}
          >
            {busy ? 'Running...' : 'Send'}
          </button>
        </div>
      </div>
    </section>
  )
}
