import { expect, test } from '@playwright/test'

import { expectNoSeriousOrCriticalViolations } from './support/a11y'
import { generationLimits } from './support/generation'
import { fixtures, installMockApi } from './support/mockApi'
import type { GenerationJob } from '../src/services/types'

function pendingJob(overrides: Partial<GenerationJob> = {}): GenerationJob {
  return {
    ...fixtures.generationJob,
    id: 'card-choice-job',
    flashcard_set_id: null,
    status: 'awaiting_card_choice',
    stage: 'awaiting_card_choice',
    progress: 100,
    requested_card_count: 20,
    generated_card_count: null,
    accepted_card_count: 0,
    rejected_card_count: 32,
    valid_candidate_count: 12,
    card_choice_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    selected_card_count: null,
    can_accept_smaller_target: true,
    latest_attempt_rejected_card_count: 12,
    latest_attempt_quality_diagnostics: null,
    retry_estimated_additional_cost_microusd: 10_000,
    previous_attempt_cost_unknown: true,
    can_cancel: true,
    can_retry: true,
    completed_at: null,
    ...overrides,
  }
}

test('instructor confirms an exact smaller set after reload with one idempotent choice', async ({ page }) => {
  let job = pendingJob()
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') return { json: generationLimits }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') return { json: { jobs: [job] } }
      if (call.method === 'POST' && call.path === '/flashcards/generation-jobs/card-choice-job/card-choice') {
        if (callNumber === 1) return { status: 503, json: { detail: 'Choice temporarily unavailable' } }
        job = pendingJob({
          status: 'completed', stage: 'completed', flashcard_set_id: 'new-set',
          generated_card_count: 10, accepted_card_count: 10, selected_card_count: 10,
          valid_candidate_count: 0, card_choice_expires_at: null,
          can_accept_smaller_target: false, can_cancel: false, can_retry: false,
          completed_at: new Date().toISOString(),
        })
        return { json: job }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await page.reload()
  await expect(page.getByText('This attempt verified 12 distinct cards out of the 20 requested.', { exact: false })).toBeVisible()
  await expect(page.getByText('Rejected across all attempts').locator('..')).toContainText('32')
  await page.setViewportSize({ width: 360, height: 780 })
  await page.getByRole('button', { name: 'Choose a smaller set' }).click()
  const dialog = page.getByRole('dialog', { name: 'Create a smaller flashcard set?' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('spinbutton', { name: 'Number of validated cards to keep' }).fill('10')
  await expectNoSeriousOrCriticalViolations(page)
  await dialog.getByRole('button', { name: 'Create set with 10 cards' }).focus()
  await page.keyboard.press('Enter')
  await expect(dialog.getByRole('alert')).toContainText('Choice temporarily unavailable')
  await expect(dialog.getByRole('spinbutton')).toBeDisabled()
  await dialog.getByRole('button', { name: 'Create set with 10 cards' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Review 10 cards' })).toBeVisible()

  const choices = api.callsFor('POST', '/flashcards/generation-jobs/card-choice-job/card-choice')
  expect(choices).toHaveLength(2)
  expect(choices.map((call) => call.body)).toEqual([{ card_count: 10 }, { card_count: 10 }])
  expect(choices[0].headers['idempotency-key']).toBe(choices[1].headers['idempotency-key'])
  expect(api.count('POST', '/flashcards/generation-jobs/card-choice-job/retry')).toBe(0)
  const widths = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: window.innerWidth }))
  expect(widths.body).toBeLessThanOrEqual(widths.viewport)
})

test('pursuing the original card target requires separate cost confirmation', async ({ page }) => {
  let job = pendingJob()
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') return { json: generationLimits }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') return { json: { jobs: [job] } }
      if (call.method === 'POST' && call.path === '/flashcards/generation-jobs/card-choice-job/retry') {
        job = pendingJob({
          status: 'queued', stage: 'queued', valid_candidate_count: 0,
          card_choice_expires_at: null, can_accept_smaller_target: false,
          can_cancel: true, can_retry: false,
        })
        return { json: job }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Start another AI generation attempt?' })
  await expect(dialog).toContainText('Estimated additional cost: $0.0100')
  await expect(dialog).toContainText('Previous attempt cost is unknown.')
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  expect(api.count('POST', '/flashcards/generation-jobs/card-choice-job/retry')).toBe(0)
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await dialog.getByRole('button', { name: 'Start new AI attempt' }).click()
  await expect(dialog).toHaveCount(0)
  expect(api.count('POST', '/flashcards/generation-jobs/card-choice-job/retry')).toBe(1)
  expect(api.callsFor('POST', '/flashcards/generation-jobs/card-choice-job/retry')[0].body).toEqual({ acknowledge_additional_cost: true })
  expect(api.count('POST', '/flashcards/generation-jobs/card-choice-job/card-choice')).toBe(0)
})
