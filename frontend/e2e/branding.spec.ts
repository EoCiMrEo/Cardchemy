import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { expect, test } from '@playwright/test'

import { expectNoHorizontalOverflow } from './support/a11y'
import { fixtures, installMockApi } from './support/mockApi'
import { studyCards, studySession } from './support/studyFixtures'

for (const role of ['instructor', 'student'] as const) {
  for (const width of [320, 1280]) {
    test(`${role} wordmark loads and fits account controls at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 })
      await installMockApi(page, {
        auth: role,
        resolver: (call) => {
          if (call.method === 'GET' && call.path === '/auth/me') {
            return { json: { ...fixtures.user(role), email: 'a.long.synthetic.account.address@example-university.test' } }
          }
          if (call.method === 'GET' && call.path === '/subjects') return { json: [fixtures.subject] }
          return undefined
        },
      })
      await page.goto('/dashboard')
      const header = page.getByRole('banner')
      const brand = header.getByRole('img', { name: 'Cardchemy', exact: true })
      await expect(header.getByRole('heading', { name: 'Cardchemy', exact: true })).toBeVisible()
      await expect(brand).toBeVisible()
      await expect.poll(() => brand.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth === 480 && image.naturalHeight === 166)).toBe(true)
      await expect(header.getByRole('button', { name: 'Logout', exact: true })).toBeVisible()
      await expectNoHorizontalOverflow(page)
      const brandBox = await brand.boundingBox()
      const logoutBox = await header.getByRole('button', { name: 'Logout', exact: true }).boundingBox()
      expect(brandBox).not.toBeNull()
      expect(logoutBox).not.toBeNull()
      if (!brandBox || !logoutBox) throw new Error('Expected visible brand/account controls')
      const overlaps = brandBox.x < logoutBox.x + logoutBox.width && brandBox.x + brandBox.width > logoutBox.x && brandBox.y < logoutBox.y + logoutBox.height && brandBox.y + brandBox.height > logoutBox.y
      expect(overlaps).toBe(false)
    })
  }
}

test('account branding and supplied ICO load in a fresh page', async ({ page, request }) => {
  await installMockApi(page, { auth: 'anonymous' })
  await page.goto('/login')
  await expect(page).toHaveTitle('Cardchemy')
  await expect(page.getByRole('img', { name: 'Cardchemy', exact: true })).toBeVisible()
  await expect(page.getByText('Turn documents into memory.', { exact: true })).toBeVisible()
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/favicon.ico')
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('type', 'image/x-icon')
  const icon = await request.get('/favicon.ico')
  expect(icon.ok()).toBe(true)
  expect((await icon.body()).subarray(0, 4)).toEqual(Buffer.from([0, 0, 1, 0]))
})

test('authored fixtures provide reproducible product screenshots without provider quota', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => call.method === 'GET' && call.path === '/subjects' ? { json: [fixtures.subject] } : undefined,
  })
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Your Subjects', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /Biology/ })).toBeVisible()
  if (process.env.CAPTURE_PRODUCT_SCREENSHOTS === '1') {
    await mkdir(resolve('../docs/images'), { recursive: true })
    await page.screenshot({ path: resolve('../docs/images/instructor-dashboard.png') })
  }
  await page.unrouteAll({ behavior: 'wait' })
  await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') return { json: studySession(studyCards) }
      return undefined
    },
  })
  await page.goto('/study/set-1')
  await expect(page.getByRole('button', { name: /Mitochondrion/ })).toBeVisible()
  if (process.env.CAPTURE_PRODUCT_SCREENSHOTS === '1') {
    await page.screenshot({ path: resolve('../docs/images/student-study.png') })
  }
})
