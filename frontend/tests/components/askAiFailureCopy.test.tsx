import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'

import { AskAiPanel } from '@/components/rag/AskAiPanel'
import { copy } from '@/i18n/en'
import type { RagAnswerJob, RagHistory, RagMessage, RagProfile, RagThread } from '@/services/types'

const mocks = vi.hoisted(() => ({
  listThreads: vi.fn(), getProfile: vi.fn(), getHistory: vi.fn(), listJobs: vi.fn(),
  createThread: vi.fn(), deleteThread: vi.fn(), ask: vi.fn(), cancelJob: vi.fn(), retryJob: vi.fn(), getRelatedPage: vi.fn(),
}))

vi.mock('@/services/rag', () => ({ ragService: mocks }))
vi.mock('@/components/rag/OriginalPdfPage', () => ({ default: ({ onAccessChanged }: { onAccessChanged: () => void }) => (
  <button type="button" onClick={onAccessChanged}>Simulate revoked PDF access</button>
) }))

const thread: RagThread = {
  id: 'thread-1', subject_id: 'subject-1', created_at: '2026-09-25T00:00:00Z', updated_at: '2026-09-25T00:00:00Z',
}
const profile: RagProfile = {
  rag_enabled: true, ask_enabled: true, ask_policy: 'related_knowledge_navigation_v8', ask_available: true, answer_available: false,
  answer_provider: '', answer_model: '',
  embedding_available: true, embedding_provider: 'gemini', embedding_model: 'example-embedding-model',
  active_embedding_provider: 'gemini', active_embedding_model: 'example-embedding-model',
  active_embedding_space_matches: true,
  source_judge_available: true, source_judge_provider: 'gemini', source_judge_model: 'example-source-judge',
  source_judge_transfers_published_content: true, chat_retention_days: 90,
  source_judge_thinking_level: 'HIGH', source_judge_transfers_page_images: true,
  source_judge_contract_version: 'visual_source_id_v5',
  source_judge_transfers_literal_subject_context: true,
}
const question: RagMessage = {
  id: 'question-1', role: 'user', outcome: null, abstention_kind: null,
  content: 'What does this lecture say?', hidden: false, sources: [],
  created_at: '2026-09-25T00:00:00Z', expires_at: '2026-12-24T00:00:00Z',
}
const excerpt = {
  excerpt_order: 1, document_title: 'Lecture 05', page_number: 17,
  section: 'Orbital motion', source_quote: 'The exact indexed reference.',
}
const openPageName = `${copy.askAi.openRelatedPage(excerpt.page_number)} — ${copy.askAi.referenceNumber(1)} — ${excerpt.document_title}`

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}
const baseJob: RagAnswerJob = {
  id: 'job-1', thread_id: thread.id, subject_id: thread.subject_id,
  question_message_id: question.id, answer_message_id: null,
  ask_policy: 'related_knowledge_navigation_v8', result_kind: 'related_knowledge', status: 'completed',
  search_mode: 'hybrid',
  embedding_provider: 'gemini', embedding_model: 'example-embedding-model',
  source_judge_provider: 'gemini', source_judge_model: 'example-source-judge',
  ai_provider: null, ai_model: null, retrieval_policy: 'hybrid_exact_v1',
  attempt_count: 1, manual_retry_count: 0, max_attempts: 3,
  estimated_input_tokens: 100, estimated_output_tokens: 0,
  actual_input_tokens: 90, actual_output_tokens: null,
  provider_request_count: 1, provider_retry_count: 0, provider_rate_limit_wait_milliseconds: 0,
  estimated_cost_microusd: 20, actual_cost_microusd: 18,
  estimated_additional_cost_microusd: null, previous_attempt_cost_microusd: null,
  usage_estimated: true, support_rejection_count: 0, related_excerpts: [excerpt],
  error_code: null, error_message: null, failure_kind: null, cancellation_requested_at: null,
  created_at: '2026-09-25T00:00:00Z', completed_at: '2026-09-25T00:00:01Z',
  updated_at: '2026-09-25T00:00:01Z', can_cancel: false, can_retry: false,
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset()
  mocks.listThreads.mockResolvedValue([thread])
  mocks.getProfile.mockResolvedValue(profile)
  mocks.getHistory.mockResolvedValue({ thread, messages: [question] })
  mocks.listJobs.mockResolvedValue([baseJob])
})

