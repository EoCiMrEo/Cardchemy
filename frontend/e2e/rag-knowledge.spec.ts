import { expect, test } from '@playwright/test'

import { expectNoSeriousOrCriticalViolations } from './support/a11y'
import { fixtures, installMockApi } from './support/mockApi'
import { generationResponse } from './support/generation'
import type { KnowledgeDocument, RagAnswerJob, RagHistory, RagThread } from '../src/services/types'

const thread: RagThread = {
  id: 'thread-1',
  subject_id: 'subject-1',
  created_at: '2026-09-19T12:00:00Z',
  updated_at: '2026-09-19T12:00:00Z',
}

const answerJob = (status: RagAnswerJob['status'], overrides: Partial<RagAnswerJob> = {}): RagAnswerJob => ({
  id: 'answer-job-1', thread_id: thread.id, subject_id: thread.subject_id,
  question_message_id: 'question-1', answer_message_id: null,
  ask_policy: 'related_knowledge_navigation_v8', result_kind: status === 'completed' ? 'no_match' : null,
  status, embedding_provider: 'gemini', embedding_model: 'gemini-embedding-001',
  source_judge_provider: 'gemini', source_judge_model: 'example-source-judge',
  ai_provider: null, ai_model: null, retrieval_policy: 'hybrid_exact_v1',
  search_mode: status === 'completed' ? 'hybrid' : 'not_searched',
  attempt_count: status === 'queued' ? 0 : 1, manual_retry_count: 0, max_attempts: 3,
  estimated_input_tokens: 200, estimated_output_tokens: 0,
  actual_input_tokens: status === 'completed' ? 150 : null,
  actual_output_tokens: null,
  provider_request_count: status === 'completed' ? 1 : 0, provider_retry_count: 0,
  provider_rate_limit_wait_milliseconds: 0, estimated_cost_microusd: 2,
  actual_cost_microusd: status === 'completed' ? 1 : null, usage_estimated: false,
  estimated_additional_cost_microusd: 2,
  previous_attempt_cost_microusd: status === 'completed' ? 1 : null,
  support_rejection_count: 0, related_excerpts: [], error_code: null, error_message: null, failure_kind: null,
  cancellation_requested_at: null, created_at: '2026-09-19T12:00:00Z',
  completed_at: status === 'completed' ? '2026-09-19T12:00:02Z' : null,
  updated_at: '2026-09-19T12:00:02Z', can_cancel: status === 'queued' || status === 'running',
  can_retry: status === 'failed' || status === 'cancelled', ...overrides,
})

const history = (withFollowUp = false): RagHistory => ({
  thread,
  messages: [
    {
      id: 'question-0', role: 'user', outcome: null, abstention_kind: null, content: 'What is perihelion?', hidden: false,
      sources: [], created_at: '2026-09-19T12:00:00Z', expires_at: '2026-12-18T12:00:00Z',
    },
    {
      id: 'answer-0', role: 'assistant', outcome: 'answer', abstention_kind: null,
      content: 'Perihelion is nearest the Sun. <script>alert("unsafe")</script>', hidden: false,
      sources: [{
        citation_order: 1, chunk_id: 'chunk-1', document_id: 'document-1',
        document_title: 'Lecture 05', content_revision_id: 'content-1', index_revision_id: 'index-1',
        page_number: 17, section: 'Orbital motion', claim_text: 'Perihelion is nearest the Sun.',
        source_quote: 'Perihelion is the point in an orbit nearest the Sun.',
      }],
      created_at: '2026-09-19T12:00:02Z', expires_at: '2026-12-18T12:00:02Z',
    },
    ...(withFollowUp ? [{
      id: 'question-1', role: 'user' as const, outcome: null, abstention_kind: null, content: 'What is aphelion?', hidden: false,
      sources: [], created_at: '2026-09-19T12:01:00Z', expires_at: '2026-12-18T12:01:00Z',
    }] : []),
  ],
})

