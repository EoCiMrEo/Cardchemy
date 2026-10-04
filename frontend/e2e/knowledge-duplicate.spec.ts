import { expect, test } from '@playwright/test'

import { expectNoSeriousOrCriticalViolations } from './support/a11y'
import { generationLimits } from './support/generation'
import { fixtures, installMockApi } from './support/mockApi'
import type { GenerationJob, KnowledgeDocument } from '../src/services/types'

const candidate = { document_id: 'document-1', title: 'Orbital motion', can_reuse: true }

function pendingJob(overrides: Partial<GenerationJob> = {}): GenerationJob {
  return {
    ...fixtures.generationJob,
    id: 'duplicate-job',
    job_kind: 'flashcards',
    flashcard_set_id: null,
    status: 'awaiting_choice',
    stage: 'awaiting_choice',
    progress: 0,
    knowledge_capture_status: 'pending',
    duplicate_candidate: candidate,
    choice_expires_at: '2026-09-25T12:00:00Z',
    can_cancel: true,
    can_retry: false,
    completed_at: null,
    ...overrides,
  }
}

test('pending duplicate choice survives reload and reuses Knowledge with one idempotent decision', async ({ page }) => {
  let job = pendingJob()
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') return { json: generationLimits }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') return { json: { jobs: [job] } }
      if (call.method === 'POST' && call.path === '/flashcards/generation-jobs/duplicate-job/knowledge-choice') {
        if (callNumber === 1) return { status: 503, json: { detail: 'Choice temporarily unavailable' } }
        job = pendingJob({
          status: 'queued', stage: 'queued', knowledge_capture_status: 'reused',
          knowledge_upload_outcome: 'reused', document_id: candidate.document_id,
          knowledge_content_revision_id: 'revision-1', duplicate_candidate: null,
          choice_expires_at: null,
        })
        return { json: job }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await page.reload()
  await page.getByRole('button', { name: 'Review matching Knowledge' }).click()
  const dialog = page.getByRole('dialog', { name: 'Matching Knowledge found' })
  await expect(dialog).toContainText('Orbital motion')
  await expect(dialog.getByRole('button', { name: 'Reuse Knowledge' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Create separate copy' })).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await page.setViewportSize({ width: 360, height: 780 })
  await page.getByRole('button', { name: 'Review matching Knowledge' }).click()
  await dialog.getByRole('button', { name: 'Reuse Knowledge' }).focus()
  await page.keyboard.press('Enter')
  await expect(dialog.getByRole('alert')).toContainText('Choice temporarily unavailable')
  await expect(dialog.getByRole('button', { name: 'Create separate copy' })).toBeDisabled()
  await dialog.getByRole('button', { name: 'Reuse Knowledge' }).focus()
  await page.keyboard.press('Enter')
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('Existing Knowledge revision reused; no new capture or indexing.')).toBeVisible()
  const choices = api.callsFor('POST', '/flashcards/generation-jobs/duplicate-job/knowledge-choice')
  expect(choices).toHaveLength(2)
  expect(choices.map((call) => call.body)).toEqual([{ choice: 'reuse' }, { choice: 'reuse' }])
  expect(choices[0].headers['idempotency-key']).toBe(choices[1].headers['idempotency-key'])

  const widths = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: window.innerWidth }))
  expect(widths.body).toBeLessThanOrEqual(widths.viewport)
})

test('incompatible duplicate offers separate copy or whole-job cancellation', async ({ page }) => {
  let job = pendingJob({ job_kind: 'knowledge_only', duplicate_candidate: { ...candidate, can_reuse: false } })
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') return { json: generationLimits }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') return { json: { jobs: [job] } }
      if (call.method === 'POST' && call.path === '/flashcards/generation-jobs/duplicate-job/knowledge-choice') {
        job = pendingJob({ job_kind: 'knowledge_only', status: 'queued', stage: 'queued', knowledge_upload_outcome: 'separate_copy', duplicate_candidate: null, choice_expires_at: null })
        return { json: job }
      }
      return undefined
    },
  })
  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Review matching Knowledge' }).click()
  const dialog = page.getByRole('dialog', { name: 'Matching Knowledge found' })
  await expect(dialog.getByRole('button', { name: 'Reuse Knowledge' })).toHaveCount(0)
  await expect(dialog).toContainText('cannot be reused')
  await dialog.getByRole('button', { name: 'Create separate copy' }).click()
  await expect(page.getByText('A separate private Knowledge copy was requested.')).toBeVisible()
  expect(api.callsFor('POST', '/flashcards/generation-jobs/duplicate-job/knowledge-choice')[0].body).toEqual({ choice: 'separate_copy' })
})