it('keeps v5 references readable without retrying them under the v8 profile', async () => {
  mocks.listJobs.mockResolvedValue([{ ...baseJob, ask_policy: 'related_knowledge_navigation_v5', can_retry: true }])
  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(excerpt.source_quote)).toBeTruthy()
  expect(screen.queryByRole('button', { name: copy.askAi.retry })).toBeNull()
  expect(mocks.retryJob).not.toHaveBeenCalled()
})

it('keeps v7 references readable and fences their retry under the v8 profile', async () => {
  mocks.listJobs.mockResolvedValue([{ ...baseJob, ask_policy: 'related_knowledge_navigation_v7', can_retry: true }])
  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(excerpt.source_quote)).toBeTruthy()
  expect(screen.queryByRole('button', { name: copy.askAi.retry })).toBeNull()
  expect(mocks.retryJob).not.toHaveBeenCalled()
})

it('fences v7 admission even when its availability flags remain true', async () => {
  mocks.getProfile.mockResolvedValue({ ...profile, ask_policy: 'related_knowledge_navigation_v7', source_judge_contract_version: 'visual_source_id_v3' })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  await screen.findByText(excerpt.source_quote)
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel })).toHaveProperty('disabled', true)
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('fences a v5 profile even when its historical availability flags are true', async () => {
  mocks.getProfile.mockResolvedValue({ ...profile, ask_policy: 'related_knowledge_navigation_v5', source_judge_contract_version: 'visual_source_id_v1' })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  await screen.findByText(excerpt.source_quote)
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel })).toHaveProperty('disabled', true)
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('shows exact related Knowledge and opens the current extracted page with the reference marked', async () => {
  const pageContent = `Previous material. ${excerpt.source_quote} More lecture material.`
  const referenceStart = pageContent.indexOf(excerpt.source_quote)
  mocks.getRelatedPage.mockResolvedValue({
    document_title: excerpt.document_title, page_number: excerpt.page_number, section: excerpt.section,
    source_quote: excerpt.source_quote, page_content: pageContent,
    reference_start: referenceStart, reference_end: referenceStart + excerpt.source_quote.length,
  })

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(copy.askAi.relatedCompleted)).toBeTruthy()
  expect(screen.getByText(excerpt.source_quote)).toBeTruthy()
  expect(screen.queryByText('Answer completed')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: openPageName }))
  expect(await screen.findByRole('dialog', { name: copy.askAi.pageDialogTitle })).toBeTruthy()
  expect(mocks.getRelatedPage).toHaveBeenCalledWith(thread.subject_id, thread.id, baseJob.id, 1, expect.any(AbortSignal))
  await waitFor(() => expect(document.querySelector('mark')?.textContent).toBe(excerpt.source_quote))
  expect(screen.getByText(copy.askAi.pageDialogDescription)).toBeTruthy()
  expect(screen.getByText(/More lecture material\./)).toBeTruthy()
})

