import { expect, test } from 'vitest'
import { getArtifactRawUrl } from './api'

test('builds global raw artifact url by default', () => {
  expect(getArtifactRawUrl('chart-123')).toBe('/api/v1/artifacts/chart-123/raw')
})

test('builds session raw artifact url when session id is provided', () => {
  expect(getArtifactRawUrl('chart-123', 'session-1')).toBe(
    '/api/v1/agent/sessions/session-1/artifacts/chart-123/raw',
  )
})
