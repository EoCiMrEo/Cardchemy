import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { useGenerationJobs } from '@/hooks/useGenerationJobs'
import StudentSubjectDetails from '@/pages/student/StudentSubjectDetails'
import type { FlashcardSet, GenerationJob, Subject } from '@/services/types'
import { copy } from '@/i18n/en'

const mocks = vi.hoisted(() => ({ subject: vi.fn(), sets: vi.fn(), progress: vi.fn(), jobs: vi.fn(), limits: vi.fn(), retry: vi.fn() }))
vi.mock('@/services/subjects', () => ({ subjectService: { getSubject: mocks.subject, getSets: mocks.sets } }))
vi.mock('@/services/study', () => ({ studyService: { getSetProgress: mocks.progress } }))
vi.mock('@/services/flashcards', () => ({ flashcardService: { listGenerationJobs: mocks.jobs, getGenerationLimits: mocks.limits, retryGenerationJob: mocks.retry } }))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(r => { resolve = r })
  return { promise, resolve }
}
const subject: Subject = { id: 'subject-1', name: 'Old subject', description: null, instructor_id: 'instructor', created_at: '2026-01-01', flashcard_set_count: 1, student_count: 1 }
const set: FlashcardSet = { id: 'set-1', subject_id: subject.id, title: 'Old set', description: null, source_pdf_name: null, generation_job_id: null, is_published: false, time_limit: null, created_at: '2026-01-01', flashcard_count: 1, approved_count: 1 }
const job: GenerationJob = {
  id: 'job-1', subject_id: subject.id, job_kind: 'flashcards', document_id: null,
  knowledge_content_revision_id: null, knowledge_capture_status: 'not_requested',
  knowledge_capture_error_code: null, knowledge_capture_error_message: null,
  flashcard_set_id: set.id, status: 'completed', progress: 100, stage: 'completed',
  requested_card_count: 2, generated_card_count: 2, ai_provider: 'test', ai_model: 'test',
  estimated_input_tokens: 0, estimated_output_tokens: 0, estimated_request_count: 0,
  provider_request_count: 0, provider_retry_count: 0, provider_rate_limit_wait_milliseconds: 0,
  cached_input_tokens: 0, provider_request_counts_by_stage: {}, actual_input_tokens: null, actual_output_tokens: null,
  estimated_cost_microusd: null, actual_cost_microusd: null, usage_estimated: true, accepted_card_count: 2, rejected_card_count: 0,
  limit_reason_code: null, limit_reason_message: null, source_pdf_name: 'test.pdf', attempt_count: 1, max_attempts: 3,
  error_code: null, error_message: null, cancellation_requested_at: null, source_retry_expires_at: null,
  created_at: '2026-01-01', started_at: null, completed_at: '2026-01-01', updated_at: '2026-01-01', can_cancel: false, can_retry: false,
}
beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset()
  mocks.subject.mockResolvedValue(subject)
  mocks.sets.mockResolvedValue([set])
  mocks.jobs.mockResolvedValue([job])
  mocks.limits.mockResolvedValue(null)
})

function subjectPage() {
  return render(<MemoryRouter initialEntries={['/subjects/subject-1']}>
    <Link to="/subjects/subject-2">Next subject</Link>
    <Routes><Route path="/subjects/:id" element={<StudentSubjectDetails />} /></Routes>
  </MemoryRouter>)
}

it('hides loaded Subject data immediately while the next Subject is loading', async () => {
  const next = deferred<Subject>()
  mocks.subject.mockResolvedValueOnce(subject).mockReturnValueOnce(next.promise)
  mocks.sets.mockResolvedValueOnce([set]).mockResolvedValueOnce([])
  subjectPage()
  await screen.findByRole('heading', { name: subject.name })
  const oldSignal = mocks.subject.mock.calls[0][1] as AbortSignal
  fireEvent.click(screen.getByText('Next subject'))
  expect(oldSignal.aborted).toBe(true)
  expect(screen.getByRole('status', { name: copy.common.loading })).toBeTruthy()
  expect(screen.queryByText(subject.name)).toBeNull()
  expect(screen.queryByText(set.title)).toBeNull()
  await act(async () => { next.resolve({ ...subject, id: 'subject-2', name: 'Next subject heading' }) })
  await screen.findByRole('heading', { name: 'Next subject heading' })
})

it('ignores an old Subject response even when the transport resolves after cancellation', async () => {
  const old = deferred<Subject>()
  mocks.subject.mockReturnValueOnce(old.promise).mockResolvedValueOnce({ ...subject, id: 'subject-2', name: 'New subject' })
  mocks.sets.mockResolvedValueOnce([set]).mockResolvedValueOnce([])
  subjectPage()
  fireEvent.click(screen.getByText('Next subject'))
  await screen.findByRole('heading', { name: 'New subject' })
  await act(async () => { old.resolve(subject) })
  expect(screen.queryByText(subject.name)).toBeNull()
  expect(screen.queryByText(set.title)).toBeNull()
  expect(screen.getByRole('heading', { name: 'New subject' })).toBeTruthy()
})

it('keeps previous Subject jobs hidden after the next poll fails and ignores an old retry response', async () => {
  mocks.jobs.mockResolvedValueOnce([job]).mockRejectedValue(new Error('offline'))
  const retried = deferred<GenerationJob>()
  mocks.retry.mockReturnValue(retried.promise)
  const completed = vi.fn()
  const view = renderHook(({ id }) => useGenerationJobs(id, completed), { initialProps: { id: subject.id } })
  await waitFor(() => expect(view.result.current.jobs).toEqual([job]))
  let retry!: Promise<void>
  act(() => { retry = view.result.current.retryJob(job.id, 'same-logical-key') })
  view.rerender({ id: 'subject-2' })
  expect(view.result.current.jobs).toEqual([])
  await waitFor(() => expect(view.result.current.loading).toBe(false))
  expect(view.result.current.statusMessage).toBe(copy.generation.statusUnavailable)
  await act(async () => { retried.resolve({ ...job, status: 'queued' }); await retry })
  expect(view.result.current.jobs).toEqual([])
  expect(completed).not.toHaveBeenCalled()
  view.unmount()
})

it('cancels old polling and prevents a delayed response from replacing current Subject jobs', async () => {
  const old = deferred<GenerationJob[]>()
  const nextJob = { ...job, id: 'job-2', subject_id: 'subject-2' }
  mocks.jobs.mockReturnValueOnce(old.promise).mockResolvedValueOnce([nextJob])
  const view = renderHook(({ id }) => useGenerationJobs(id, vi.fn()), { initialProps: { id: subject.id } })
  const signal = mocks.jobs.mock.calls[0][1] as AbortSignal
  view.rerender({ id: 'subject-2' })
  expect(signal.aborted).toBe(true)
  await waitFor(() => expect(view.result.current.jobs).toEqual([nextJob]))
  await act(async () => { old.resolve([job]) })
  expect(view.result.current.jobs).toEqual([nextJob])
})