it('distinguishes buttons for separate references on the same PDF page', async () => {
  const secondExcerpt = { ...excerpt, excerpt_order: 2, source_quote: 'Another exact indexed reference.' }
  mocks.listJobs.mockResolvedValue([{ ...baseJob, related_excerpts: [excerpt, secondExcerpt] }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByRole('button', { name: openPageName })).toBeTruthy()
  expect(screen.getByRole('button', {
    name: `${copy.askAi.openRelatedPage(17)} — ${copy.askAi.referenceNumber(2)} — ${excerpt.document_title}`,
  })).toBeTruthy()
})

it('discards a pre-revocation thread read after PDF access changes', async () => {
  const staleHistory = deferred<RagHistory>()
  const staleJobs = deferred<RagAnswerJob[]>()
  const currentHistory = deferred<RagHistory>()
  const currentJobs = deferred<RagAnswerJob[]>()
  mocks.getHistory.mockResolvedValueOnce({ thread, messages: [question] })
    .mockReturnValueOnce(staleHistory.promise).mockReturnValueOnce(currentHistory.promise)
  mocks.listJobs.mockResolvedValueOnce([baseJob])
    .mockReturnValueOnce(staleJobs.promise).mockReturnValueOnce(currentJobs.promise)
  mocks.ask.mockResolvedValue(baseJob)
  mocks.getRelatedPage.mockResolvedValue({
    document_title: excerpt.document_title, page_number: excerpt.page_number, section: excerpt.section,
    source_quote: excerpt.source_quote, page_content: excerpt.source_quote,
    reference_start: 0, reference_end: excerpt.source_quote.length,
  })

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(excerpt.source_quote)).toBeTruthy()
  fireEvent.change(screen.getByRole('textbox', { name: copy.askAi.questionLabel }), {
    target: { value: 'Find another related page.' },
  })
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.ask }))
  await waitFor(() => expect(mocks.listJobs).toHaveBeenCalledTimes(2))

  fireEvent.click(screen.getByRole('button', { name: openPageName }))
  fireEvent.click(await screen.findByRole('button', { name: 'Simulate revoked PDF access' }))
  await waitFor(() => expect(mocks.listJobs).toHaveBeenCalledTimes(3))
  expect(screen.queryByText(excerpt.source_quote)).toBeNull()
  expect(screen.queryByRole('dialog', { name: copy.askAi.pageDialogTitle })).toBeNull()

  await act(async () => {
    currentHistory.resolve({ thread, messages: [question] })
    currentJobs.resolve([])
    await Promise.all([currentHistory.promise, currentJobs.promise])
  })
  expect(await screen.findByText(question.content!)).toBeTruthy()

  await act(async () => {
    staleHistory.resolve({ thread, messages: [question] })
    staleJobs.resolve([baseJob])
    await Promise.all([staleHistory.promise, staleJobs.promise])
  })
  expect(screen.queryByText(excerpt.source_quote)).toBeNull()
  expect(screen.queryByRole('dialog', { name: copy.askAi.pageDialogTitle })).toBeNull()
})

it('renders no match as a distinct safe result without a source or page request', async () => {
  mocks.listJobs.mockResolvedValue([{ ...baseJob, result_kind: 'no_match', related_excerpts: [] }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(copy.askAi.noMatch)).toBeTruthy()
  expect(screen.queryByRole('region', { name: copy.askAi.relatedKnowledgeTitle })).toBeNull()
  expect(screen.queryByRole('button', { name: openPageName })).toBeNull()
  expect(mocks.getRelatedPage).not.toHaveBeenCalled()
})

it('labels a withdrawn related bundle without suggesting a page is still available', async () => {
  mocks.listJobs.mockResolvedValue([{ ...baseJob, related_excerpts: [] }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(copy.askAi.relatedUnavailable)).toBeTruthy()
  expect(screen.queryByText(copy.askAi.relatedCompleted)).toBeNull()
  expect(screen.queryByRole('button', { name: openPageName })).toBeNull()
  expect(mocks.getRelatedPage).not.toHaveBeenCalled()
})

it('explains selected text and full-page PNG transfer before a v7 question and keeps results unverified', async () => {
  render(<AskAiPanel subjectId={thread.subject_id} />)
  const disclosure = await screen.findByText(/bounded selected page text and full-page PNG images rendered from the original PDF/)
  expect(disclosure.textContent).toContain('example-source-judge')
  expect(disclosure.textContent).toContain('only page labels and IDs, with no generated answer')
  expect(disclosure.textContent).toContain('Full earlier questions, chat history, assistant answers and original PDF file bytes are not sent')
  expect(disclosure.textContent).toContain('unverified reading suggestions')
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel }).hasAttribute('disabled')).toBe(false)
})

