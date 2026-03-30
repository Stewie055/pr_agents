import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import App from './App'

vi.mock('./hooks/useAgentWorkspace', () => ({
  useAgentWorkspace: () => ({
    busy: false,
    debugOpen: false,
    liveAssistant: null,
    messages: [],
    prompt: '',
    quickPrompts: [],
    reportPreview: '',
    run: null,
    sessionId: 'session-1',
    statusText: 'Ready.',
    taskDetail: null,
    toolSteps: [],
    chartUrl: null,
    promptSnapshot: {},
    memorySnapshot: {},
    runMetadata: {},
    onPromptChange: vi.fn(),
    onQuickPrompt: vi.fn(),
    onSend: vi.fn(),
    toggleDebug: vi.fn(),
  }),
}))

test('renders app shell with chat, workbench, and debug drawer', () => {
  render(<App />)

  expect(screen.getByTestId('app-shell')).toBeInTheDocument()
  expect(screen.getByText('Conversation')).toBeInTheDocument()
  expect(screen.getByText('Current Run Output')).toBeInTheDocument()
  expect(screen.getByTestId('debug-drawer')).toBeInTheDocument()
})
