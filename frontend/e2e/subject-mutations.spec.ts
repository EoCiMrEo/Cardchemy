import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'
import { generationResponse } from './support/generation'

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
                invite_url: 'https://cards.example.com/join?token=generated-invitation-token',
                delivery_queued: false,
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
