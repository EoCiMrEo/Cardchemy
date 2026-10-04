import { expect, test, type Page } from '@playwright/test'

import { fixtures, installMockApi, type MockResponse } from './support/mockApi'
import { expectNoSeriousOrCriticalViolations } from './support/a11y'
import type { RagAnswerJob } from '../src/services/types'

const originalPath = '/subjects/subject-1/rag/threads/thread-1/answer-jobs/job-1/related-excerpts/1/original-pdf'
const pagePath = originalPath.replace('/original-pdf', '/page')
const firstReferenceName = 'Read lecture page 1 — Reference 1 — Lecture 1'
const thread = { id: 'thread-1', subject_id: 'subject-1', created_at: '2026-09-19T12:00:00Z', updated_at: '2026-09-19T12:00:00Z' }

// A small, deterministic two-page PDF exercises the real worker, canvas and text layer.
function lecturePdf(padded = false, denseText = false): Buffer {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 360 220] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 360 220] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ...[1, 2].map((number) => {
      const sentence = `BT /F1 18 Tf 20 150 Td (PDF lecture page ${number}.) Tj ET`
      const text = denseText ? Array(1200).fill(sentence).join('\n') : sentence
      return `<< /Length ${text.length} >>\nstream\n${text}\nendstream`
    }),
  ]
  let data = '%PDF-1.4\n'
  const offsets = [0]
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(data))
    data += `${index + 1} 0 obj\n${object}\nendobj\n`
  })
  if (padded) data += '% padding to exercise PDF.js byte-range reads\n'.repeat(20_000)
  const xref = Buffer.byteLength(data)
  data += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
  data += offsets.slice(1).map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')
  data += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(data)
}

const job: RagAnswerJob = {
  id: 'job-1', thread_id: thread.id, subject_id: thread.subject_id, question_message_id: 'question-1', answer_message_id: null,
  ask_policy: 'related_knowledge_navigation_v3', result_kind: 'related_knowledge', search_mode: 'lexical_fallback', status: 'completed',
  embedding_provider: 'gemini', embedding_model: 'gemini-embedding-001',
  source_judge_provider: null, source_judge_model: null,
  ai_provider: '', ai_model: '', retrieval_policy: 'hybrid_exact_v1', attempt_count: 1, manual_retry_count: 0, max_attempts: 3,
  estimated_input_tokens: 200, estimated_output_tokens: 0, actual_input_tokens: null, actual_output_tokens: null,
  provider_request_count: 1, provider_retry_count: 0, provider_rate_limit_wait_milliseconds: 0,
  estimated_cost_microusd: 2, actual_cost_microusd: null, estimated_additional_cost_microusd: 2,
  previous_attempt_cost_microusd: null, usage_estimated: false, support_rejection_count: 0,
  related_excerpts: [1, 2, 3].map((number) => ({ excerpt_order: number, document_title: `Lecture ${number}`, page_number: 1, section: null, source_quote: `Related source ${number}.` })),
  error_code: null, error_message: null, failure_kind: null, cancellation_requested_at: null,
  created_at: thread.created_at, completed_at: thread.created_at, updated_at: thread.updated_at, can_cancel: false, can_retry: false,
}

