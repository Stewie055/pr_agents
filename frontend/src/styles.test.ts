import { expect, test } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

test('desktop layout uses independent chat and workbench scrolling', () => {
  const css = readFileSync(resolve(__dirname, 'styles.css'), 'utf-8')

  expect(css).toContain('body {\n  margin: 0;')
  expect(css).toContain('overflow: hidden;')
  expect(css).toContain('.chat-panel {')
  expect(css).toContain('overflow-y: auto;')
  expect(css).toContain('.workbench {')
  expect(css).toContain('height: 100vh;')
})

test('mobile layout restores natural page scrolling', () => {
  const css = readFileSync(resolve(__dirname, 'styles.css'), 'utf-8')

  expect(css).toContain('@media (max-width: 1180px)')
  expect(css).toContain('@media (max-width: 760px)')
  expect(css).toContain('body {\n    overflow: auto;')
  expect(css).toContain('.chat-panel {')
  expect(css).toContain('overflow: visible;')
  expect(css).toContain('.workbench {')
})
