import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'

test.describe('invitation join flow', () => {
  test('shows a stable error for a missing token without navigating to token=null', async ({ page }) => {
    const api = await installMockApi(page, { auth: 'anonymous' })

    await page.goto('/join')

    await expect(page).toHaveURL(/\/join$/)
    await expect(page.getByRole('heading', { name: 'Join Failed' })).toBeVisible()
    await expect(page.getByText('No invitation token was provided')).toBeVisible()
    expect(page.url()).not.toContain('token=null')
    expect(api.count('POST', '/subjects/invitations/accept')).toBe(0)
  })

  test('preserves an encoded token when an anonymous student is sent to registration', async ({ page }) => {
    const token = 'invite+with/slashes?and=symbols'
    const api = await installMockApi(page, { auth: 'anonymous' })

    await page.goto(`/join?token=${encodeURIComponent(token)}`)

    await expect(page).toHaveURL(/\/register\?token=/)
    expect(new URL(page.url()).searchParams.get('token')).toBe(token)
    await expect(page.getByRole('heading', { name: 'Join Course' })).toBeVisible()
    expect(api.count('POST', '/subjects/invitations/accept')).toBe(0)
  })

  test('blocks an instructor without consuming the invitation', async ({ page }) => {
    const api = await installMockApi(page, { auth: 'instructor' })

    await page.goto('/join?token=student-invitation')

    await expect(page.getByRole('heading', { name: 'Join Failed' })).toBeVisible()
    await expect(page.getByText('Only student accounts can accept course invitations')).toBeVisible()
    expect(api.count('POST', '/subjects/invitations/accept')).toBe(0)
  })

  test('sends one accept request under Strict Mode and renders success', async ({ page }) => {
    const api = await installMockApi(page, {
      auth: 'student',
      resolver: (call) => {
        if (call.method === 'POST' && call.path === '/subjects/invitations/accept') {
          return {
            delayMs: 100,
            json: { message: 'Successfully joined course', subject_name: fixtures.subject.name },
          }
        }
        return undefined
      },
    })

    await page.goto('/join?token=student-invitation')

    await expect(page.getByRole('heading', { name: 'Course Joined' })).toBeVisible()
    await expect(page.getByText(fixtures.subject.name)).toBeVisible()
    expect(api.count('POST', '/subjects/invitations/accept')).toBe(1)
    expect(api.callsFor('POST', '/subjects/invitations/accept')[0]?.body).toEqual({
      token: 'student-invitation',
    })
  })

  test('aborts an in-flight accept request when the join page is left', async ({ page }) => {
    const failedRequests: string[] = []
    page.on('requestfailed', (request) => failedRequests.push(request.url()))
    const api = await installMockApi(page, {
      auth: 'student',
      resolver: (call) => {
        if (call.method === 'POST' && call.path === '/subjects/invitations/accept') {
          return {
            delayMs: 2_000,
            json: { message: 'Successfully joined course', subject_name: fixtures.subject.name },
          }
        }
        return undefined
      },
    })

    await page.goto('/join?token=student-invitation')
    await expect.poll(() => api.count('POST', '/subjects/invitations/accept')).toBe(1)
    await page.evaluate(() => {
      window.history.pushState({}, '', '/dashboard')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })

    await expect(page.getByRole('heading', { name: 'My Courses' })).toBeVisible()
    await expect
      .poll(() => failedRequests.some((url) => url.endsWith('/api/subjects/invitations/accept')))
      .toBe(true)
  })

  test('shows a join error and retries the same invitation successfully', async ({ page }) => {
    const api = await installMockApi(page, {
      auth: 'student',
      resolver: (call, callNumber) => {
        if (call.method === 'POST' && call.path === '/subjects/invitations/accept') {
          return callNumber === 1
            ? { status: 503, json: { detail: 'Joining is temporarily unavailable' } }
            : {
                json: {
                  message: 'Successfully joined course',
                  subject_name: fixtures.subject.name,
                },
              }
        }
        return undefined
      },
    })

    await page.goto('/join?token=student-invitation')

    await expect(page.getByRole('alert')).toContainText('Joining is temporarily unavailable')
    await page.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByRole('heading', { name: 'Course Joined' })).toBeVisible()
    expect(api.count('POST', '/subjects/invitations/accept')).toBe(2)
    expect(api.callsFor('POST', '/subjects/invitations/accept').map((call) => call.body)).toEqual([
      { token: 'student-invitation' },
      { token: 'student-invitation' },
    ])
  })
})