it('keeps clarification separate from no match and provider failure without opening a source', async () => {
  mocks.listJobs.mockResolvedValue([{ ...baseJob, result_kind: 'clarification_needed',
    search_mode: 'not_searched', related_excerpts: [] }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(copy.askAi.clarificationNeeded)).toBeTruthy()
  expect(screen.queryByText(copy.askAi.noMatch)).toBeNull()
  expect(screen.queryByText(copy.askAi.sourceProviderTemporarilyUnavailable)).toBeNull()
  expect(screen.queryByRole('button', { name: openPageName })).toBeNull()
  expect(mocks.getRelatedPage).not.toHaveBeenCalled()
})

it('keeps v3 source history readable while a paused v5 profile blocks new questions', async () => {
  mocks.getProfile.mockResolvedValue({ ...profile, ask_enabled: false, ask_available: false,
    source_judge_available: false })
  mocks.listJobs.mockResolvedValue([{ ...baseJob, ask_policy: 'related_knowledge_navigation_v3',
    source_judge_provider: null, source_judge_model: null }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(excerpt.source_quote)).toBeTruthy()
  expect(screen.getByText(copy.askAi.paused)).toBeTruthy()
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel }).hasAttribute('disabled')).toBe(true)
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('keeps v4 text-only disclosure and history readable without reopening the old policy', async () => {
  mocks.getProfile.mockResolvedValue({ ...profile, ask_policy: 'related_knowledge_navigation_v4',
    source_judge_thinking_level: 'LOW', source_judge_transfers_page_images: false,
    source_judge_transfers_literal_subject_context: false,
    source_judge_contract_version: 'source_id_only_public_v1' })
  mocks.listJobs.mockResolvedValue([{ ...baseJob, ask_policy: 'related_knowledge_navigation_v4',
    status: 'failed', result_kind: null, related_excerpts: [], can_retry: true }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  const disclosure = await screen.findByText(/bounded extracted page text from reviewed, published Knowledge/)
  expect(disclosure.textContent).toContain('Earlier chat and original PDF bytes are not sent')
  expect(disclosure.textContent).not.toContain('PNG')
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel }).hasAttribute('disabled')).toBe(true)
  expect(screen.queryByRole('button', { name: copy.askAi.retry })).toBeNull()
  expect(mocks.ask).not.toHaveBeenCalled()
})

it.each([
  { source_judge_thinking_level: 'LOW' as const },
  { source_judge_transfers_page_images: false },
  { source_judge_contract_version: 'unexpected-contract' },
])('keeps an inconsistent v7 profile closed: %j', async (change) => {
  mocks.getProfile.mockResolvedValue({ ...profile, ...change })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  await screen.findByText(copy.askAi.paused)
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel }).hasAttribute('disabled')).toBe(true)
  expect(mocks.ask).not.toHaveBeenCalled()
})

it.each([
  { source_judge_thinking_level: 'LOW' as const },
  { source_judge_transfers_page_images: false },
  { source_judge_contract_version: 'changed-contract' },
])('requires disclosure review if a visual processor field changes before submission: %j', async (change) => {
  mocks.getProfile.mockResolvedValueOnce(profile).mockResolvedValue({ ...profile, ...change })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.change(await screen.findByRole('textbox', { name: copy.askAi.questionLabel }), {
    target: { value: 'Which lecture page should I read?' },
  })
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.ask }))
  expect(await screen.findByText(copy.askAi.profileChanged)).toBeTruthy()
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('keeps Ask closed when the release gate is off even if availability is reported true', async () => {
  mocks.getProfile.mockResolvedValue({ ...profile, ask_enabled: false })

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(copy.askAi.paused)).toBeTruthy()
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel }).hasAttribute('disabled')).toBe(true)
  expect(screen.getByRole('button', { name: copy.askAi.newConversation }).hasAttribute('disabled')).toBe(true)
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('requires updated source-judge disclosure before enqueueing after a profile change', async () => {
  mocks.getProfile.mockResolvedValueOnce(profile)
    .mockResolvedValue({ ...profile, source_judge_model: 'new-source-judge' })
  mocks.ask.mockResolvedValue({ ...baseJob, status: 'queued', result_kind: null, related_excerpts: [] })

  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.change(await screen.findByRole('textbox', { name: copy.askAi.questionLabel }), {
    target: { value: 'Which lecture page should I read?' },
  })
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.ask }))
  expect(await screen.findByText(copy.askAi.profileChanged)).toBeTruthy()
  expect(screen.getByText(/new-source-judge/)).toBeTruthy()
  expect(mocks.ask).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: copy.askAi.ask }))
  await waitFor(() => expect(mocks.ask).toHaveBeenCalledTimes(1))
})