async function setup(page: Page, options: { unavailable?: boolean; malformed?: boolean; delayMs?: number; revokeOnNext?: boolean;
  failNextMetadata?: boolean; failNextPageRead?: boolean; unavailableOnNext?: boolean;
  padded?: boolean; denseText?: boolean } = {}) {
  const pdf = options.malformed ? Buffer.from('%PDF-1.4\ninvalid') : lecturePdf(options.padded, options.denseText)
  let headReads = 0
  let pageReads = 0
  let revoked = false
  const api = await installMockApi(page, { auth: 'student', resolver: (call): MockResponse | undefined => {
    if (call.path === '/subjects/subject-1') return { json: fixtures.subject }
    if (call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
    if (call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
    if (call.path === '/subjects/subject-1/rag/threads') return { json: { threads: [thread] } }
    if (call.path === '/subjects/subject-1/rag/threads/thread-1') return { json: { thread, messages: [{
      id: 'question-1', role: 'user', outcome: null, abstention_kind: null, content: 'Where should I read?', hidden: false,
      sources: [], created_at: thread.created_at, expires_at: '2026-12-18T12:00:00Z',
    }] } }
    if (call.path.endsWith('/answer-jobs')) return { json: { jobs: [revoked ? { ...job, related_excerpts: [] } : job] } }
    if (call.path === pagePath) {
      pageReads += 1
      if (revoked) return { status: 404, json: { detail: 'Unavailable' } }
      if (options.failNextPageRead && pageReads > 1) return { status: 503, json: { detail: 'Temporary outage' } }
      return { json: { document_title: 'Lecture 1', page_number: 1, section: null, source_quote: 'Related source 1.',
        page_content: 'Related source 1. Read the full lecture.', reference_start: 0, reference_end: 17 } }
    }
    if (call.path === originalPath) {
      if (call.method === 'HEAD') {
        headReads += 1
        if (options.revokeOnNext && headReads > 1) revoked = true
        if (options.unavailable || revoked) return { status: 404, body: '' }
        if (headReads > 1 && options.failNextMetadata) return { status: 503, body: '' }
        if (headReads > 1 && options.unavailableOnNext) return { status: 404, body: '' }
        return { body: '', contentType: 'application/pdf', headers: {
          'content-length': String(pdf.byteLength), 'accept-ranges': 'bytes', 'x-pdf-page-count': '2', 'cache-control': 'no-store',
        } }
      }
      const match = call.headers.range?.match(/^bytes=(\d+)-(\d+)$/)
      if (!match) return { status: 400, json: { detail: 'Range required' } }
      const begin = Number(match[1]); const end = Number(match[2]) + 1
      return { status: 206, body: pdf.subarray(begin, end), contentType: 'application/pdf', delayMs: options.delayMs,
        headers: { 'content-range': `bytes ${begin}-${end - 1}/${pdf.byteLength}`, 'cache-control': 'no-store' } }
    }
    return undefined
  } })
  await page.goto('/subjects/subject-1')
  return api
}

test('three unverified references open a real PDF through authenticated ranges and reauthorize navigation', async ({ page }) => {
  const api = await setup(page)
  const workerUrls: string[] = []
  const streamErrors: string[] = []
  page.on('worker', (worker) => workerUrls.push(worker.url()))
  page.on('console', (message) => {
    if (message.type() === 'error' && message.text().includes('ReadableStreamDefaultController')) {
      streamErrors.push(message.text())
    }
  })
  page.on('pageerror', (error) => {
    if (error.message.includes('ReadableStreamDefaultController')) streamErrors.push(error.message)
  })
  // The dev server needs its inline React preamble during bootstrap. Apply the shipped
  // policy before loading the optional PDF module to exercise its same-origin worker.
  await page.evaluate(() => {
    const policy = document.createElement('meta')
    policy.httpEquiv = 'Content-Security-Policy'
    policy.content = "default-src 'self'; object-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'"
    document.head.append(policy)
  })
  await expect(page.getByText('Reference 3', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: firstReferenceName })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Read lecture page 1 — Reference 2 — Lecture 2' })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Read lecture page 1 — Reference 3 — Lecture 3' })).toHaveCount(1)
  await expect(page.getByText(/embedding service was unavailable/)).toBeVisible()
  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  // Five Chromium workers can decode the on-demand PDF worker concurrently.
  // Give the real renderer time to become ready without weakening later assertions.
  await expect(dialog.getByRole('button', { name: 'Next PDF page' })).toBeEnabled({ timeout: 15_000 })
  await expect(dialog.locator('canvas')).toHaveCount(1)
  expect(workerUrls.some((url) => new URL(url).searchParams.get('mime') === 'js-v1')).toBe(true)
  await expect(dialog.locator('.lecture-pdf-text-layer')).toContainText('PDF lecture page 1.')
  await dialog.getByText('Readable text from this PDF page', { exact: true }).click()
  await expect(dialog.getByText('PDF lecture page 1.', { exact: true }).last()).toBeVisible()
  await dialog.getByRole('button', { name: 'Next PDF page' }).focus()
  await page.keyboard.press('Enter')
  await expect(dialog.getByText('PDF page 2 of 2', { exact: true })).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'Extracted text for cited page 1' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Previous PDF page' })).toBeEnabled()
  expect(api.callsFor('HEAD', originalPath)).toHaveLength(2)
  for (const request of api.callsFor('GET', originalPath)) {
    expect(request.headers.authorization).toBe('Bearer boot-access-token')
    expect(request.headers.range).toMatch(/^bytes=\d+-\d+$/)
  }
  await expectNoSeriousOrCriticalViolations(page)
  expect(streamErrors).toEqual([])
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('button', { name: firstReferenceName })).toBeFocused()
})