test('instructor Knowledge remains independent from flashcard generation and requires publication', async ({ page }, testInfo) => {
  let published = false
  const document = (): KnowledgeDocument => ({
    id: 'document-1', subject_id: 'subject-1', title: 'Lecture 05', source_pdf_name: 'lecture-05.pdf',
    created_at: '2026-09-19T12:00:00Z', updated_at: '2026-09-19T12:00:02Z',
    content_revision: {
      id: 'content-1', revision_no: 1, status: 'ready', is_active: true, page_count: 18,
      reviewed_at: published ? '2026-09-19T12:05:00Z' : null,
      published_at: published ? '2026-09-19T12:05:00Z' : null,
      error_code: null, error_message: null,
    },
    index_revision: {
      id: 'index-1', revision_no: 1, status: 'ready', is_active: true, chunk_count: 24,
      embedded_count: 24, embedding_model: 'offline', embedding_space_revision: 'v1',
      error_code: null, error_message: null,
    },
    index_job: {
      id: 'index-job-1', status: 'completed', attempt_count: 1, max_attempts: 3,
      error_code: null, error_message: null, created_at: '2026-09-19T12:00:00Z',
      completed_at: '2026-09-19T12:00:02Z',
    },
    can_review_publish: !published, can_unpublish: published, can_retry_index: false,
    can_rebuild_from_pages: true, requires_pdf_reupload: false,
  })
  await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/knowledge/documents') return { json: { documents: [document()] } }
      if (call.method === 'POST' && call.path.endsWith('/review-publish')) {
        published = true
        return { json: document() }
      }
      return generationResponse(call)
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByRole('button', { name: 'Generate Flashcard Set' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('heading', { name: 'Subject Knowledge' })).toBeVisible()
  await expect(page.getByText('Awaiting instructor review')).toBeVisible()
  await expect(page.getByText('Private', { exact: true })).toBeVisible()
  await expect(page.getByText(/Before upload: extracted page text.*sent to Google Gemini API \(gemini-embedding-001\)/)).toBeVisible()
  await page.getByRole('button', { name: 'Review & publish' }).click()
  await expect(page.getByText('Published for enrolled students')).toBeVisible()
  await expect(page.getByText(/indexing retry rebuilds from persisted extracted pages/i).first()).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)
  if (process.env.RAG_UI_CAPTURE === '1') {
    await page.screenshot({ path: testInfo.outputPath('phase18-instructor-knowledge.png'), fullPage: true })
  }
})

