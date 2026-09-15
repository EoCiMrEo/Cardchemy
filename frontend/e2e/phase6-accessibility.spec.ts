import { expect, test } from '@playwright/test'

import {
  expectNoNestedInteractiveControls,
  expectNoSeriousOrCriticalViolations,
} from './support/a11y'
import { fixtures, installMockApi } from './support/mockApi'
import { answerResponse, studyCards, studySession } from './support/studyFixtures'

test('login has associated fields and no serious or critical axe violations', async ({ page }) => {
  await installMockApi(page, { auth: 'anonymous' })
  await page.goto('/login')

  await expect(page.getByLabel('Email')).toHaveAttribute('type', 'email')
  await expect(page.getByLabel('Password')).toHaveAttribute('type', 'password')
  await expectNoNestedInteractiveControls(page)
  await expectNoSeriousOrCriticalViolations(page)
})

test('dashboard, failed-save, and completion states have no serious or critical axe violations', async ({
  page,
}) => {
  await installMockApi(page, {
    auth: 'student',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return { json: studySession([studyCards[0]]) }
      }
      if (call.method === 'POST' && call.path === '/study/progress') {
        if (callNumber === 1) {
          return { status: 503, json: { detail: 'Progress storage is temporarily unavailable' } }
        }
        const body = call.body as { selected_option: string | null }
        return { json: answerResponse(studyCards[0], body.selected_option) }
      }
      return undefined
    },
  })

  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'My Courses' })).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)

  await page.goto('/study/set-1')
  await page.getByRole('button', { name: /Mitochondrion/ }).click()
  await expect(page.getByRole('alert')).toContainText('Progress storage is temporarily unavailable')
  await expect(page.getByRole('button', { name: 'Retry answer' })).toBeFocused()
  await expectNoSeriousOrCriticalViolations(page)

  await page.getByRole('button', { name: 'Retry answer' }).click()
  await page.getByRole('button', { name: 'Next Question' }).click()
  await expect(page.getByRole('heading', { name: 'Session Complete!' })).toBeFocused()
  await expectNoSeriousOrCriticalViolations(page)
})

test('student subject progress exposes meaningful progress semantics', async ({ page }) => {
  await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') {
        return { json: fixtures.subject }
      }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
        return { json: [fixtures.set] }
      }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') {
        return { json: fixtures.progress }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  const progress = page.getByRole('progressbar', { name: `Study progress for ${fixtures.set.title}` })
  await expect(progress).toHaveAttribute('aria-valuemin', '0')
  await expect(progress).toHaveAttribute('aria-valuemax', '100')
  await expect(progress).toHaveAttribute('aria-valuenow', '37')
  await expect(progress).toHaveAttribute('aria-valuetext', '37% complete, 63% mastery')
  await expect(page.getByRole('link', { name: 'Back to Dashboard' })).toBeVisible()
  await expectNoNestedInteractiveControls(page)
  await expectNoSeriousOrCriticalViolations(page)
})

test('study question, timer, and answer feedback remain accessible without color alone', async ({ page }) => {
  await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return { json: studySession([studyCards[0]], 30) }
      }
      if (call.method === 'POST' && call.path === '/study/progress') {
        const body = call.body as { selected_option: string | null }
        return { json: answerResponse(studyCards[0], body.selected_option) }
      }
      return undefined
    },
  })

  await page.goto('/study/set-1')
  const timer = page.getByRole('progressbar', { name: 'Time remaining for this question' })
  await expect(timer).toHaveAttribute('aria-valuemin', '0')
  await expect(timer).toHaveAttribute('aria-valuemax', '100')
  await expect(timer).toHaveAttribute('aria-valuetext', /seconds remaining/)
  await expect(page.getByRole('button', { name: 'Leave study session' })).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)

  await page.getByRole('button', { name: /Nucleus/ }).first().click()
  await expect(page.getByText('Incorrect', { exact: true })).toBeVisible()
  await expect(page.getByText('Correct answer', { exact: true })).toBeVisible()
  await expect(page.getByText('Your answer', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Next Question' })).toBeFocused()
  await expectNoNestedInteractiveControls(page)
  await expectNoSeriousOrCriticalViolations(page)
})

test('set actions and preview expose names, dialog semantics, and non-nested controls', async ({ page }) => {
  await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/sets/set-1') {
        return { json: fixtures.set }
      }
      if (call.method === 'GET' && call.path === '/flashcards/sets/set-1/cards') {
        return { json: fixtures.cards }
      }
      return undefined
    },
  })

  await page.goto('/sets/set-1')
  await expect(page.getByRole('link', { name: 'Back to Dashboard' })).toBeVisible()
  await expect(
    page.getByRole('button', { name: `Delete ${fixtures.cards[0].front_content}` }),
  ).toBeVisible()
  await expectNoNestedInteractiveControls(page)
  await expectNoSeriousOrCriticalViolations(page)

  await page.getByRole('button', { name: 'Preview' }).click()
  const dialog = page.getByRole('dialog', { name: `${fixtures.set.title} - Preview` })
  await expect(dialog).toBeVisible()
  await expect(dialog).toHaveAttribute('aria-describedby', /\S+/)
  const descriptionId = await dialog.getAttribute('aria-describedby')
  expect(descriptionId).toBeTruthy()
  await expect(page.locator(`#${descriptionId ?? 'missing-dialog-description'}`)).toContainText(
    'Select the card to reveal the answer',
  )
  await expect(dialog.getByRole('button', { name: 'Show Answer' })).toHaveCount(2)
  await expect(dialog.getByRole('button', { name: 'Close' })).toBeVisible()
  await expectNoNestedInteractiveControls(page)
  await expectNoSeriousOrCriticalViolations(page)
})

test('reduced-motion users receive immediate state changes and equivalent text cues', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/sets/set-1') {
        return { json: fixtures.set }
      }
      if (call.method === 'GET' && call.path === '/flashcards/sets/set-1/cards') {
        return { json: fixtures.cards }
      }
      return undefined
    },
  })

  await page.goto('/sets/set-1')
  expect(await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true)
  await page.getByRole('button', { name: 'Preview' }).click()
  const cardControl = page.locator('button[aria-describedby="preview-card-content"]')
  await cardControl.click()
  await expect(cardControl).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText(`Answer: ${fixtures.cards[0].back_content}`, { exact: true })).toBeAttached()
  await page.waitForTimeout(50)
  const runningAnimations = await page.evaluate(() =>
    document.getAnimations().filter((animation) => animation.playState === 'running').length,
  )
  expect(runningAnimations).toBe(0)
})
