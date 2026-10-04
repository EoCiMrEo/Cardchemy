import { expect, test } from '@playwright/test'

import { expectNoSeriousOrCriticalViolations } from './support/a11y'
import { generationLimits, generationResponse } from './support/generation'
import { fixtures, installMockApi } from './support/mockApi'
import type { KnowledgeDocument } from '../src/services/types'

const attachmentPath = '/subjects/subject-1/knowledge/documents/document-1/attach-original-pdf'

function readyDocument(): KnowledgeDocument {
  return {
    id: 'document-1', subject_id: 'subject-1', title: 'Lecture 05', source_pdf_name: 'lecture.pdf',
    created_at: '2026-09-20T00:00:00Z', updated_at: '2026-09-20T00:00:00Z',
    content_revision: {
      id: 'revision-1', revision_no: 1, status: 'ready', is_active: true, page_count: 2,
      reviewed_at: '2026-09-20T00:05:00Z', published_at: '2026-09-20T00:05:00Z',
      error_code: null, error_message: null,
    },
    index_revision: {
      id: 'index-1', revision_no: 1, status: 'ready', is_active: true, chunk_count: 2,
      embedded_count: 2, embedding_model: 'gemini-embedding-001', embedding_space_revision: 'v1',
      error_code: null, error_message: null,
    },
    index_job: null, can_review_publish: false, can_unpublish: true, can_retry_index: false,
    can_rebuild_from_pages: true, requires_pdf_reupload: false,
  }
}

test('instructor attaches the exact original to a ready revision without creating a new job', async ({ page }) => {
  const document = readyDocument()
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/knowledge/documents') return { json: { documents: [document] } }
      if (call.method === 'POST' && call.path === attachmentPath) {
        if (callNumber === 1) return { status: 409, json: { detail: { code: 'knowledge_pdf_revision_mismatch', message: 'Original PDF does not match this Knowledge revision.' } } }
        return { json: document }
      }
      return generationResponse(call)
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByRole('heading', { name: 'Subject Knowledge' })).toBeVisible()
  await page.getByRole('button', { name: 'Attach exact original PDF' }).click()
  await expect(page.getByText(/exact PDF used for this active Knowledge revision/)).toBeVisible()
  await expect(page.getByText(/without a new revision, indexing, or AI call/)).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)

  await page.getByLabel('Exact original PDF file').setInputFiles({
    name: 'lecture-original.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\noriginal lecture\n'),
  })
  await page.getByRole('button', { name: 'Attach to current revision' }).click()
  await expect(page.getByRole('alert')).toContainText('Original PDF does not match this Knowledge revision.')
  await expect(page.getByRole('button', { name: 'Attach to current revision' })).toBeEnabled()
  await page.getByRole('button', { name: 'Attach to current revision' }).click()
  await expect(page.getByRole('status')).toContainText('The original PDF is attached to this Knowledge revision.')

  const calls = api.callsFor('POST', attachmentPath)
  expect(calls).toHaveLength(2)
  expect(calls.map((call) => call.body)).toEqual(['%PDF-1.4\noriginal lecture\n', '%PDF-1.4\noriginal lecture\n'])
  expect(calls.every((call) => call.headers['content-type'] === 'application/pdf')).toBe(true)
  expect(api.count('POST', '/flashcards/knowledge-jobs')).toBe(0)
  expect(api.count('PUT', '/flashcards/knowledge-jobs/document-1/source')).toBe(0)
  expect(api.count('POST', '/subjects/subject-1/knowledge/documents/document-1/retry-index')).toBe(0)
})

test('oversized attachment is stopped before upload; unavailable revisions have no attach action', async ({ page }) => {
  let document = readyDocument()
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/knowledge/documents') return { json: { documents: [document] } }
      if (call.method === 'GET' && call.path === '/flashcards/generation-limits') {
        return { json: { ...generationLimits, max_upload_bytes: 1024 } }
      }
      return generationResponse(call)
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByRole('heading', { name: 'Subject Knowledge' })).toBeVisible()
  await page.getByRole('button', { name: 'Attach exact original PDF' }).click()
  await expect(page.getByText('Maximum file size: 1,024 bytes.')).toBeVisible()
  await page.getByLabel('Exact original PDF file').setInputFiles({
    name: 'too-large.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(1025, 65),
  })
  await page.getByRole('button', { name: 'Attach to current revision' }).click()
  await expect(page.getByRole('alert')).toContainText('1,024-byte upload limit')
  expect(api.count('POST', attachmentPath)).toBe(0)

  document = {
    ...document,
    content_revision: { ...document.content_revision!, status: 'processing' },
  }
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Subject Knowledge' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Attach exact original PDF' })).toHaveCount(0)
})
