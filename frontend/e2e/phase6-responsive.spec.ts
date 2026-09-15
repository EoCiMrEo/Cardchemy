import { expect, test } from '@playwright/test'

import {
  expectMinimumTouchTarget,
  expectNoHorizontalOverflow,
  expectNoNestedInteractiveControls,
} from './support/a11y'
import { fixtures, installMockApi } from './support/mockApi'
import { studyCards, studySession } from './support/studyFixtures'

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

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
})

test('long header, email, subject actions, and invitation dialog fit a narrow viewport', async ({ page }) => {
  const longSubject = {
    ...fixtures.subject,
    name: 'Advanced Molecular Biology With A Deliberately Long Course Name',
    description: 'A long description designed to wrap cleanly on a narrow mobile viewport.',
  }
  await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/auth/me') {
        return {
          json: {
            ...fixtures.user('instructor'),
            email: 'an.extremely.long.instructor.email.address@example-university.test',
          },
        }
      }
      if (call.method === 'GET' && call.path === '/subjects') return { json: [longSubject] }
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: longSubject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
        return { json: [{ ...fixtures.set, title: `${longSubject.name} Comprehensive Review Set` }] }
      }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') {
        return { json: { jobs: [] } }
      }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') {
        return { json: generationLimits }
      }
      return undefined
    },
  })

  await page.goto('/dashboard')
  await expect(page.getByText('an.extremely.long.instructor.email.address@example-university.test')).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectMinimumTouchTarget(page, 'button:has-text("Logout")')
  await expectMinimumTouchTarget(page, 'button:has-text("New Subject")')
  await expectNoNestedInteractiveControls(page)

  await page.getByRole('link', { name: /Advanced Molecular Biology/ }).click()
  await expect(page.getByRole('heading', { name: longSubject.name, exact: true })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectMinimumTouchTarget(page, 'button:has-text("Invite")')
  await expectMinimumTouchTarget(page, 'button:has-text("Edit")')
  await expectMinimumTouchTarget(page, 'button:has-text("Delete")')

  await page.getByRole('button', { name: 'Invite', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Invite Students' })
  await expect(dialog).toBeVisible()
  await expectNoHorizontalOverflow(page)
  const dialogDimensions = await dialog.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }))
  expect(dialogDimensions.scrollWidth).toBeLessThanOrEqual(dialogDimensions.clientWidth + 1)
  await expectMinimumTouchTarget(page, '[role="dialog"] button:has-text("Generate Invite Link")')
  await expectMinimumTouchTarget(page, '[role="dialog"] button:has-text("Close")')
})

test('timed mobile study controls fit without overflow and keep touch targets large enough', async ({ page }) => {
  await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/study/sets/set-1/session') {
        return { json: studySession([studyCards[0]], 30) }
      }
      return undefined
    },
  })

  await page.goto('/study/set-1')
  await expect(page.getByRole('heading', { name: studyCards[0].front_content })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await expectMinimumTouchTarget(page, 'button[aria-label="Leave study session"]')

  const answerButtons = page.locator('main button')
  await expect(answerButtons).toHaveCount(4)
  for (let index = 0; index < await answerButtons.count(); index += 1) {
    const box = await answerButtons.nth(index).boundingBox()
    expect(box?.width ?? 0).toBeGreaterThanOrEqual(44)
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
  }
})