test('a PDF with a distant cross-reference table loads through multiple authenticated ranges', async ({ page }) => {
  const api = await setup(page, { padded: true })
  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await expect(dialog.locator('.lecture-pdf-text-layer')).toContainText('PDF lecture page 1.', { timeout: 15_000 })
  const reads = api.callsFor('GET', originalPath)
  expect(reads.length).toBeGreaterThan(1)
  for (const read of reads) {
    expect(read.headers.authorization).toBe('Bearer boot-access-token')
    expect(read.headers.range).toMatch(/^bytes=\d+-\d+$/)
  }
})

test('missing and malformed originals show safe extracted text fallback', async ({ page }) => {
  await setup(page, { unavailable: true })
  await page.setViewportSize({ width: 360, height: 780 })
  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await expect(dialog.getByText('The original PDF is unavailable. Read the extracted page text below.')).toBeVisible()
  await expect(dialog).toContainText('Read the full lecture.')
  await expectNoSeriousOrCriticalViolations(page)
  expect(await page.evaluate(() => document.body.scrollWidth <= innerWidth)).toBe(true)
})

test('malformed PDF does not replace the extracted text with raw parser errors', async ({ page }) => {
  await setup(page, { malformed: true })
  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await expect(dialog.getByRole('alert')).toHaveText('The original PDF could not be displayed. Read the extracted page text below.', { timeout: 15_000 })
  await expect(dialog).toContainText('Read the full lecture.')
  await expect(dialog.getByText(/InvalidPDFException|Invalid PDF structure/)).toHaveCount(0)
})

test('revoked navigation clears the PDF and stale references', async ({ page }) => {
  await setup(page, { revokeOnNext: true })
  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await dialog.getByRole('button', { name: 'Next PDF page' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('region', { name: 'Related published Knowledge' })).toHaveCount(0)
  await expect(page.locator('canvas')).toHaveCount(0)
})

for (const mode of ['metadata', 'page', 'missing-original'] as const) {
  test(`${mode} failure during navigation keeps authorized extracted text`, async ({ page }) => {
    await setup(page, { failNextMetadata: mode === 'metadata', failNextPageRead: mode === 'page',
      unavailableOnNext: mode === 'missing-original' })
    await page.getByRole('button', { name: 'Read lecture page 1' }).first().click()
    const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
    await expect(dialog.getByRole('button', { name: 'Next PDF page' })).toBeEnabled({ timeout: 15_000 })
    await dialog.getByRole('button', { name: 'Next PDF page' }).click()
    await expect(dialog.getByText(mode === 'missing-original'
      ? 'The original PDF is unavailable. Read the extracted page text below.'
      : 'The original PDF could not be displayed. Read the extracted page text below.')).toBeVisible()
    await expect(dialog).toContainText('Read the full lecture.')
    await expect(dialog.locator('canvas')).toHaveCount(0)
  })
}

test('closing an in-flight PDF request cannot reopen the dialog or retain a canvas', async ({ page }) => {
  const api = await setup(page, { delayMs: 700 })
  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await expect.poll(() => api.callsFor('GET', originalPath).length).toBe(1)
  await expect(dialog.getByText('Loading the original lecture PDF…')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await page.waitForTimeout(800)
  await expect(dialog).not.toBeVisible()
  await expect(page.locator('canvas')).toHaveCount(0)
  expect(api.callsFor('GET', originalPath)).toHaveLength(1)
})

test('closing while dense PDF text is rendering leaves no stream controller error', async ({ page }) => {
  await page.addInitScript(() => {
    const originalRead = ReadableStreamDefaultReader.prototype.read
    const originalCancel = ReadableStreamDefaultReader.prototype.cancel
    const textReaders = new WeakSet<ReadableStreamDefaultReader<unknown>>()
    ReadableStreamDefaultReader.prototype.read = function (this: ReadableStreamDefaultReader<unknown>) {
      return originalRead.call(this).then((result) => {
        const value = result.value as { items?: unknown; styles?: unknown } | undefined
        if (!result.done && value && Array.isArray(value.items) && value.items.length > 0
          && value.styles && typeof value.styles === 'object'
          && !document.documentElement.dataset.pdfTextChunkObserved) {
          textReaders.add(this)
          document.documentElement.dataset.pdfTextChunkObserved = 'true'
          const dialog = document.querySelector<HTMLElement>('[role="dialog"]')
          const close = Array.from(dialog?.querySelectorAll<HTMLButtonElement>('button') ?? [])
            .find((button) => button.textContent?.trim() === 'Close')
          close?.click()
        }
        return result
      })
    }
    ReadableStreamDefaultReader.prototype.cancel = function (this: ReadableStreamDefaultReader<unknown>, reason?: unknown) {
      if (textReaders.has(this)) {
        document.documentElement.dataset.pdfTextCancelReason = reason instanceof Error ? reason.message : 'invalid'
      }
      return originalCancel.call(this, reason)
    }
  })
  await setup(page, { denseText: true })
  const streamErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && message.text().includes('ReadableStreamDefaultController')) {
      streamErrors.push(message.text())
    }
  })
  page.on('pageerror', (error) => streamErrors.push(error.message))
  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.pdfTextChunkObserved),
    { timeout: 15_000 }).toBe('true')
  await expect(dialog).not.toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.pdfTextCancelReason)).toBe('pdf_viewer_closed')
  await page.waitForTimeout(500)
  expect(streamErrors).toEqual([])
})