test('cancel in duplicate dialog ends the entire Knowledge upload job', async ({ page }) => {
  let job = pendingJob({ job_kind: 'knowledge_only' })
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') return { json: generationLimits }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') return { json: { jobs: [job] } }
      if (call.method === 'POST' && call.path === '/flashcards/generation-jobs/duplicate-job/cancel') {
        job = pendingJob({ job_kind: 'knowledge_only', status: 'cancelled', stage: 'cancelled', duplicate_candidate: null, choice_expires_at: null, can_cancel: false })
        return { json: job }
      }
      return undefined
    },
  })
  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Review matching Knowledge' }).click()
  await page.getByRole('dialog', { name: 'Matching Knowledge found' }).getByRole('button', { name: 'Cancel whole job' }).click()
  await expect(page.getByRole('dialog', { name: 'Matching Knowledge found' })).toHaveCount(0)
  expect(api.count('POST', '/flashcards/generation-jobs/duplicate-job/cancel')).toBe(1)
  expect(api.count('POST', '/flashcards/generation-jobs/duplicate-job/knowledge-choice')).toBe(0)
})

test('unchanged explicit revision reports no changes without asking for a duplicate choice', async ({ page }) => {
  const document: KnowledgeDocument = {
    id: 'document-1', subject_id: 'subject-1', title: 'Orbital motion', source_pdf_name: 'repeat.pdf',
    created_at: '2026-09-20T00:00:00Z', updated_at: '2026-09-20T00:00:00Z',
    content_revision: {
      id: 'revision-1', revision_no: 1, status: 'ready', is_active: true, page_count: 2,
      reviewed_at: null, published_at: null, error_code: null, error_message: null,
    },
    index_revision: {
      id: 'index-1', revision_no: 1, status: 'ready', is_active: true, chunk_count: 2,
      embedded_count: 2, embedding_model: 'gemini-embedding-001', embedding_space_revision: 'v1',
      error_code: null, error_message: null,
    },
    index_job: null, can_review_publish: true, can_unpublish: false, can_retry_index: false,
    can_rebuild_from_pages: true, requires_pdf_reupload: false,
  }
  const reserved = pendingJob({ id: 'revision-job', job_kind: 'knowledge_only', status: 'awaiting_upload', stage: 'awaiting_upload', duplicate_candidate: null, choice_expires_at: null })
  const unchanged = pendingJob({
    id: 'revision-job', job_kind: 'knowledge_only', status: 'completed', stage: 'completed',
    document_id: document.id, knowledge_content_revision_id: 'revision-1',
    knowledge_capture_status: 'unchanged', knowledge_upload_outcome: 'no_changes',
    duplicate_candidate: null, choice_expires_at: null, can_cancel: false,
  })
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') return { json: generationLimits }
      if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') return { json: { jobs: [] } }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/knowledge/documents') return { json: { documents: [document] } }
      if (call.method === 'POST' && call.path === '/flashcards/knowledge-jobs') return { json: reserved }
      if (call.method === 'PUT' && call.path === '/flashcards/knowledge-jobs/revision-job/source') return { json: unchanged }
      return undefined
    },
  })
  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Upload new revision' }).click()
  await page.locator('#knowledge-pdf').setInputFiles({
    name: 'repeat.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n'),
  })
  await page.getByRole('button', { name: 'Upload to Knowledge' }).click()
  await expect(page.getByText('No changes detected. The existing Knowledge revision is unchanged.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Review matching Knowledge' })).toHaveCount(0)
  expect(api.count('PUT', '/flashcards/knowledge-jobs/revision-job/source')).toBe(1)
  expect(api.count('POST', '/flashcards/generation-jobs/revision-job/knowledge-choice')).toBe(0)
})
