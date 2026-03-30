import { afterEach, expect, test, vi } from 'vitest'
import { getArtifactRawUrl, registerDemoSource, sendMessage } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('builds global raw artifact url by default', () => {
  expect(getArtifactRawUrl('chart-123')).toBe('/api/v1/artifacts/chart-123/raw')
})

test('builds session raw artifact url when session id is provided', () => {
  expect(getArtifactRawUrl('chart-123', 'session-1')).toBe(
    '/api/v1/agent/sessions/session-1/artifacts/chart-123/raw',
  )
})

test('sends source_id when starting an agent run', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ session_id: 'session-1', run_id: 'run-1', message_id: 'msg-1', stream_url: '/stream' }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await sendMessage('session-1', 'Run file analysis', 'src-1')

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/agent/sessions/session-1/messages',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ content: 'Run file analysis', source_id: 'src-1' }),
    }),
  )
})

test('registers demo source through helper endpoint', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ source_id: 'src-1', session_id: 'session-1', source_type: 'file', name: 'demo.csv', payload: {}, metadata: {}, created_at: '' }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await registerDemoSource('session-1', 'a_demo_file')

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/agent/sessions/session-1/demo-sources/a_demo_file',
    { method: 'POST' },
  )
})