test('Next, close and reopen while PDF text is streaming keeps the new page intact', async ({ page }) => {
  test.setTimeout(60_000)
  await page.addInitScript(() => {
    const originalRead = ReadableStreamDefaultReader.prototype.read
    const originalCancel = ReadableStreamDefaultReader.prototype.cancel
    const secondPageReaders = new WeakSet<ReadableStreamDefaultReader<unknown>>()
    ReadableStreamDefaultReader.prototype.read = function (this: ReadableStreamDefaultReader<unknown>) {
      return originalRead.call(this).then((result) => {
        const value = result.value as { items?: Array<{ str?: string }> } | undefined
        if (result.done || document.documentElement.dataset.pdfSecondChunkObserved
          || !value?.items?.some((item) => item.str?.includes('PDF lecture page 2.'))) return result
        secondPageReaders.add(this)
        document.documentElement.dataset.pdfSecondChunkObserved = 'true'
        // Keep the real PDF.js text read pending until the old viewer has closed
        // and a fresh viewer has rendered. No wall-clock delay controls the race.
        return new Promise<typeof result>((resolve) => {
          window.addEventListener('release-pdf-second-text-read', () => {
            document.documentElement.dataset.pdfSecondReadReleased = 'true'
            resolve(result)
          }, { once: true })
        })
      })
    }
    ReadableStreamDefaultReader.prototype.cancel = function (this: ReadableStreamDefaultReader<unknown>, reason?: unknown) {
      if (secondPageReaders.has(this)) {
        document.documentElement.dataset.pdfSecondCancelReason = reason instanceof Error ? reason.message : 'invalid'
      }
      return originalCancel.call(this, reason)
    }
  })
  await setup(page, { denseText: true })
  const streamErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && message.text().includes('ReadableStreamDefaultController')) {
      streamErrors.push(message.text())
    }
  })
  page.on('pageerror', (error) => streamErrors.push(error.message))

  await page.getByRole('button', { name: firstReferenceName }).click()
  const dialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await expect(dialog.locator('.lecture-pdf-text-layer')).toContainText('PDF lecture page 1.', { timeout: 15_000 })
  await dialog.getByRole('button', { name: 'Next PDF page' }).click()
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.pdfSecondChunkObserved),
    { timeout: 15_000 }).toBe('true')
  await expect(dialog.getByText('PDF page 2 of 2', { exact: true })).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.pdfSecondCancelReason)).toBe('pdf_viewer_closed')
  await page.getByRole('button', { name: firstReferenceName }).click()
  await expect(dialog.locator('.lecture-pdf-text-layer')).toContainText('PDF lecture page 1.', { timeout: 15_000 })
  await page.evaluate(() => window.dispatchEvent(new Event('release-pdf-second-text-read')))
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.pdfSecondReadReleased)).toBe('true')
  await expect(dialog.getByText('PDF page 1 of 2', { exact: true })).toBeVisible()
  await expect(dialog.locator('.lecture-pdf-text-layer')).not.toContainText('PDF lecture page 2.')
  await expect(dialog.locator('canvas')).toHaveCount(1)
  await expect(dialog.getByText('The original PDF could not be displayed. Read the extracted page text below.')).toHaveCount(0)
  await page.waitForTimeout(500)
  expect(streamErrors).toEqual([])
})
