import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'
import type { ApiCall, MockResponse } from './support/mockApi'

const generationLimits = {
  generation_available: true,
  ai_provider: 'test-provider',
  ai_model: 'test-model',
  ai_pricing_configured: true,
  unavailable_reasons: [],
  max_upload_bytes: 10_000_000,
  max_pages: 100,
  max_extracted_chars: 100_000,
  min_card_count: 1,
  max_card_count: 100,
  daily_jobs_per_user: 10,
  daily_cards_per_user: 1_000,
  daily_upload_bytes_per_user: 100_000_000,
  max_active_jobs_per_user: 3,
  daily_jobs_remaining: 10,
  daily_cards_remaining: 1_000,
  daily_upload_bytes_remaining: 100_000_000,
  active_job_slots_remaining: 3,
  deployment_queue_slots_remaining: 10,
  quota_resets_at: '2026-09-16T00:00:00Z',
  failed_source_retention_hours: 24,
  upload_reservation_minutes: 15,
  ocr_enabled: false,
}

function generationResponse(call: ApiCall): MockResponse | undefined {
  if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') {
    return { json: { jobs: [] } }
  }
  if (call.method === 'GET' && call.path === '/flashcards/generation-limits') {
    return { json: generationLimits }
  }
  return undefined
}

test.describe('role-aware subject details and recovery', () => {
  test('selects the instructor view and retries one failed subject load', async ({ page }) => {
    let allowLoad = false
    const api = await installMockApi(page, {
      auth: 'instructor',
      resolver: (call) => {
        if (call.method === 'GET' && call.path === '/subjects/subject-1') {
          return allowLoad
            ? { json: fixtures.subject }
            : { status: 503, json: { detail: 'Instructor subject temporarily unavailable' } }
        }
        if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
          return allowLoad
            ? { json: [fixtures.set] }
            : { status: 503, json: { detail: 'Instructor sets temporarily unavailable' } }
        }
        return generationResponse(call)
      },
    })

    await page.goto('/subjects/subject-1')
    await expect(page.getByRole('alert')).toContainText(/temporarily unavailable/i)

    const subjectCallsBeforeRetry = api.count('GET', '/subjects/subject-1')
    const setCallsBeforeRetry = api.count('GET', '/subjects/subject-1/sets')
    allowLoad = true
    await page.getByRole('button', { name: 'Retry' }).click()

    await expect(page.getByRole('heading', { name: fixtures.subject.name })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Invite', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Edit', exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Study Now' })).toHaveCount(0)
    expect(api.count('GET', '/subjects/subject-1')).toBe(subjectCallsBeforeRetry + 1)
    expect(api.count('GET', '/subjects/subject-1/sets')).toBe(setCallsBeforeRetry + 1)
    expect(api.count('GET', '/study/sets/set-1/progress')).toBe(0)
  })

  test('selects the student view, retries its load, and recovers partial authoritative progress', async ({
    page,
  }) => {
    let allowLoad = false
    let allowProgress = false
    const authoritativeProgress = {
      ...fixtures.progress,
      completion_percentage: 37,
      mastery_percentage: 63,
    }
    const api = await installMockApi(page, {
      auth: 'student',
      resolver: (call) => {
        if (call.method === 'GET' && call.path === '/subjects/subject-1') {
          return allowLoad
            ? { json: fixtures.subject }
            : { status: 503, json: { detail: 'Student course temporarily unavailable' } }
        }
        if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
          return allowLoad
            ? { json: [fixtures.set] }
            : { status: 503, json: { detail: 'Published sets temporarily unavailable' } }
        }
        if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') {
          return allowProgress
            ? { json: authoritativeProgress }
            : { status: 503, json: { detail: 'Progress temporarily unavailable' } }
        }
        return undefined
      },
    })

    await page.goto('/subjects/subject-1')
    await expect(page.getByRole('alert')).toContainText(/temporarily unavailable/i)

    const subjectCallsBeforeRetry = api.count('GET', '/subjects/subject-1')
    const setCallsBeforeRetry = api.count('GET', '/subjects/subject-1/sets')
    allowLoad = true
    await page.getByRole('button', { name: 'Retry' }).click()

    await expect(page.getByRole('heading', { name: fixtures.subject.name })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Study Now' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Invite', exact: true })).toHaveCount(0)
    expect(api.count('GET', '/subjects/subject-1')).toBe(subjectCallsBeforeRetry + 1)
    expect(api.count('GET', '/subjects/subject-1/sets')).toBe(setCallsBeforeRetry + 1)
    await expect(page.getByRole('alert')).toContainText('Some progress details could not be loaded')

    const subjectCallsBeforeProgressRetry = api.count('GET', '/subjects/subject-1')
    const setCallsBeforeProgressRetry = api.count('GET', '/subjects/subject-1/sets')
    const progressCallsBeforeRetry = api.count('GET', '/study/sets/set-1/progress')
    allowProgress = true
    await page.getByRole('alert').getByRole('button', { name: 'Retry' }).click()

    await expect(page.getByText('37% complete')).toBeVisible()
    await expect(page.getByText('63% mastery')).toBeVisible()
    expect(api.count('GET', '/subjects/subject-1')).toBe(subjectCallsBeforeProgressRetry + 1)
    expect(api.count('GET', '/subjects/subject-1/sets')).toBe(setCallsBeforeProgressRetry + 1)
    expect(api.count('GET', '/study/sets/set-1/progress')).toBe(progressCallsBeforeRetry + 1)
  })
})