test('Ask AI hides historical generated answers and retries one source search safely', async ({ page }, testInfo) => {
  let accepted = false
  let jobPollsAfterAccept = 0
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call, callNumber) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/threads') return { json: { threads: [thread] } }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}`) return { json: history(accepted) }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) {
        if (!accepted) return { json: { jobs: [answerJob('completed', {
          ask_policy: 'two_request_local_support_v1', answer_message_id: 'answer-0', result_kind: null,
        })] } }
        jobPollsAfterAccept += 1
        return { json: { jobs: [answerJob(jobPollsAfterAccept >= 2 ? 'completed' : 'queued', {
          ask_policy: 'related_knowledge_navigation_v8', result_kind: jobPollsAfterAccept >= 2 ? 'no_match' : null,
          answer_message_id: null,
        })] } }
      }
      if (call.method === 'POST' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) {
        if (callNumber === 1) return { status: 503, json: { detail: 'Knowledge search temporarily unavailable' } }
        accepted = true
        return { status: 202, json: answerJob('queued', { ask_policy: 'related_knowledge_navigation_v8' }) }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByText('What is perihelion?')).toBeVisible()
  await expect(page.getByText('<script>alert("unsafe")</script>', { exact: false })).toHaveCount(0)
  await expect(page.locator('article script')).toHaveCount(0)
  await expect(page.getByText(/bounded selected page text and full-page PNG images.*example-source-judge.*unverified reading suggestions/)).toBeVisible()
  await expect(page.getByText(/at most 160 characters from the immediately preceding user question/)).toBeVisible()
  await expect(page.getByRole('dialog', { name: 'Authorized evidence' })).toHaveCount(0)

  await page.getByRole('textbox', { name: 'Question' }).fill('What is aphelion?')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Knowledge search temporarily unavailable')
  await page.getByRole('button', { name: 'Retry question safely' }).click()
  await expect.poll(() => api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`).length).toBe(2)
  const submissions = api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`)
  expect(submissions).toHaveLength(2)
  expect(submissions[0].body).toEqual({ question: 'What is aphelion?', document_ids: [] })
  expect(submissions[0].headers['idempotency-key']).toBe(submissions[1].headers['idempotency-key'])
  await expect(page.getByText('Question queued')).toBeVisible()
  await expect(page.getByRole('status')).toContainText(
    'No related reference was found for this question. Try a more specific question or open the published lecture.',
    { timeout: 6_000 },
  )
  await expectNoSeriousOrCriticalViolations(page)
  if (process.env.RAG_UI_CAPTURE === '1') {
    await page.screenshot({ path: testInfo.outputPath('phase18-student-ask-ai.png'), fullPage: true })
  }

  await page.setViewportSize({ width: 360, height: 780 })
  const widths = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: window.innerWidth }))
  expect(widths.body).toBeLessThanOrEqual(widths.viewport)
})

