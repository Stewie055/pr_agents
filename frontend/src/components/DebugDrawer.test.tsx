import { expect, test, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DebugDrawer } from './DebugDrawer'

test('toggles debug drawer visibility and renders snapshots', async () => {
  const user = userEvent.setup()
  const onToggle = vi.fn()

  render(
    <DebugDrawer
      open={true}
      onToggle={onToggle}
      promptSnapshot={{ user_goal: 'Run demo' }}
      memorySnapshot={{ latest_report_summary: 'Summary' }}
      runMetadata={{ model_mode_used: 'fake' }}
      toolCalls={[{ tool_name: 'run_file_analysis_workflow' }]}
    />,
  )

  expect(screen.getByTestId('debug-drawer')).toHaveClass('open')
  expect(screen.getByText('Prompt Snapshot')).toBeInTheDocument()
  expect(screen.getByText(/Run demo/)).toBeInTheDocument()
  expect(screen.getByText('Run Metadata')).toBeInTheDocument()

  await user.click(screen.getByText('Close'))
  expect(onToggle).toHaveBeenCalledTimes(1)
})
