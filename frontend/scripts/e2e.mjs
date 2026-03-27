import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import process from 'node:process'
import { setTimeout as delay } from 'node:timers/promises'

import { chromium } from '@playwright/test'

const BASE_URL = 'http://127.0.0.1:8001'

async function waitForServer(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {}
    await delay(250)
  }
  throw new Error(`server did not become ready: ${url}`)
}

function startBackend() {
  return spawn(
    'bash',
    [
      '-lc',
      "cd /root/projects/pr_agents && PR_AGENTS_INTENT_MODE=fake uv run python -c \"from pr_agents.bootstrap import build_api_app; import uvicorn; uvicorn.run(build_api_app(), host='127.0.0.1', port=8001)\"",
    ],
    {
      stdio: 'inherit',
      env: process.env,
    },
  )
}

async function textGrowth(page, selector, samples = 12, intervalMs = 150) {
  let previousLength = 0
  let observedGrowth = false

  for (let index = 0; index < samples; index += 1) {
    await page.waitForTimeout(intervalMs)
    const current = await page.evaluate((currentSelector) => {
      return document.querySelector(currentSelector)?.textContent || ''
    }, selector)
    if (current.length > previousLength && previousLength > 0) {
      observedGrowth = true
      break
    }
    if (current.length > previousLength) {
      previousLength = current.length
    }
  }

  if (!observedGrowth) throw new Error(`text did not grow for selector ${selector}`)
}

async function testDirectReply(page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="workbench-empty"]', { timeout: 10000 })
  await page.waitForSelector('[data-testid="prompt"]', { timeout: 10000 })
  await page.fill('[data-testid="prompt"]', '你好')
  await page.click('[data-testid="send-message"]')

  await page.waitForSelector('[data-testid="live-assistant"]', { timeout: 10000 })
  const liveRunCount = await page.locator('[data-testid="live-run"]').count()
  assert.equal(liveRunCount, 0, 'direct reply should not create a live tool card')
  await textGrowth(page, '[data-testid="live-assistant"]')

  await page.click('[data-testid="debug-drawer-toggle"]')
  await page.click('[data-testid="control-modify"]')
  const errorState = await page.textContent('[data-testid="workspace-state"]')
  assert.match(errorState || '', /error/, 'modify state should expose the error state in the workbench')
  await page.click('[data-testid="control-resume"]')
}

async function testToolReply(page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="prompt"]', { timeout: 10000 })
  await page.fill('[data-testid="prompt"]', 'Please use A_DEMO file data to generate a scientific plot and report.')
  await page.click('[data-testid="send-message"]')

  await page.waitForSelector('[data-testid="live-run"]', { timeout: 15000 })
  const liveRunText = await page.locator('[data-testid="live-run"]').textContent()
  assert.match(liveRunText || '', /Task in progress/, 'tool path should show the live tool card first')

  await page.click('[data-testid="debug-drawer-toggle"]')
  await page.click('[data-testid="control-pause"]')
  const pausedState = await page.textContent('[data-testid="workspace-state"]')
  assert.match(pausedState || '', /paused/, 'pause control should expose paused state')
  await page.click('[data-testid="control-resume"]')

  await page.waitForSelector('[data-testid="live-assistant"]', { timeout: 15000 })
  await textGrowth(page, '[data-testid="live-assistant"]')
  await page.waitForSelector('text=Task details', { timeout: 15000 })
  const completedState = await page.textContent('[data-testid="workspace-state"]')
  assert.match(completedState || '', /completed/, 'tool path should finish in completed state')
}

async function main() {
  const backend = startBackend()
  let browser

  const cleanup = async () => {
    if (browser) await browser.close()
    backend.kill('SIGTERM')
    await delay(500)
  }

  process.on('SIGINT', async () => {
    await cleanup()
    process.exit(130)
  })

  try {
    await waitForServer(BASE_URL)
    browser = await chromium.launch({ headless: true })

    const directPage = await browser.newPage()
    await testDirectReply(directPage)
    await directPage.close()

    const toolPage = await browser.newPage()
    await testToolReply(toolPage)
    await toolPage.close()

    await cleanup()
    console.log('frontend e2e passed')
  } catch (error) {
    await cleanup()
    console.error(error)
    process.exit(1)
  }
}

await main()