it('highlights the unchanged page span across extraction line breaks only when its words match', async () => {
  const pageSpan = 'The exact\nindexed reference.'
  mocks.getRelatedPage.mockResolvedValue({
    document_title: excerpt.document_title, page_number: 17, section: excerpt.section,
    source_quote: excerpt.source_quote, page_content: pageSpan,
    reference_start: 0, reference_end: pageSpan.length,
  })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.click(await screen.findByRole('button', { name: openPageName }))
  await waitFor(() => expect(document.querySelector('mark')?.textContent).toBe(pageSpan))
  expect(screen.queryByText(copy.askAi.pageReferenceNotLocated)).toBeNull()
})

it('does not highlight an unrelated page span even if supplied offsets are in bounds', async () => {
  const pageSpan = 'Unrelated text with no matching words.'
  mocks.getRelatedPage.mockResolvedValue({
    document_title: excerpt.document_title, page_number: 17, section: excerpt.section,
    source_quote: excerpt.source_quote, page_content: pageSpan,
    reference_start: 0, reference_end: pageSpan.length,
  })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.click(await screen.findByRole('button', { name: openPageName }))
  expect(await screen.findByText(copy.askAi.pageReferenceNotLocated)).toBeTruthy()
  expect(document.querySelector('mark')).toBeNull()
})

it('hides generated answers and legacy jobs even if the history API still returns them', async () => {
  const oldAnswer: RagMessage = {
    ...question, id: 'old-answer', role: 'assistant', outcome: 'answer',
    content: 'An old generated answer should not be shown.',
    sources: [{ citation_order: 1, chunk_id: 'chunk-1', document_id: 'document-1',
      document_title: 'Old lecture', content_revision_id: 'content-1', index_revision_id: 'index-1',
      page_number: 1, section: null, claim_text: 'An old claim.', source_quote: 'An old quote.' }],
  }
  mocks.getHistory.mockResolvedValue({ thread, messages: [question, oldAnswer] })
  mocks.listJobs.mockResolvedValue([{ ...baseJob, ask_policy: 'two_request_local_support_v1',
    answer_message_id: oldAnswer.id, result_kind: null, related_excerpts: [] }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(question.content!)).toBeTruthy()
  expect(screen.queryByText(oldAnswer.content!)).toBeNull()
  expect(screen.queryByText('An old quote.')).toBeNull()
  expect(screen.queryByText(copy.askAi.relatedCompleted)).toBeNull()
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel })).toBeTruthy()
})

it('keeps a previous source result beside its question when a later search has no match', async () => {
  const newerQuestion: RagMessage = { ...question, id: 'question-2', content: 'A newer question?' }
  mocks.getHistory.mockResolvedValue({ thread, messages: [question, newerQuestion] })
  mocks.listJobs.mockResolvedValue([
    { ...baseJob, id: 'job-2', question_message_id: newerQuestion.id, result_kind: 'no_match', related_excerpts: [] },
    baseJob,
  ])

  const { container } = render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(excerpt.source_quote)).toBeTruthy()
  expect(screen.getByText(copy.askAi.noMatch)).toBeTruthy()
  const rendered = container.textContent ?? ''
  expect(rendered.indexOf(question.content!)).toBeLessThan(rendered.indexOf(excerpt.source_quote))
  expect(rendered.indexOf(excerpt.source_quote)).toBeLessThan(rendered.indexOf(newerQuestion.content!))
})