test('Ask AI renders durable source-search running, failed and cancelled states without old answer text', async ({ page }) => {
  const stateThreads: RagThread[] = ['running', 'failed', 'cancelled'].map((state, index) => ({
    id: `thread-${state}`,
    subject_id: 'subject-1',
    created_at: `2026-09-19T12:0${index}:00Z`,
    updated_at: `2026-09-19T12:0${index}:00Z`,
  }))
  const stateFor = (threadId: string): RagAnswerJob['status'] =>
    threadId.endsWith('running') ? 'running' : threadId.endsWith('failed') ? 'failed' : 'cancelled'

  await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/threads') {
        return { json: { threads: stateThreads } }
      }
      const match = call.path.match(/^\/subjects\/subject-1\/rag\/threads\/([^/]+)(?:\/(answer-jobs))?$/)
      if (call.method === 'GET' && match) {
        const selected = stateThreads.find((item) => item.id === match[1])!
        if (match[2]) {
          const jobState = stateFor(selected.id)
          return {
            json: {
              jobs: [answerJob(jobState, {
                id: `job-${jobState}`,
                thread_id: selected.id,
                error_code: jobState === 'failed' ? 'rag_answer_failed' : null,
                failure_kind: jobState === 'failed' ? 'provider_temporarily_unavailable' : null,
                error_message: jobState === 'failed'
                  ? 'Answer generation failed.'
                  : null,
              })],
            },
          }
        }
        return {
          json: {
            thread: selected,
            messages: selected.id.endsWith('running') ? [
              {
                id: 'abstained-answer', role: 'assistant', outcome: 'abstained', abstention_kind: 'support_rejected',
                content: 'I do not have enough supported course evidence to answer that.',
                hidden: false, sources: [], created_at: '2026-09-19T12:00:00Z',
                expires_at: '2026-12-18T12:00:00Z',
              },
              {
                id: 'hidden-answer', role: 'assistant', outcome: 'answer',
                content: 'Previously grounded text must not remain visible.',
                hidden: true, sources: [], created_at: '2026-09-19T12:00:01Z',
                expires_at: '2026-12-18T12:00:01Z',
              },
            ] : [],
          },
        }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByText('Checking related published Knowledge pages')).toBeVisible()
  await expect(page.getByText('I could not verify an answer against the published course material.')).toHaveCount(0)
  await expect(page.getByText('This message is unavailable because its source access or revision is no longer current.')).toHaveCount(0)
  await expect(page.getByText('Previously grounded text must not remain visible.')).toHaveCount(0)

  await page.locator('#rag-thread').selectOption('thread-failed')
  await expect(page.getByText('Source-search provider temporarily unavailable')).toBeVisible()
  await expect(page.getByText('The Knowledge search could not be completed safely. Retrying starts a new attempt and may incur cost.')).toBeVisible()
  await expect(page.getByText('Answer generation failed.')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Retry search' })).toBeVisible()

  await page.locator('#rag-thread').selectOption('thread-cancelled')
  await expect(page.getByText('Knowledge search cancelled')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry search' })).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)
})

test('Ask AI shows exact source text and opens its current extracted lecture page on mobile', async ({ page }) => {
  const relatedQuote = 'A nearby course passage. <script>alert("unsafe")</script>'
  const relatedHistory: RagHistory = {
    thread,
    messages: [
      { id: 'question-1', role: 'user', outcome: null, abstention_kind: null,
        content: 'What does the lecture explain?', hidden: false, sources: [],
        created_at: '2026-09-19T12:01:00Z', expires_at: '2026-12-18T12:01:00Z' },
      { id: 'answer-related', role: 'assistant', outcome: 'answer', abstention_kind: null,
        content: 'A generated sentence must not appear in source-only mode.',
        hidden: false, sources: [], created_at: '2026-09-19T12:01:02Z',
        expires_at: '2026-12-18T12:01:02Z' },
    ],
  }
  await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/threads') return { json: { threads: [thread] } }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}`) return { json: relatedHistory }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) {
        return { json: { jobs: [answerJob('completed', {
          result_kind: 'related_knowledge', answer_message_id: null, related_excerpts: [{
            excerpt_order: 1, document_title: 'Lecture 05', page_number: 17, section: 'Orbital motion', source_quote: relatedQuote,
          }],
        })] } }
      }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs/answer-job-1/related-excerpts/1/page`) {
        const pageContent = `Before. ${relatedQuote} After.`
        const start = pageContent.indexOf(relatedQuote)
        return { json: {
          document_title: 'Lecture 05', page_number: 17, section: 'Orbital motion',
          source_quote: relatedQuote, page_content: pageContent,
          reference_start: start, reference_end: start + relatedQuote.length,
        } }
      }
      if (call.path.endsWith('/original-pdf')) {
        return { status: 404, json: { detail: 'Original PDF unavailable' } }
      }
      return undefined
    },
  })

  await page.setViewportSize({ width: 360, height: 780 })
  await page.goto('/subjects/subject-1')
  await expect(page.getByText('Related Knowledge found')).toBeVisible()
  const related = page.getByRole('region', { name: 'Related published Knowledge' })
  await expect(related).toContainText('They have not been verified as an answer')
  await expect(related).toContainText('Lecture 05 · p.17 · Orbital motion')
  await expect(related).toContainText(relatedQuote)
  await expect(page.getByText('A generated sentence must not appear in source-only mode.')).toHaveCount(0)
  await expect(page.locator('article script')).toHaveCount(0)
  await related.getByRole('button', { name: 'Read lecture page 17 — Reference 1 — Lecture 05' }).click()
  const pageDialog = page.getByRole('dialog', { name: 'Published Knowledge page' })
  await expect(pageDialog).toContainText('Read the original lecture at the referenced page')
  await expect(pageDialog).toContainText('The original PDF is unavailable')
  await expect(pageDialog.locator('mark')).toHaveText(relatedQuote)
  await expect(pageDialog).toContainText('Before.')
  await expect(pageDialog).toContainText('After.')
  const widths = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: window.innerWidth }))
  expect(widths.body).toBeLessThanOrEqual(widths.viewport)
  await expectNoSeriousOrCriticalViolations(page)
})

test('paused Ask AI keeps questions visible and prevents new work without showing old answers', async ({ page }) => {
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/profile') {
        return { json: {
          rag_enabled: true, ask_enabled: false, ask_policy: 'related_knowledge_navigation_v3', ask_available: false, answer_available: false,
          answer_provider: 'gemini', answer_model: 'gemini-3.5-flash',
          embedding_available: true, embedding_provider: 'gemini',
          embedding_model: 'gemini-embedding-001',
          active_embedding_provider: 'gemini', active_embedding_model: 'gemini-embedding-001',
          active_embedding_space_matches: true,
          source_judge_available: false, source_judge_provider: null, source_judge_model: null,
          source_judge_transfers_published_content: false, chat_retention_days: 90,
          source_judge_thinking_level: null, source_judge_transfers_page_images: false,
          source_judge_contract_version: null,
          source_judge_transfers_literal_subject_context: false,
        } }
      }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/threads') return { json: { threads: [thread] } }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}`) return { json: history() }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) {
        return { json: { jobs: [answerJob('failed', { can_retry: false })] } }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByText(/Knowledge search is paused/)).toBeVisible()
  await expect(page.getByText('What is perihelion?')).toBeVisible()
  await expect(page.getByText(/Perihelion is nearest the Sun/)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'New conversation' })).toBeDisabled()
  await expect(page.getByRole('textbox', { name: 'Question' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Ask', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Retry search' })).toHaveCount(0)
  expect(api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`)).toHaveLength(0)
  await expectNoSeriousOrCriticalViolations(page)
})

test('each manual Ask retry requires cost confirmation and a fresh operation key', async ({ page }) => {
  let retryCount = 0
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/threads') return { json: { threads: [thread] } }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}`) return { json: history() }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) {
        return { json: { jobs: [answerJob('failed', {
          ask_policy: 'related_knowledge_navigation_v8',
          manual_retry_count: retryCount,
          estimated_additional_cost_microusd: retryCount === 0 ? null : 25_000,
          previous_attempt_cost_microusd: retryCount === 0 ? null : 15_000,
        })] } }
      }
      if (call.method === 'POST' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs/answer-job-1/retry`) {
        retryCount += 1
        return { json: answerJob('failed', {
          ask_policy: 'related_knowledge_navigation_v8',
          manual_retry_count: retryCount,
          estimated_additional_cost_microusd: 25_000,
          previous_attempt_cost_microusd: 15_000,
        }) }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Retry search' }).click()
  const dialog = page.getByRole('dialog', { name: 'Start another Knowledge search?' })
  await expect(dialog).toContainText('Estimated additional cost is unavailable.')
  await expect(dialog).toContainText('Previous attempt cost is unknown.')
  await expect(dialog).toContainText('at most 160 characters from the immediately preceding user question')
  await expect(dialog).toContainText('Full earlier questions, chat history, assistant answers and original PDF file bytes are not sent')
  expect(api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs/answer-job-1/retry`)).toHaveLength(0)
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  expect(api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs/answer-job-1/retry`)).toHaveLength(0)

  await page.getByRole('button', { name: 'Retry search' }).click()
  await dialog.getByRole('button', { name: 'Start new search' }).click()
  await expect(dialog).not.toBeVisible()
  await page.getByRole('button', { name: 'Retry search' }).click()
  await expect(dialog).toContainText('Estimated additional cost: $0.03')
  await expect(dialog).toContainText('Previous attempt recorded cost: $0.02')
  await dialog.getByRole('button', { name: 'Start new search' }).click()
  await expect.poll(() => api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs/answer-job-1/retry`).length).toBe(2)
  const attempts = api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs/answer-job-1/retry`)
  expect(attempts).toHaveLength(2)
  expect(attempts[0].headers['idempotency-key']).not.toBe(attempts[1].headers['idempotency-key'])
  await expectNoSeriousOrCriticalViolations(page)
})

test('a changed Ask provider disclosure stops enqueue until the student sees it', async ({ page }) => {
  let profileReads = 0
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/threads') return { json: { threads: [thread] } }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/profile') {
        profileReads += 1
        return { json: {
          rag_enabled: true, ask_enabled: true, ask_policy: 'related_knowledge_navigation_v8', ask_available: true, answer_available: false,
          answer_provider: 'gemini', answer_model: 'gemini-3.5-flash',
          embedding_available: true, embedding_provider: 'gemini',
          embedding_model: profileReads === 1 ? 'gemini-embedding-001' : 'gemini-embedding-2',
          active_embedding_provider: 'gemini', active_embedding_model: profileReads === 1 ? 'gemini-embedding-001' : 'gemini-embedding-2',
          active_embedding_space_matches: true,
          source_judge_available: true, source_judge_provider: 'gemini', source_judge_model: 'example-source-judge',
          source_judge_transfers_published_content: true, chat_retention_days: 90,
          source_judge_thinking_level: 'HIGH', source_judge_transfers_page_images: true,
          source_judge_contract_version: 'visual_source_id_v5',
          source_judge_transfers_literal_subject_context: true,
        } }
      }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}`) return { json: history() }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) return { json: { jobs: [] } }
      if (call.method === 'POST' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) return { status: 202, json: answerJob('queued') }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await page.getByRole('textbox', { name: 'Question' }).fill('What is perihelion?')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('embedding model, or source judge changed')
  await expect(page.getByText(/gemini-embedding-2/)).toBeVisible()
  expect(api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`)).toHaveLength(0)
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect.poll(() => api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`).length).toBe(1)
  await expect(page.getByRole('textbox', { name: 'Question' })).toBeEmpty()
})

