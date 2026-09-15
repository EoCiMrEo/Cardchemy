import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'

test.describe('role-aware routing', () => {
  test('redirects a student away from instructor set editing', async ({ page }) => {
    const api = await installMockApi(page, { auth: 'student' })

    await page.goto('/sets/set-1')

    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'My Courses' })).toBeVisible()
    expect(api.count('GET', '/subjects/sets/set-1')).toBe(0)
    expect(api.count('GET', '/flashcards/sets/set-1/cards')).toBe(0)
  })

  test('redirects an instructor away from student study mode', async ({ page }) => {
    const api = await installMockApi(page, { auth: 'instructor' })

    await page.goto('/study/set-1')

    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'Your Subjects' })).toBeVisible()
    expect(api.count('GET', '/study/sets/set-1/session')).toBe(0)
  })

  test('redirects an anonymous protected deep link to sign in', async ({ page }) => {
    await installMockApi(page, { auth: 'anonymous' })

    await page.goto('/sets/set-1')

    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible()
  })
})

test.describe('access-token refresh', () => {
  test('shares one refresh across simultaneous 401 responses and retries both once', async ({ page }) => {
    const attempts = new Map<string, number>()
    const api = await installMockApi(page, {
      auth: 'instructor',
      resolver: async (call, callNumber) => {
        if (call.method === 'POST' && call.path === '/auth/refresh' && callNumber === 2) {
          return {
            delayMs: 100,
            json: {
              access_token: 'refreshed-access-token',
              token_type: 'bearer',
              expires_in: 900,
            },
          }
        }
        if (
          call.method === 'GET' &&
          ['/subjects/sets/set-1', '/flashcards/sets/set-1/cards'].includes(call.path)
        ) {
          attempts.set(call.path, (attempts.get(call.path) ?? 0) + 1)
          if (call.headers.authorization === 'Bearer boot-access-token') {
            return { status: 401, json: { detail: 'Access token expired' } }
          }
          expect(call.headers.authorization).toBe('Bearer refreshed-access-token')
          return { json: call.path.includes('/flashcards/') ? fixtures.cards : fixtures.set }
        }
        return undefined
      },
    })

    await page.goto('/sets/set-1')

    await expect(page.getByRole('heading', { name: fixtures.set.title })).toBeVisible()
    await expect.poll(() => api.count('POST', '/auth/refresh')).toBe(2)
    // React Strict Mode intentionally runs the idempotent loader twice in development.
    // Each initial request must be retried once with the one shared refreshed token.
    expect(attempts.get('/subjects/sets/set-1')).toBe(4)
    expect(attempts.get('/flashcards/sets/set-1/cards')).toBe(4)
    for (const path of ['/subjects/sets/set-1', '/flashcards/sets/set-1/cards']) {
      const authorizations = api.callsFor('GET', path).map((call) => call.headers.authorization)
      expect(authorizations.filter((value) => value === 'Bearer boot-access-token')).toHaveLength(2)
      expect(authorizations.filter((value) => value === 'Bearer refreshed-access-token')).toHaveLength(2)
    }
  })

  test('clears a failed refresh once and does not enter an interceptor loop', async ({ page }) => {
    await page.addInitScript(() => {
      ;(window as Window & { __sessionEndedCount?: number }).__sessionEndedCount = 0
      window.addEventListener('auth:session-ended', () => {
        const trackedWindow = window as Window & { __sessionEndedCount?: number }
        trackedWindow.__sessionEndedCount = (trackedWindow.__sessionEndedCount ?? 0) + 1
      })
    })

    const api = await installMockApi(page, {
      auth: 'instructor',
      resolver: (call, callNumber) => {
        if (call.method === 'POST' && call.path === '/auth/refresh' && callNumber === 2) {
          return { delayMs: 100, status: 401, json: { detail: 'Refresh session ended' } }
        }
        if (
          call.method === 'GET' &&
          ['/subjects/sets/set-1', '/flashcards/sets/set-1/cards'].includes(call.path)
        ) {
          return { status: 401, json: { detail: 'Access token expired' } }
        }
        return undefined
      },
    })

    await page.goto('/sets/set-1')

    await expect(page).toHaveURL(/\/login$/)
    await expect
      .poll(() =>
        page.evaluate(
          () => (window as Window & { __sessionEndedCount?: number }).__sessionEndedCount ?? 0,
        ),
      )
      .toBe(1)
    await page.waitForTimeout(150)
    expect(api.count('POST', '/auth/refresh')).toBe(2)
    expect(api.count('GET', '/subjects/sets/set-1')).toBe(2)
    expect(api.count('GET', '/flashcards/sets/set-1/cards')).toBe(2)
  })

  test('does not refresh again when a retried request is also unauthorized', async ({ page }) => {
    const api = await installMockApi(page, {
      auth: 'instructor',
      resolver: (call, callNumber) => {
        if (call.method === 'POST' && call.path === '/auth/refresh' && callNumber === 2) {
          return {
            json: {
              access_token: 'refreshed-access-token',
              token_type: 'bearer',
              expires_in: 900,
            },
          }
        }
        if (
          call.method === 'GET' &&
          ['/subjects/sets/set-1', '/flashcards/sets/set-1/cards'].includes(call.path)
        ) {
          return { status: 401, json: { detail: 'Still unauthorized' } }
        }
        return undefined
      },
    })

    await page.goto('/sets/set-1')

    await expect(page.getByRole('alert')).toContainText(/unable|failed|unauthorized/i)
    await page.waitForTimeout(150)
    expect(api.count('POST', '/auth/refresh')).toBe(2)
    expect(api.count('GET', '/subjects/sets/set-1')).toBe(4)
    expect(api.count('GET', '/flashcards/sets/set-1/cards')).toBe(4)
  })

  test('cancels a stale successful bootstrap refresh before explicit login', async ({ page }) => {
    await installMockApi(page, {
      auth: 'anonymous',
      resolver: (call) => {
        if (call.method === 'POST' && call.path === '/auth/refresh') {
          return {
            delayMs: 1_000,
            headers: { 'set-cookie': 'refresh_session=stale-refresh-cookie; Path=/; HttpOnly; SameSite=Lax' },
            json: {
              access_token: 'stale-access-token',
              token_type: 'bearer',
              expires_in: 900,
            },
          }
        }
        if (call.method === 'POST' && call.path === '/auth/login') {
          return {
            headers: { 'set-cookie': 'refresh_session=login-refresh-cookie; Path=/; HttpOnly; SameSite=Lax' },
            json: {
              access_token: 'login-access-token',
              token_type: 'bearer',
              expires_in: 900,
            },
          }
        }
        if (call.method === 'GET' && call.path === '/auth/me') {
          return { json: fixtures.user('instructor') }
        }
        return undefined
      },
    })

    await page.goto('/login')
    await page.getByRole('textbox', { name: 'Email' }).fill('instructor@example.com')
    await page.locator('input[type="password"]').fill('correct horse battery staple')
    await page.getByRole('button', { name: 'Sign In' }).click()

    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'Your Subjects' })).toBeVisible()
    await page.waitForTimeout(1_100)
    await expect(page).toHaveURL(/\/dashboard$/)
    const refreshCookie = (await page.context().cookies()).find(
      (cookie) => cookie.name === 'refresh_session',
    )
    expect(refreshCookie?.value).toBe('login-refresh-cookie')
  })
})
