import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'
import { answerResponse, studyCards, studySession } from './support/studyFixtures'

test('reuses the exact idempotency key for a failed-save retry and rotates it for the next card', async ({
  page,
}) => {
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return { json: studySession() }
      }
      if (call.method === 'POST' && call.path === '/study/progress') {
        const body = call.body as { flashcard_id: string; selected_option: string | null }
        if (callNumber === 1) {
          return { status: 503, json: { detail: 'Progress storage is temporarily unavailable' } }
        }
        const card = studyCards.find((candidate) => candidate.id === body.flashcard_id) ?? studyCards[0]
        return { json: answerResponse(card, body.selected_option) }
      }
      return undefined
    },
  })

  await page.goto('/study/set-1')
  await page.getByRole('button', { name: /Mitochondrion/ }).click()

  await expect(page.getByRole('alert')).toContainText('Progress storage is temporarily unavailable')
  await expect(page.getByRole('heading', { name: studyCards[0].front_content })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Next Question' })).toHaveCount(0)
  expect(api.count('POST', '/study/progress')).toBe(1)

  await page.getByRole('button', { name: 'Retry answer' }).click()
  await expect(page.getByText('Correct!', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Next Question' }).click()
  await page.getByRole('button', { name: /Nucleus/ }).click()
  await expect(page.getByText('Correct!', { exact: true })).toBeVisible()

  const writes = api.callsFor('POST', '/study/progress')
  expect(writes).toHaveLength(3)
  const keys = writes.map((call) => call.headers['idempotency-key'])
  expect(keys[0]).toBeTruthy()
  expect(keys[1]).toBe(keys[0])
  expect(keys[2]).toBeTruthy()
  expect(keys[2]).not.toBe(keys[0])
  expect(writes[1]?.body).toEqual(writes[0]?.body)
})

test('locks a rapid double activation across the timer boundary to one progress write', async ({ page }) => {
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return { json: studySession([studyCards[0]], 1) }
      }
      if (call.method === 'POST' && call.path === '/study/progress') {
        const body = call.body as { selected_option: string | null }
        return { delayMs: 300, json: answerResponse(studyCards[0], body.selected_option) }
      }
      return undefined
    },
  })

  await page.goto('/study/set-1')
  const answer = page.getByRole('button', { name: /Mitochondrion/ })
  await expect(page.getByRole('progressbar', { name: 'Time remaining for this question' })).toBeVisible()
  await page.waitForTimeout(850)
  await answer.evaluate((button) => {
    const answerButton = button as HTMLButtonElement
    answerButton.click()
    answerButton.click()
  })

  await expect(page.getByRole('button', { name: 'Next Question' })).toBeVisible()
  await page.waitForTimeout(350)
  expect(api.count('POST', '/study/progress')).toBe(1)
})

test('an untimed card without answer options always offers an answer path and completes', async ({ page }) => {
  const optionlessCard = {
    id: 'optionless-card',
    set_id: 'set-1',
    front_content: 'Recall this concept without answer choices',
    options: [],
    card_type: 'multiple_choice',
  }
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return {
          json: {
            cards: [optionlessCard],
            total_due: 1,
            new_cards: 1,
            review_cards: 0,
            time_limit: null,
          },
        }
      }
      if (call.method === 'POST' && call.path === '/study/progress') {
        return {
          json: {
            progress: {
              id: 'progress-optionless-card',
              flashcard_id: optionlessCard.id,
              status: 'learning',
              ease_factor: 2.5,
              interval_days: 1,
              next_review: '2026-09-16T00:00:00Z',
              last_reviewed: '2026-09-15T00:00:00Z',
              correct_count: 0,
              incorrect_count: 1,
            },
            is_correct: false,
            quality: 1,
            correct_option: 'A recalled answer',
            correct_option_index: 0,
          },
        }
      }
      return undefined
    },
  })

  await page.goto('/study/set-1')
  await expect(page.getByRole('progressbar', { name: 'Time remaining for this question' })).toHaveCount(0)
  await expect(page.getByRole('alert')).toContainText('No answer options are available')
  await page.getByRole('button', { name: "I don't know" }).click()
  await expect(page.getByText('Incorrect', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Next Question' }).click()
  await expect(page.getByRole('heading', { name: 'Session Complete!' })).toBeVisible()

  expect(api.count('POST', '/study/progress')).toBe(1)
  expect(api.callsFor('POST', '/study/progress')[0]?.body).toEqual({
    flashcard_id: optionlessCard.id,
    selected_option: null,
  })
})

test('Review Again requests review_all and renders a real session', async ({ page }) => {
  const completeProgress = {
    ...fixtures.progress,
    studied: fixtures.progress.total,
    new: 0,
    completion_percentage: 100,
  }
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') {
        return { json: fixtures.subject }
      }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
        return { json: [fixtures.set] }
      }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') {
        return { json: completeProgress }
      }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return { json: studySession([studyCards[0]]) }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await page.getByRole('link', { name: 'Review Again' }).click()

  await expect(page).toHaveURL(/\/study\/set-1\?mode=review_all$/)
  await expect(page.getByRole('heading', { name: studyCards[0].front_content })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'All Caught Up!' })).toHaveCount(0)
  const sessionCall = api.callsFor('GET', '/study/sets/set-1/session').at(-1)
  expect(sessionCall?.query.get('mode')).toBe('review_all')
  expect(sessionCall?.query.get('limit')).toBe('20')
})

test('the complete study flow is operable with the keyboard at a mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return { json: studySession() }
      }
      if (call.method === 'POST' && call.path === '/study/progress') {
        const body = call.body as { flashcard_id: string; selected_option: string | null }
        const card = studyCards.find((candidate) => candidate.id === body.flashcard_id) ?? studyCards[0]
        return { json: answerResponse(card, body.selected_option) }
      }
      return undefined
    },
  })

  await page.goto('/study/set-1')
  await expect(page.getByRole('heading', { name: studyCards[0].front_content })).toBeFocused()

  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: /Nucleus/ }).first()).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: /Mitochondrion/ })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Next Question' })).toBeFocused()
  await page.keyboard.press('Enter')

  await expect(page.getByRole('heading', { name: studyCards[1].front_content })).toBeFocused()
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: /Nucleus/ })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Next Question' })).toBeFocused()
  await page.keyboard.press('Enter')

  await expect(page.getByRole('heading', { name: 'Session Complete!' })).toBeFocused()
  expect(api.count('POST', '/study/progress')).toBe(2)
})