test('student dashboard recovers its load and retries a failed join without duplicating requests', async ({
  page,
}) => {
  let allowSubjects = false
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects') {
        return allowSubjects
          ? { json: [fixtures.subject] }
          : { status: 503, json: { detail: 'Student courses temporarily unavailable' } }
      }
      if (call.method === 'POST' && call.path === '/subjects/invitations/accept') {
        return callNumber === 1
          ? { status: 503, json: { detail: 'Invitation service temporarily unavailable' } }
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

  await page.goto('/dashboard')
  await expect(page.getByRole('alert')).toContainText('Student courses temporarily unavailable')

  const loadCallsBeforeRetry = api.count('GET', '/subjects')
  allowSubjects = true
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('heading', { name: fixtures.subject.name })).toBeVisible()
  expect(api.count('GET', '/subjects')).toBe(loadCallsBeforeRetry + 1)

  await page.getByRole('button', { name: 'Join Course', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('textbox', { name: 'Invitation token' }).fill('  dashboard-invite  ')
  await dialog.getByRole('button', { name: 'Join Course', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Invitation service temporarily unavailable')

  const joinCallsBeforeRetry = api.count('POST', '/subjects/invitations/accept')
  const loadCallsBeforeJoinRetry = api.count('GET', '/subjects')
  await dialog.getByRole('button', { name: 'Join Course', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect.poll(() => api.count('GET', '/subjects')).toBe(loadCallsBeforeJoinRetry + 1)
  expect(api.count('POST', '/subjects/invitations/accept')).toBe(joinCallsBeforeRetry + 1)
  expect(api.callsFor('POST', '/subjects/invitations/accept').map((call) => call.body)).toEqual([
    { token: 'dashboard-invite' },
    { token: 'dashboard-invite' },
  ])
})

test('study mode retries one failed load and preserves the answer for a failed save retry', async ({
  page,
}) => {
  let allowSession = false
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return allowSession
          ? {
              json: {
                cards: [
                  {
                    id: fixtures.cards[0].id,
                    set_id: fixtures.cards[0].set_id,
                    front_content: fixtures.cards[0].front_content,
                    options: fixtures.cards[0].options,
                    card_type: 'multiple_choice',
                  },
                ],
                total_due: 1,
                new_cards: 1,
                review_cards: 0,
                time_limit: null,
              },
            }
          : { status: 503, json: { detail: 'Study session temporarily unavailable' } }
      }
      if (call.method === 'POST' && call.path === '/study/progress') {
        return callNumber === 1
          ? { status: 503, json: { detail: 'Progress save temporarily unavailable' } }
          : {
              json: {
                progress: {
                  id: 'progress-1',
                  flashcard_id: fixtures.cards[0].id,
                  status: 'learning',
                  ease_factor: 2.5,
                  interval_days: 1,
                  next_review: '2026-09-16T00:00:00Z',
                  last_reviewed: '2026-09-15T00:00:00Z',
                  correct_count: 1,
                  incorrect_count: 0,
                },
                is_correct: true,
                quality: 5,
                correct_option: fixtures.cards[0].back_content,
                correct_option_index: 1,
              },
            }
      }
      return undefined
    },
  })

  await page.goto('/study/set-1')
  await expect(page.getByRole('alert')).toContainText('Study session temporarily unavailable')

  const sessionCallsBeforeRetry = api.count('GET', '/study/sets/set-1/session')
  allowSession = true
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('heading', { name: fixtures.cards[0].front_content })).toBeVisible()
  expect(api.count('GET', '/study/sets/set-1/session')).toBe(sessionCallsBeforeRetry + 1)

  await page.getByRole('button', { name: /Mitochondrion/ }).click()
  await expect(page.getByRole('alert')).toContainText('Progress save temporarily unavailable')
  expect(page.getByRole('button', { name: 'Next Question' })).toHaveCount(0)

  const progressCallsBeforeRetry = api.count('POST', '/study/progress')
  await page.getByRole('button', { name: 'Retry answer' }).click()
  await expect(page.getByText('Correct!', { exact: true })).toBeVisible()
  expect(api.count('POST', '/study/progress')).toBe(progressCallsBeforeRetry + 1)
  expect(api.callsFor('POST', '/study/progress').map((call) => call.body)).toEqual([
    { flashcard_id: fixtures.cards[0].id, selected_option: fixtures.cards[0].back_content },
    { flashcard_id: fixtures.cards[0].id, selected_option: fixtures.cards[0].back_content },
  ])
})

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
  expect(new URL(page.url()).searchParams.get('token')).toBe(inviteToken)

  await page.getByRole('textbox', { name: 'Email' }).fill('student@example.com')
  await page.getByLabel('Password').fill('correct-horse-battery-staple')
  await page.getByRole('button', { name: 'Sign In' }).click()

  await expect(page.getByRole('heading', { name: 'Course Joined' })).toBeVisible()
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

