import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'
import { generationLimits } from './support/generation'

test('renders durable provider request telemetry for a completed generation job', async ({ page }) => {
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') {
        return { json: fixtures.subject }
      }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
        return { json: [fixtures.set] }
      }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') {
        return { json: { jobs: [fixtures.generationJob] } }
      }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') {
        return { json: generationLimits }
      }
      return undefined
    },
  })

  const [profileResponse, jobsResponse] = await Promise.all([
    page.waitForResponse((response) => (
      new URL(response.url()).pathname === '/api/auth/me'
      && response.request().method() === 'GET'
    )),
    page.waitForResponse((response) => (
      new URL(response.url()).pathname === '/api/flashcards/generation-jobs'
      && response.request().method() === 'GET'
    )),
    page.goto('/subjects/subject-1'),
  ])
  expect(profileResponse.ok()).toBe(true)
  expect(jobsResponse.ok()).toBe(true)
  expect(api.callsFor('GET', '/flashcards/generation-jobs').at(-1)?.query.get('subject_id')).toBe('subject-1')

  const jobs = page.getByRole('region', { name: 'Generation jobs' })
  await expect(jobs.getByText('cell-biology.pdf')).toBeVisible()
  await expect(jobs.getByText('3 actual, 4 estimated, 1 retry')).toBeVisible()
  await expect(jobs.getByText('12.5 s')).toBeVisible()
  await expect(jobs.getByText('8,192')).toBeVisible()
})
