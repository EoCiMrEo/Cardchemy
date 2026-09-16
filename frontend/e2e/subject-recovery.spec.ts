import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'
import { generationResponse } from './support/generation'

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
