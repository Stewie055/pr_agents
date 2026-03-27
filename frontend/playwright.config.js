import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  fullyParallel: false,
  retries: 0,
  reporter: 'line',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:8001',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  webServer: {
    command:
      "cd /root/projects/pr_agents && PR_AGENTS_INTENT_MODE=fake uv run python -c \"from pr_agents.bootstrap import build_api_app; import uvicorn; uvicorn.run(build_api_app(), host='127.0.0.1', port=8001)\"",
    url: 'http://127.0.0.1:8001',
    reuseExistingServer: false,
    timeout: 120000,
  },
})