it('shows a safe page-unavailable state if source access changed before opening', async () => {
  mocks.getRelatedPage.mockRejectedValue(new Error('Internal source detail must stay hidden'))

  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.click(await screen.findByRole('button', { name: openPageName }))
  expect(await screen.findByRole('dialog', { name: copy.askAi.pageDialogTitle })).toBeTruthy()
  expect(await screen.findByText(copy.askAi.pageUnavailable)).toBeTruthy()
  expect(screen.queryByText('Internal source detail must stay hidden')).toBeNull()
  expect(mocks.getHistory).toHaveBeenCalledTimes(2)
})

it('closes an open page and clears its quote when revalidation withdraws the source', async () => {
  mocks.getRelatedPage.mockRejectedValue(new Error('Page revoked'))
  mocks.listJobs.mockResolvedValueOnce([baseJob]).mockResolvedValue([])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.click(await screen.findByRole('button', { name: openPageName }))
  await waitFor(() => expect(screen.queryByRole('dialog', { name: copy.askAi.pageDialogTitle })).toBeNull())
  expect(screen.queryByText(excerpt.source_quote)).toBeNull()
})

it('removes displayed excerpts when polling cannot revalidate the active conversation', async () => {
  mocks.getHistory.mockResolvedValueOnce({ thread, messages: [question] })
    .mockRejectedValueOnce(new Error('Refresh unavailable'))
  mocks.listJobs.mockResolvedValueOnce([
    { ...baseJob, status: 'running', result_kind: null, related_excerpts: [] },
    { ...baseJob, id: 'older-job', related_excerpts: [excerpt] },
  ]).mockResolvedValue([])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(excerpt.source_quote)).toBeTruthy()
  await waitFor(() => expect(screen.queryByText(excerpt.source_quote)).toBeNull(), { timeout: 4_000 })
  expect(screen.getByRole('alert')).toBeTruthy()
})

it('keeps raw provider errors hidden and asks before a paid manual retry', async () => {
  mocks.listJobs.mockResolvedValue([{ ...baseJob, status: 'failed', result_kind: null,
    related_excerpts: [], error_code: 'rag_answer_failed', error_message: 'DO_NOT_RENDER_INTERNAL_ERROR',
    failure_kind: 'provider_temporarily_unavailable', can_retry: true,
    estimated_additional_cost_microusd: 30_000, previous_attempt_cost_microusd: null }])

  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(copy.askAi.sourceProviderTemporarilyUnavailable)).toBeTruthy()
  expect(screen.getByText(copy.askAi.sourceFailure)).toBeTruthy()
  expect(screen.queryByText('DO_NOT_RENDER_INTERNAL_ERROR')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.retry }))
  expect(screen.getByText(copy.askAi.retryLiteralSubjectDialogDescription)).toBeTruthy()
  expect(screen.getByText(copy.askAi.estimatedAdditionalCost('$0.03'))).toBeTruthy()
  expect(screen.getByText(copy.askAi.previousAttemptCostUnknown)).toBeTruthy()
  expect(mocks.retryJob).not.toHaveBeenCalled()
})

it('discloses a bounded optional literal subject without adding browser history to Ask', async () => {
  mocks.ask.mockResolvedValue({ ...baseJob, status: 'queued', result_kind: null, related_excerpts: [] })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  const disclosure = await screen.findByText(/Before searching: your unchanged current question/)
  expect(disclosure.textContent).toContain('for one query embedding')
  expect(disclosure.textContent).toContain('in at most one request')
  expect(disclosure.textContent).toContain('at most 160 characters from the immediately preceding user question')
  expect(disclosure.textContent).toContain('may accompany the page-selection request')
  expect(disclosure.textContent).toContain('Full earlier questions, chat history, assistant answers and original PDF file bytes are not sent')
  fireEvent.change(screen.getByRole('textbox', { name: copy.askAi.questionLabel }), {
    target: { value: 'What does it stand for?' },
  })
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.ask }))
  await waitFor(() => expect(mocks.ask).toHaveBeenCalledTimes(1))
  expect(mocks.ask).toHaveBeenCalledWith(thread.subject_id, thread.id, 'What does it stand for?', expect.any(String))
})

