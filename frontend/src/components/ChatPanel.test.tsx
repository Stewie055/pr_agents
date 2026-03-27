import { expect, test, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatPanel } from './ChatPanel'

test('renders messages and submits prompt from textarea', async () => {
  const user = userEvent.setup()
  const onSend = vi.fn()

  render(
    <ChatPanel
      messages={[
        {
          message_id: 'msg-1',
          session_id: 'session-1',
          role: 'assistant',
          message_type: 'chat',
          content: 'Ready for analysis.',
          metadata: {},
          created_at: '',
        },
      ]}
      liveAssistant={null}
      steps={[
        {
          step_id: 'step-1',
          run_id: 'run-1',
          step_index: 0,
          title: 'Run File Analysis',
          tool_name: 'run_file_analysis_workflow',
          status: 'running',
          inputs_summary: {},
          observation_summary: {},
          error_summary: {},
          artifact_ids: [],
          created_at: '',
          updated_at: '',
        },
      ]}
      statusText="Ready."
      prompt="Hello"
      busy={false}
      quickPrompts={[{ label: 'Run File Demo', prompt: 'demo' }]}
      onPromptChange={() => undefined}
      onSend={onSend}
      onQuickPrompt={() => undefined}
    />,
  )

  expect(screen.getByText('Ready for analysis.')).toBeInTheDocument()
  expect(screen.getAllByTestId('tool-status-pill')).toHaveLength(1)

  await user.click(screen.getByTestId('send-message'))
  expect(onSend).toHaveBeenCalledTimes(1)
})