test('retries subject creation exactly once with the same payload', async ({ page }) => {
  let created = false
  const createdSubject = { ...fixtures.subject, name: 'Chemistry' }
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects') {
        return { json: created ? [createdSubject] : [] }
      }
      if (call.method === 'POST' && call.path === '/subjects') {
        if (callNumber === 1) {
          return { status: 503, json: { detail: 'Subject creation temporarily unavailable' } }
        }
        created = true
        return { json: createdSubject }
      }
      return undefined
    },
  })

  await page.goto('/dashboard')
  await page.getByRole('button', { name: 'New Subject' }).click()
  await page.getByRole('textbox', { name: 'Subject name' }).fill(createdSubject.name)
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Subject creation temporarily unavailable')

  const createCallsBeforeRetry = api.count('POST', '/subjects')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.getByRole('heading', { name: createdSubject.name })).toBeVisible()
  expect(api.count('POST', '/subjects')).toBe(createCallsBeforeRetry + 1)
  expect(api.callsFor('POST', '/subjects').map((call) => call.body)).toEqual([
    { name: createdSubject.name },
    { name: createdSubject.name },
  ])
})

test('keeps subject, set, and invitation mutation dialogs recoverable after server errors', async ({
  page,
}) => {
  let currentSubject = { ...fixtures.subject }
  let currentSet = { ...fixtures.set }
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') {
        return { json: currentSubject }
      }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
        return { json: [currentSet] }
      }
      if (call.method === 'PUT' && call.path === '/subjects/subject-1') {
        if (callNumber === 1) {
          return { status: 503, json: { detail: 'Subject update temporarily unavailable' } }
        }
        currentSubject = { ...currentSubject, ...(call.body as Partial<typeof currentSubject>) }
        return { json: currentSubject }
      }
      if (call.method === 'PUT' && call.path === '/subjects/subject-1/sets/set-1') {
        if (callNumber === 1) {
          return { status: 503, json: { detail: 'Set update temporarily unavailable' } }
        }
        currentSet = { ...currentSet, ...(call.body as Partial<typeof currentSet>) }
        return { json: currentSet }
      }
      if (call.method === 'POST' && call.path === '/subjects/subject-1/invite') {
        return callNumber === 1
          ? { status: 503, json: { detail: 'Invitation generation temporarily unavailable' } }
          : {
              json: {
                token: 'generated-invitation-token',
                subject_id: fixtures.subject.id,
                expires_at: '2026-09-16T00:00:00Z',
              },
            }
      }
      return generationResponse(call)
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByRole('heading', { name: fixtures.subject.name })).toBeVisible()

  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByRole('textbox', { name: 'Name' }).fill('Advanced Biology')
  await dialog.getByRole('button', { name: 'Save Changes' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Subject update temporarily unavailable')
  const subjectUpdatesBeforeRetry = api.count('PUT', '/subjects/subject-1')
  await dialog.getByRole('button', { name: 'Save Changes' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('heading', { name: 'Advanced Biology' })).toBeVisible()
  expect(api.count('PUT', '/subjects/subject-1')).toBe(subjectUpdatesBeforeRetry + 1)
  expect(api.callsFor('PUT', '/subjects/subject-1').map((call) => call.body)).toEqual([
    { name: 'Advanced Biology', description: fixtures.subject.description },
    { name: 'Advanced Biology', description: fixtures.subject.description },
  ])

  await page.getByRole('button', { name: `Edit ${fixtures.set.title}` }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByRole('textbox', { name: 'Title' }).fill('Cell structures revised')
  await dialog.getByRole('button', { name: 'Save Changes' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Set update temporarily unavailable')
  const setUpdatesBeforeRetry = api.count('PUT', '/subjects/subject-1/sets/set-1')
  await dialog.getByRole('button', { name: 'Save Changes' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('heading', { name: 'Cell structures revised' })).toBeVisible()
  expect(api.count('PUT', '/subjects/subject-1/sets/set-1')).toBe(setUpdatesBeforeRetry + 1)
  expect(api.callsFor('PUT', '/subjects/subject-1/sets/set-1').map((call) => call.body)).toEqual([
    {
      title: 'Cell structures revised',
      description: fixtures.set.description,
      is_published: fixtures.set.is_published,
      time_limit: null,
    },
    {
      title: 'Cell structures revised',
      description: fixtures.set.description,
      is_published: fixtures.set.is_published,
      time_limit: null,
    },
  ])

  await page.getByRole('button', { name: 'Invite', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Generate Invite Link' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Invitation generation temporarily unavailable')
  const inviteCallsBeforeRetry = api.count('POST', '/subjects/subject-1/invite')
  await dialog.getByRole('button', { name: 'Generate Invite Link' }).click()
  await expect(dialog.getByRole('status')).toContainText('Link generated successfully')
  expect(api.count('POST', '/subjects/subject-1/invite')).toBe(inviteCallsBeforeRetry + 1)
  expect(api.callsFor('POST', '/subjects/subject-1/invite').map((call) => call.body)).toEqual([
    { expires_in_hours: 24 },
    { expires_in_hours: 24 },
  ])
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
  expect(api.count('GET', '/subjects/sets/set-1')).toBe(2)
  expect(api.count('GET', '/flashcards/sets/set-1/cards')).toBe(2)
})

test('validates every local edit branch while preserving all unrelated card actions', async ({ page }) => {
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/sets/set-1') {
        return { json: fixtures.set }
      }
      if (call.method === 'GET' && call.path === '/flashcards/sets/set-1/cards') {
        return {
          json: [fixtures.cards[0], { ...fixtures.cards[1], is_approved: false }],
        }
      }
      return undefined
    },
  })

  await page.goto('/sets/set-1')
  await page
    .getByRole('button', { name: `Edit ${fixtures.cards[0].front_content}`, exact: true })
    .click()

  await expect(
    page.getByRole('button', { name: `Approve ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: `Edit ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: `Delete ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()

  const writesBeforeValidation = api.count('PUT', '/flashcards/card-1')
  await page.getByRole('textbox', { name: 'Front' }).fill('')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Enter a question before saving')
  expect(api.count('PUT', '/flashcards/card-1')).toBe(writesBeforeValidation)

  await page.getByRole('textbox', { name: 'Front' }).fill(fixtures.cards[0].front_content)
  const optionOne = await page.getByRole('textbox', { name: 'Option 1' }).inputValue()
  await page.getByRole('textbox', { name: 'Option 2' }).fill(optionOne.toUpperCase())
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Each answer option must be unique')
  expect(api.count('PUT', '/flashcards/card-1')).toBe(writesBeforeValidation)
})