test.describe('recoverable application errors', () => {
  test('shows an actionable dashboard load error and recovers on retry', async ({ page }) => {
    let allowSuccess = false
    const api = await installMockApi(page, {
      auth: 'instructor',
      resolver: (call) => {
        if (call.method === 'GET' && call.path === '/subjects') {
          return allowSuccess
            ? { json: [fixtures.subject] }
            : { status: 503, json: { detail: 'Subjects are temporarily unavailable' } }
        }
        return undefined
      },
    })

    await page.goto('/dashboard')

    await expect(page.getByRole('alert')).toContainText('Subjects are temporarily unavailable')
    const attemptsBeforeRetry = api.count('GET', '/subjects')
    allowSuccess = true
    await page.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByRole('heading', { name: fixtures.subject.name })).toBeVisible()
    expect(api.count('GET', '/subjects')).toBe(attemptsBeforeRetry + 1)
  })

  test('recovers when loading a flashcard set fails', async ({ page }) => {
    let allowSuccess = false
    const api = await installMockApi(page, {
      auth: 'instructor',
      resolver: (call) => {
        if (call.method === 'GET' && call.path === '/subjects/sets/set-1') {
          return allowSuccess
            ? { json: fixtures.set }
            : { status: 503, json: { detail: 'The set is temporarily unavailable' } }
        }
        if (call.method === 'GET' && call.path === '/flashcards/sets/set-1/cards') {
          return allowSuccess
            ? { json: fixtures.cards }
            : { status: 503, json: { detail: 'The cards are temporarily unavailable' } }
        }
        return undefined
      },
    })

    await page.goto('/sets/set-1')

    await expect(page.getByRole('alert')).toContainText(/temporarily unavailable|unable to load/i)
    const setAttemptsBeforeRetry = api.count('GET', '/subjects/sets/set-1')
    const cardAttemptsBeforeRetry = api.count('GET', '/flashcards/sets/set-1/cards')
    allowSuccess = true
    await page.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByRole('heading', { name: fixtures.set.title })).toBeVisible()
    expect(api.count('GET', '/subjects/sets/set-1')).toBe(setAttemptsBeforeRetry + 1)
    expect(api.count('GET', '/flashcards/sets/set-1/cards')).toBe(cardAttemptsBeforeRetry + 1)
  })

  test('renders the wildcard not-found route', async ({ page }) => {
    await installMockApi(page, { auth: 'anonymous' })

    await page.goto('/this-route-does-not-exist')

    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
    await expect(page.getByRole('link', { name: /dashboard|home/i })).toBeVisible()
  })

  test('renders the application error boundary for an unexpected render failure', async ({ page }) => {
    let breakRendering = true
    await installMockApi(page, {
      auth: 'instructor',
      resolver: (call) => {
        if (call.method === 'GET' && call.path === '/subjects') {
          return breakRendering ? {
            json: [
              {
                ...fixtures.subject,
                name: { unexpected: 'object instead of a string' },
              },
            ],
          } : { json: [] }
        }
        return undefined
      },
    })

    await page.goto('/dashboard')

    await expect(page.getByRole('heading', { name: 'Something went wrong' })).toBeVisible()
    breakRendering = false
    await page.getByRole('button', { name: 'Try again' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'Your Subjects' })).toBeVisible()
  })
})
