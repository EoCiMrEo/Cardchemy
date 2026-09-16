import { defineConfig, devices } from '@playwright/test'

if (process.env.RUN_JOURNEY_TESTS !== '1' || !process.env.JOURNEY_APP_ORIGIN || !process.env.JOURNEY_OUTPUT_DIR) {
  throw new Error('Use scripts/test_journey.py to create the disposable journey runtime')
}

export default defineConfig({
  testDir: './journey',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 90_000,
  reporter: 'list',
  outputDir: process.env.JOURNEY_OUTPUT_DIR,
  use: {
    baseURL: process.env.JOURNEY_APP_ORIGIN,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
