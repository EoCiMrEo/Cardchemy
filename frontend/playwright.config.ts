import { defineConfig, devices } from '@playwright/test'

import { API_ORIGIN, APP_ORIGIN } from './e2e/support/constants'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['line'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: APP_ORIGIN,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: process.env.PLAYWRIGHT_MANAGED_SERVER === '1'
    ? undefined
    : {
        command: 'node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4175 --strictPort',
        url: APP_ORIGIN,
        reuseExistingServer: false,
        env: {
          VITE_API_URL: API_ORIGIN,
        },
      },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
