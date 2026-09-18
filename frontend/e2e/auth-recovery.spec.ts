import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'

test('shows backend failures in login, registration, forgot-password, and reset-password forms', async ({
  page,
}) => {
  const api = await installMockApi(page, {
    auth: 'anonymous',
    resolver: (call) => {
      if (call.method === 'POST' && call.path === '/auth/login') {
        return { status: 401, json: { detail: 'Credentials rejected by the server' } }
      }
      if (call.method === 'POST' && call.path === '/auth/register') {
        return { status: 422, json: { detail: 'Registration invitation was rejected' } }
      }
      if (call.method === 'POST' && call.path === '/auth/password/forgot') {
        return { status: 503, json: { detail: 'Reset request service is unavailable' } }
      }
      if (call.method === 'POST' && call.path === '/auth/password/reset') {
        return { status: 400, json: { detail: 'Reset token is expired' } }
      }
      return undefined
    },
  })

  await test.step('login', async () => {
    await page.goto('/login')
    await page.getByRole('textbox', { name: 'Email' }).fill('student@example.com')
    await page.getByLabel('Password').fill('wrong-password')
    await page.getByRole('button', { name: 'Sign In' }).click()
    await expect(page.getByRole('alert')).toContainText('Credentials rejected by the server')
    expect(api.count('POST', '/auth/login')).toBe(1)
  })

  await test.step('registration', async () => {
    await page.goto('/register?token=valid-invitation-token')
    await page.getByRole('textbox', { name: 'Full Name' }).fill('Student Example')
    await page.getByRole('textbox', { name: 'Email' }).fill('student@example.com')
    await page.getByLabel('Password').fill('long-enough-password')
    await page.getByRole('button', { name: 'Create Student Account' }).click()
    await expect(page.getByRole('alert')).toContainText('Registration invitation was rejected')
    expect(api.count('POST', '/auth/register')).toBe(1)
  })

  await test.step('forgot password', async () => {
    await page.goto('/forgot-password')
    await page.getByRole('textbox', { name: 'Email' }).fill('student@example.com')
    await page.getByRole('button', { name: 'Send reset link' }).click()
    await expect(page.getByRole('status')).toContainText('Reset request service is unavailable')
    expect(api.count('POST', '/auth/password/forgot')).toBe(1)
  })

  await test.step('reset password', async () => {
    await page.goto('/reset-password?token=expired-reset-token')
    await page.getByLabel('New password').fill('replacement-password')
    await page.getByRole('button', { name: 'Reset password' }).click()
    await expect(page.getByText('Reset token is expired', { exact: true })).toBeVisible()
    expect(api.count('POST', '/auth/password/reset')).toBe(1)
  })
})

test('preserves an existing student invitation through sign-in and completes the join', async ({ page }) => {
  const inviteToken = 'existing-student-invite-token'
  const api = await installMockApi(page, {
    auth: 'anonymous',
    resolver: (call) => {
      if (call.method === 'POST' && call.path === '/auth/login') {
        return {
          json: {
            access_token: 'existing-student-access-token',
            token_type: 'bearer',
            expires_in: 900,
          },
        }
      }
      if (call.method === 'GET' && call.path === '/auth/me') {
        return { json: fixtures.user('student') }
      }
      if (call.method === 'POST' && call.path === '/subjects/invitations/accept') {
        return {
          json: {
            message: 'Successfully joined course',
            subject_name: fixtures.subject.name,
          },
        }
      }
      return undefined
    },
  })

  await page.goto(`/join?token=${encodeURIComponent(inviteToken)}`)
  await expect(page).toHaveURL(/\/register\?token=/)
  await page.getByRole('link', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/login\?token=/)
  await expect(page.getByRole('heading', { name: 'Welcome Back', exact: true })).toBeVisible()
  expect(new URL(page.url()).searchParams.get('token')).toBe(inviteToken)

  await page.getByRole('textbox', { name: 'Email' }).fill('student@example.com')
  await page.getByLabel('Password').fill('correct-horse-battery-staple')
  await page.getByRole('button', { name: 'Sign In' }).click()

  await expect(page.getByRole('heading', { name: 'Course Joined' })).toBeVisible()
  expect(api.callsFor('POST', '/auth/login')[0]?.body).toEqual({
    username: 'student@example.com',
    password: 'correct-horse-battery-staple',
  })
  expect(api.count('POST', '/subjects/invitations/accept')).toBe(1)
  expect(api.callsFor('POST', '/subjects/invitations/accept')[0]?.body).toEqual({
    token: inviteToken,
  })
})

test('keeps the session active after failed logout and retries exactly once', async ({ page }) => {
  let allowLogout = false
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects') return { json: [] }
      if (call.method === 'POST' && call.path === '/auth/logout') {
        return allowLogout
          ? { json: { message: 'Signed out' } }
          : { status: 503, json: { detail: 'Sign out service temporarily unavailable' } }
      }
      return undefined
    },
  })

  await page.goto('/dashboard')
  await page.getByRole('button', { name: 'Logout' }).click()
  await expect(page.getByRole('alert')).toContainText('Sign out service temporarily unavailable')
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: 'Your Subjects' })).toBeVisible()

  const logoutCallsBeforeRetry = api.count('POST', '/auth/logout')
  allowLogout = true
  await page.getByRole('button', { name: 'Logout' }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(api.count('POST', '/auth/logout')).toBe(logoutCallsBeforeRetry + 1)
})

test('does not retry protected resources after refresh itself fails', async ({ page }) => {
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
  await page.waitForTimeout(150)

  expect(api.count('POST', '/auth/refresh')).toBe(2)
  expect(api.count('GET', '/subjects/sets/set-1')).toBe(1)
  expect(api.count('GET', '/flashcards/sets/set-1/cards')).toBe(1)
})
