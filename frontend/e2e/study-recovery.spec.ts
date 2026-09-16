import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'

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
