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
  question_message_id: 'question-1', answer_message_id: status === 'completed' ? 'answer-1' : null,
  status, ai_provider: 'deterministic', ai_model: 'offline', retrieval_policy: 'hybrid_exact_v1',
  attempt_count: status === 'queued' ? 0 : 1, manual_retry_count: 0, max_attempts: 3,
  estimated_input_tokens: 200, estimated_output_tokens: 80,
  actual_input_tokens: status === 'completed' ? 150 : null,
  actual_output_tokens: status === 'completed' ? 40 : null,
  provider_request_count: status === 'completed' ? 3 : 0, provider_retry_count: 0,
  provider_rate_limit_wait_milliseconds: 0, estimated_cost_microusd: 2,
  actual_cost_microusd: status === 'completed' ? 1 : null, usage_estimated: false,
  support_rejection_count: 0, error_code: null, error_message: null,
  cancellation_requested_at: null, created_at: '2026-09-19T12:00:00Z',
  completed_at: status === 'completed' ? '2026-09-19T12:00:02Z' : null,
  updated_at: '2026-09-19T12:00:02Z', can_cancel: status === 'queued' || status === 'running',
  can_retry: status === 'failed' || status === 'cancelled', ...overrides,
})

const history = (withFollowUp = false): RagHistory => ({
  thread,
  messages: [
    {
      id: 'question-0', role: 'user', outcome: null, content: 'What is perihelion?', hidden: false,
      sources: [], created_at: '2026-09-19T12:00:00Z', expires_at: '2026-12-18T12:00:00Z',
    },
    {
      id: 'answer-0', role: 'assistant', outcome: 'answer',
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
      id: 'question-1', role: 'user' as const, outcome: null, content: 'What is aphelion?', hidden: false,
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
  await expect(page.getByRole('button', { name: 'Generate Flashcard Set' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Subject Knowledge' })).toBeVisible()
  await expect(page.getByText('Awaiting instructor review')).toBeVisible()
  await expect(page.getByText('Private', { exact: true })).toBeVisible()
  await expect(page.getByText(/sent to Google Gemini API \(gemini-embedding-001\)/)).toBeVisible()
  await page.getByRole('button', { name: 'Review & publish' }).click()
  await expect(page.getByText('Published for enrolled students')).toBeVisible()
  await expect(page.getByText(/indexing retry rebuilds from persisted extracted pages/i).first()).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)
  if (process.env.RAG_UI_CAPTURE === '1') {
    await page.screenshot({ path: testInfo.outputPath('phase18-instructor-knowledge.png'), fullPage: true })
  }
})

test('Ask AI escapes model text, exposes authorized evidence, and retries one logical question safely', async ({ page }, testInfo) => {
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
        if (!accepted) return { json: { jobs: [answerJob('completed')] } }
        jobPollsAfterAccept += 1
        return { json: { jobs: [answerJob(jobPollsAfterAccept >= 2 ? 'completed' : 'queued')] } }
      }
      if (call.method === 'POST' && call.path === `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`) {
        if (callNumber === 1) return { status: 503, json: { detail: 'Answer admission temporarily unavailable' } }
        accepted = true
        return { status: 202, json: answerJob('queued') }
      }
      return undefined
    },
  })

  await page.goto('/subjects/subject-1')
  await expect(page.getByText('<script>alert("unsafe")</script>', { exact: false })).toBeVisible()
  await expect(page.locator('article script')).toHaveCount(0)
  await expect(page.getByText(/bounded private chat history.*Google Gemini API \(gemini-3.5-flash\)/)).toBeVisible()
  await page.getByRole('button', { name: /Lecture 05 · p\.17 · Orbital motion/ }).click()
  const evidence = page.getByRole('dialog', { name: 'Authorized evidence' })
  await expect(evidence).toContainText('Perihelion is the point in an orbit nearest the Sun.')
  await evidence.getByRole('button', { name: 'Close' }).click()

  await page.getByRole('textbox', { name: 'Question' }).fill('What is aphelion?')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Answer admission temporarily unavailable')
  await page.getByRole('button', { name: 'Retry question safely' }).click()
  const submissions = api.callsFor('POST', `/subjects/subject-1/rag/threads/${thread.id}/answer-jobs`)
  expect(submissions).toHaveLength(2)
  expect(submissions[0].headers['idempotency-key']).toBe(submissions[1].headers['idempotency-key'])
  await expect(page.getByText('Question queued')).toBeVisible()
  await expect(page.getByText('Answer completed')).toBeVisible({ timeout: 6_000 })
  await expectNoSeriousOrCriticalViolations(page)
  if (process.env.RAG_UI_CAPTURE === '1') {
    await page.screenshot({ path: testInfo.outputPath('phase18-student-ask-ai.png'), fullPage: true })
  }

  await page.setViewportSize({ width: 360, height: 780 })
  const widths = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: window.innerWidth }))
  expect(widths.body).toBeLessThanOrEqual(widths.viewport)
})

test('Ask AI renders durable running, failed, cancelled, abstained, and hidden-source states', async ({ page }) => {
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
                error_code: jobState === 'failed' ? 'rag_knowledge_unavailable' : null,
                error_message: jobState === 'failed'
                  ? 'No reviewed and published Knowledge is available for this subject yet.'
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
                id: 'abstained-answer', role: 'assistant', outcome: 'abstained',
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
  await expect(page.getByText('Searching published Knowledge and checking support')).toBeVisible()
  await expect(page.getByText('The course material did not provide enough support for an answer.')).toBeVisible()
  await expect(page.getByText('This message is unavailable because its source access or revision is no longer current.')).toBeVisible()
  await expect(page.getByText('Previously grounded text must not remain visible.')).toHaveCount(0)

  await page.locator('#rag-thread').selectOption('thread-failed')
  await expect(page.getByText('Answer failed safely')).toBeVisible()
  await expect(page.getByText('No reviewed and published Knowledge is available for this subject yet.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry answer' })).toBeVisible()

  await page.locator('#rag-thread').selectOption('thread-cancelled')
  await expect(page.getByText('Answer cancelled')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry answer' })).toBeVisible()
  await expectNoSeriousOrCriticalViolations(page)
})