test('a changed literal-subject capability blocks a confirmed retry without sending history', async ({ page }) => {
  let profileReads = 0
  const api = await installMockApi(page, {
    auth: 'student',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/subject-1') return { json: fixtures.subject }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/sets') return { json: [fixtures.set] }
      if (call.method === 'GET' && call.path === '/study/sets/set-1/progress') return { json: fixtures.progress }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/profile') {
        profileReads += 1
        return { json: {
          rag_enabled: true, ask_enabled: true, ask_policy: 'related_knowledge_navigation_v8', ask_available: true,
          answer_available: false, answer_provider: null, answer_model: null,
          embedding_available: true, embedding_provider: 'gemini', embedding_model: 'gemini-embedding-001',
          active_embedding_provider: 'gemini', active_embedding_model: 'gemini-embedding-001', active_embedding_space_matches: true,
          source_judge_available: true, source_judge_provider: 'gemini', source_judge_model: 'example-source-judge',
          source_judge_transfers_published_content: true, source_judge_thinking_level: 'HIGH',
          source_judge_transfers_page_images: true, source_judge_contract_version: 'visual_source_id_v5',
          source_judge_transfers_literal_subject_context: profileReads === 1, chat_retention_days: 90,
        } }
      }
      if (call.method === 'GET' && call.path === '/subjects/subject-1/rag/threads') return { json: { threads: [thread] } }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}`) return { json: history() }
      if (call.method === 'GET' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) {
        return { json: { jobs: [answerJob('failed')] } }
      }
      return undefined
    },
  })
  await page.goto('/subjects/subject-1')
  await page.getByRole('button', { name: 'Retry search' }).click()
  const dialog = page.getByRole('dialog', { name: 'Start another Knowledge search?' })
  await expect(dialog).toContainText('at most 160 characters')
  await dialog.getByRole('button', { name: 'Start new search' }).click()
  await expect(page.getByRole('alert')).toContainText('Review the updated disclosure')
  await expect(page.getByRole('textbox', { name: 'Question' })).toBeDisabled()
  expect(api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs/answer-job-1/retry`)).toHaveLength(0)
})
