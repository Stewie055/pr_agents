import { expect, test } from '@playwright/test'

test('direct reply streams without a live tool card', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('prompt').fill('你好')
  await page.getByTestId('send-message').click()

  await expect(page.getByTestId('live-assistant')).toBeVisible()
  await expect(page.getByTestId('live-run')).toHaveCount(0)

  const firstSample = await page.evaluate(() => document.querySelector('[data-testid="live-assistant"]')?.textContent || '')
  await page.waitForTimeout(200)
  const secondSample = await page.evaluate(() => document.querySelector('[data-testid="live-assistant"]')?.textContent || '')

  expect((secondSample || '').length).toBeGreaterThan((firstSample || '').length)
  await expect(page.getByTestId('status')).toHaveText(/Completed|Ready|Reply received/)
})

test('tool request shows live run first and then streams assistant text', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('prompt').fill('Please use A_DEMO file data to generate a scientific plot and report.')
  await page.getByTestId('send-message').click()

  const liveRun = page.getByTestId('live-run')
  await expect(liveRun).toBeVisible()
  await expect(liveRun).toContainText('Task in progress')

  await expect(page.getByTestId('live-assistant')).toBeVisible({ timeout: 15000 })

  const firstSample = await page.evaluate(() => document.querySelector('[data-testid="live-assistant"]')?.textContent || '')
  await page.waitForTimeout(350)
  const secondSample = await page.evaluate(() => document.querySelector('[data-testid="live-assistant"]')?.textContent || '')

  expect((secondSample || '').length).toBeGreaterThan((firstSample || '').length)
  await expect(page.getByText('Task details')).toBeVisible({ timeout: 15000 })
})