it.each([
  { source_judge_transfers_literal_subject_context: false },
  { source_judge_contract_version: 'visual_source_id_v2' },
  { ask_policy: 'related_knowledge_navigation_v6' as const },
])('keeps search closed for a missing v7 context contract: %j', async (change) => {
  mocks.getProfile.mockResolvedValue({ ...profile, ...change })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  await screen.findByText(excerpt.source_quote)
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel })).toHaveProperty('disabled', true)
  expect(screen.getByRole('button', { name: copy.askAi.ask })).toHaveProperty('disabled', true)
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('keeps search closed when an older server omits the context capability', async () => {
  const { source_judge_transfers_literal_subject_context: omitted, ...withoutCapability } = profile
  expect(omitted).toBe(true)
  mocks.getProfile.mockResolvedValue(withoutCapability)
  render(<AskAiPanel subjectId={thread.subject_id} />)
  await screen.findByText(excerpt.source_quote)
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel })).toHaveProperty('disabled', true)
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('keeps v6 references readable and never retries them under v7', async () => {
  mocks.listJobs.mockResolvedValue([{ ...baseJob, ask_policy: 'related_knowledge_navigation_v6', can_retry: true }])
  render(<AskAiPanel subjectId={thread.subject_id} />)
  expect(await screen.findByText(excerpt.source_quote)).toBeTruthy()
  expect(screen.queryByRole('button', { name: copy.askAi.retry })).toBeNull()
  expect(mocks.retryJob).not.toHaveBeenCalled()
})

it('requires profile review when literal-subject capability changes before submission', async () => {
  mocks.getProfile.mockResolvedValueOnce(profile)
    .mockResolvedValue({ ...profile, source_judge_transfers_literal_subject_context: false })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.change(await screen.findByRole('textbox', { name: copy.askAi.questionLabel }), {
    target: { value: 'What does it stand for?' },
  })
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.ask }))
  expect(await screen.findByText(copy.askAi.profileChanged)).toBeTruthy()
  expect(screen.getByRole('textbox', { name: copy.askAi.questionLabel })).toHaveProperty('value', 'What does it stand for?')
  expect(mocks.ask).not.toHaveBeenCalled()
})

it('rechecks literal-subject capability at retry confirmation and preserves unknown spend', async () => {
  mocks.getProfile.mockResolvedValueOnce(profile)
    .mockResolvedValue({ ...profile, source_judge_transfers_literal_subject_context: false })
  mocks.listJobs.mockResolvedValue([{ ...baseJob, status: 'failed', result_kind: null, related_excerpts: [], can_retry: true,
    estimated_additional_cost_microusd: null, previous_attempt_cost_microusd: null }])
  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.click(await screen.findByRole('button', { name: copy.askAi.retry }))
  expect(screen.getByText(copy.askAi.retryLiteralSubjectDialogDescription)).toBeTruthy()
  expect(screen.getByText(copy.askAi.previousAttemptCostUnknown)).toBeTruthy()
  expect(mocks.retryJob).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.confirmRetry }))
  expect(await screen.findByText(copy.askAi.profileChanged)).toBeTruthy()
  expect(mocks.retryJob).not.toHaveBeenCalled()
})

it('cancels a v7 retry without any new request and confirms only once', async () => {
  const failed = { ...baseJob, status: 'failed' as const, result_kind: null, related_excerpts: [], can_retry: true }
  mocks.listJobs.mockResolvedValue([failed])
  mocks.retryJob.mockResolvedValue({ ...failed, status: 'queued', can_retry: false })
  render(<AskAiPanel subjectId={thread.subject_id} />)
  fireEvent.click(await screen.findByRole('button', { name: copy.askAi.retry }))
  fireEvent.click(screen.getByRole('button', { name: copy.common.cancel }))
  expect(mocks.retryJob).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.retry }))
  fireEvent.click(screen.getByRole('button', { name: copy.askAi.confirmRetry }))
  await waitFor(() => expect(mocks.retryJob).toHaveBeenCalledTimes(1))
})
