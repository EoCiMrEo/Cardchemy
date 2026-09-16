import { expect, test } from '@playwright/test'

import { expectNoHorizontalOverflow } from './support/a11y'
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

function subjectPageResponse(call: ApiCall): MockResponse | undefined {
  if (call.method === 'GET' && call.path === '/subjects/subject-1') {
    return { json: fixtures.subject }
  }
  if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') {
    return { json: [fixtures.set] }
  }
  if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') {
    return { json: { jobs: [] } }
  }
  if (call.method === 'GET' && call.path === '/flashcards/generation-limits') {
    return { json: generationLimits }
  }
  return undefined
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
})

test('queues an emailed invitation and keeps its server-generated link copyable', async ({ page }) => {
  const inviteUrl = 'https://cards.example.com/join?token=emailed-invitation-token'
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'POST' && call.path === '/subjects/subject-1/invite') {
        return {
          json: {
            token: 'emailed-invitation-token',
            subject_id: fixtures.subject.id,
            expires_at: '2026-09-16T00:00:00Z',
            invite_url: inviteUrl,
            delivery_queued: true,
          },
        }
      }
      return subjectPageResponse(call)
    },
  })

  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Invite', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Invite Students' })
  const email = dialog.getByRole('textbox', { name: 'Student email (optional)' })
  await expect(email).toHaveAttribute('aria-describedby', 'invite-recipient-help')
  await email.fill('student@example.com')
  await dialog.getByRole('button', { name: 'Generate and Email Invite' }).click()

  await expect(dialog.getByRole('status')).toContainText('Invitation email queued for delivery')
  await expect(dialog.getByLabel('Copyable invitation link')).toHaveValue(inviteUrl)
  await expect(dialog.getByRole('button', { name: 'Copy invitation link' })).toBeVisible()
  expect(api.callsFor('POST', '/subjects/subject-1/invite').map((call) => call.body)).toEqual([
    { expires_in_hours: 24, recipient_email: 'student@example.com' },
  ])
  await expectNoHorizontalOverflow(page)
})

test('keeps copy-only invitations email-free and uses the backend absolute URL', async ({ page }) => {
  const inviteUrl = 'https://cards.example.com/join?token=copy-only-invitation-token'
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'POST' && call.path === '/subjects/subject-1/invite') {
        return {
          json: {
            token: 'copy-only-invitation-token',
            subject_id: fixtures.subject.id,
            expires_at: '2026-09-16T00:00:00Z',
            invite_url: inviteUrl,
            delivery_queued: false,
          },
        }
      }
      return subjectPageResponse(call)
    },
  })

  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Invite', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Invite Students' })
  await dialog.getByRole('button', { name: 'Generate Invite Link' }).click()

  await expect(dialog.getByRole('status')).toContainText('Link generated successfully')
  await expect(dialog.getByLabel('Copyable invitation link')).toHaveValue(inviteUrl)
  expect(api.callsFor('POST', '/subjects/subject-1/invite').map((call) => call.body)).toEqual([
    { expires_in_hours: 24 },
  ])
})
