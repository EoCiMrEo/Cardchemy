import { Fragment, lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Bot, FileText, Loader2, MessageCirclePlus, Send, Trash2, UserRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { ragService } from '@/services/rag'
import type { RagAnswerJob, RagMessage, RagProfile, RagRelatedExcerpt, RagRelatedPage, RagThread } from '@/services/types'

const OriginalPdfPage = lazy(() => import('./OriginalPdfPage'))

interface AskAiPanelProps {
  subjectId: string
}

function formatMicrousd(value: number): string {
  if (value > 0 && value < 10_000) return '<$0.01'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value / 1_000_000)
}

function sameProcessorProfile(left: RagProfile, right: RagProfile): boolean {
  return left.ask_policy === right.ask_policy
    && left.ask_available === right.ask_available
    && left.embedding_provider === right.embedding_provider
    && left.embedding_model === right.embedding_model
    && left.active_embedding_provider === right.active_embedding_provider
    && left.active_embedding_model === right.active_embedding_model
    && left.active_embedding_space_matches === right.active_embedding_space_matches
    && left.source_judge_available === right.source_judge_available
    && left.source_judge_provider === right.source_judge_provider
    && left.source_judge_model === right.source_judge_model
    && left.source_judge_transfers_published_content === right.source_judge_transfers_published_content
    && left.source_judge_thinking_level === right.source_judge_thinking_level
    && left.source_judge_transfers_page_images === right.source_judge_transfers_page_images
    && left.source_judge_transfers_literal_subject_context === right.source_judge_transfers_literal_subject_context
    && left.source_judge_contract_version === right.source_judge_contract_version
    && left.ask_enabled === right.ask_enabled
    && left.chat_retention_days === right.chat_retention_days
}

function canSearch(profile: RagProfile | null): boolean {
  return profile?.rag_enabled === true
    && profile.ask_enabled === true
    && profile.ask_available === true
    && profile.ask_policy === 'related_knowledge_navigation_v8'
    && profile.source_judge_available === true
    && profile.source_judge_transfers_published_content === true
    && profile.source_judge_transfers_page_images === true
    && profile.source_judge_thinking_level === 'HIGH'
    && profile.source_judge_contract_version === 'visual_source_id_v5'
    && profile.source_judge_transfers_literal_subject_context === true
    && Boolean(profile.source_judge_provider && profile.source_judge_model)
}

function jobStatusLabel(job: RagAnswerJob): string {
  if (job.status === 'queued') return copy.askAi.queued
  if (job.status === 'running') return copy.askAi.running
  if (job.status === 'completed') {
    if (job.result_kind === 'related_knowledge') return job.related_excerpts.length > 0
      ? copy.askAi.relatedCompleted : copy.askAi.relatedUnavailable
    if (job.result_kind === 'no_match') return copy.askAi.noMatch
    if (job.result_kind === 'clarification_needed') return copy.askAi.clarificationNeeded
    return copy.askAi.sourceSearchFailed
  }
  if (job.status === 'failed') {
    return job.failure_kind === 'provider_temporarily_unavailable'
      ? copy.askAi.sourceProviderTemporarilyUnavailable
      : copy.askAi.sourceSearchFailed
  }
  return copy.askAi.cancelled
}

function visibleRelatedExcerpts(job: RagAnswerJob | undefined): RagRelatedExcerpt[] {
  return job?.status === 'completed' && job.result_kind === 'related_knowledge'
    ? job.related_excerpts
    : []
}

function RelatedKnowledgePanel({
  excerpts, headingId, onOpenPage,
}: {
  excerpts: RagRelatedExcerpt[]
  headingId: string
  onOpenPage: (excerpt: RagRelatedExcerpt) => void
}) {
  if (excerpts.length === 0) return null
  return (
    <section aria-labelledby={headingId} className="min-w-0 space-y-3 rounded border border-amber-200 bg-amber-50 p-3 sm:p-4">
      <div>
        <h3 id={headingId} className="text-sm font-semibold text-amber-950">{copy.askAi.relatedKnowledgeTitle}</h3>
        <p className="mt-1 text-sm text-amber-900">{copy.askAi.relatedKnowledgeDescription}</p>
      </div>
      <ol className="space-y-3">
        {excerpts.map((excerpt, index) => (
          <li key={`${index}-${excerpt.document_title}-${excerpt.page_number}`} className="min-w-0 rounded border border-amber-200 bg-white p-3">
            <p className="mb-1 text-xs font-semibold text-slate-600">{copy.askAi.referenceNumber(index + 1)}</p>
            <p className="break-words text-xs font-semibold text-amber-900">{copy.askAi.citationLabel(excerpt.document_title, excerpt.page_number, excerpt.section)}</p>
            <blockquote className="mt-2 whitespace-pre-wrap break-words border-l-4 border-amber-300 pl-3 text-sm text-slate-800">{excerpt.source_quote}</blockquote>
            <Button type="button" size="sm" variant="outline" className="mt-3 min-h-11"
              aria-label={`${copy.askAi.openRelatedPage(excerpt.page_number)} — ${copy.askAi.referenceNumber(index + 1)} — ${excerpt.document_title}`}
              onClick={() => onOpenPage(excerpt)}>
              <FileText className="mr-2 h-4 w-4" aria-hidden="true" />{copy.askAi.openRelatedPage(excerpt.page_number)}
            </Button>
          </li>
        ))}
      </ol>
    </section>
  )
}

interface RelatedPageTarget {
  threadId: string
  jobId: string
  excerptOrder: number
}

export function AskAiPanel({ subjectId }: AskAiPanelProps) {
  return <SubjectAskAiPanel key={subjectId} subjectId={subjectId} />
}

function SubjectAskAiPanel({ subjectId }: AskAiPanelProps) {
  const [threads, setThreads] = useState<RagThread[]>([])
  const [profile, setProfile] = useState<RagProfile | null>(null)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<RagMessage[]>([])
  const [jobs, setJobs] = useState<RagAnswerJob[]>([])
  const [question, setQuestion] = useState('')
  const [submissionKey, setSubmissionKey] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [loadedSubjectId, setLoadedSubjectId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pageTarget, setPageTarget] = useState<RelatedPageTarget | null>(null)
  const [relatedPage, setRelatedPage] = useState<RagRelatedPage | null>(null)
  const [pageLoading, setPageLoading] = useState(false)
  const [pageError, setPageError] = useState(false)
  const [retryCandidate, setRetryCandidate] = useState<RagAnswerJob | null>(null)
  const [retrySubmitting, setRetrySubmitting] = useState(false)
  const requestRevisionRef = useRef(0)
  const requestControllerRef = useRef<AbortController | null>(null)
  const pageControllerRef = useRef<AbortController | null>(null)
  const pageRevisionRef = useRef(0)
  const pageTargetRef = useRef<RelatedPageTarget | null>(null)
  const pageTriggerRef = useRef<HTMLElement | null>(null)
  const retryKeysRef = useRef(new Map<string, string>())
  const loading = loadedSubjectId !== subjectId

  const closeRelatedPage = useCallback(() => {
    pageRevisionRef.current += 1
    pageControllerRef.current?.abort()
    pageControllerRef.current = null
    pageTargetRef.current = null
    setPageTarget(null)
    setRelatedPage(null)
    setPageLoading(false)
    setPageError(false)
  }, [])

  const loadThread = useCallback(async (
    targetThreadId: string,
    signal?: AbortSignal,
    revision = requestRevisionRef.current,
  ) => {
    try {
      const [history, nextJobs] = await Promise.all([
        ragService.getHistory(subjectId, targetThreadId, signal),
        ragService.listJobs(subjectId, targetThreadId, signal),
      ])
      if (signal?.aborted || revision !== requestRevisionRef.current) return
      setMessages(history.messages.filter((message) => message.role === 'user'))
      setJobs(nextJobs.filter((job) => job.ask_policy === 'related_knowledge_v1'
        || job.ask_policy === 'related_knowledge_navigation_v2'
        || job.ask_policy === 'related_knowledge_navigation_v3'
        || job.ask_policy === 'related_knowledge_navigation_v4'
        || job.ask_policy === 'related_knowledge_navigation_v5'
        || job.ask_policy === 'related_knowledge_navigation_v6'
        || job.ask_policy === 'related_knowledge_navigation_v7'
        || job.ask_policy === 'related_knowledge_navigation_v8'))
      const viewed = pageTargetRef.current
      if (viewed && (
        viewed.threadId !== targetThreadId
        || !nextJobs.some((job) => job.id === viewed.jobId
          && job.status === 'completed' && job.result_kind === 'related_knowledge'
          && history.messages.some((message) => message.id === job.question_message_id && message.role === 'user' && !message.hidden)
          && job.related_excerpts.some((excerpt) => excerpt.excerpt_order === viewed.excerptOrder))
      )) closeRelatedPage()
      setError(null)
    } catch (caught: unknown) {
      if (!signal?.aborted && revision === requestRevisionRef.current) {
        setMessages([])
        setJobs([])
        closeRelatedPage()
        setRetryCandidate(null)
        setError(apiErrorMessage(caught, copy.askAi.loadFailed))
      }
    }
  }, [closeRelatedPage, subjectId])

  const onPageAccessChanged = useCallback(() => {
    const target = pageTargetRef.current
    closeRelatedPage()
    if (!target) return
    // A poll or initial history read may have started before access changed.
    // Invalidate it before reloading, and remove its source text immediately.
    const revision = ++requestRevisionRef.current
    requestControllerRef.current?.abort()
    const controller = new AbortController()
    requestControllerRef.current = controller
    setLoadedSubjectId(null)
    setMessages([])
    setJobs([])
    setRetryCandidate(null)
    setError(null)
    void loadThread(target.threadId, controller.signal, revision).finally(() => {
      if (!controller.signal.aborted && revision === requestRevisionRef.current) {
        setLoadedSubjectId(subjectId)
      }
    })
  }, [closeRelatedPage, loadThread, subjectId])

  const selectThread = useCallback(async (targetThreadId: string | null) => {
    requestRevisionRef.current += 1
    const revision = requestRevisionRef.current
    requestControllerRef.current?.abort()
    const controller = new AbortController()
    requestControllerRef.current = controller
    setThreadId(targetThreadId)
    setMessages([])
    setJobs([])
    closeRelatedPage()
    setError(null)
    if (targetThreadId) await loadThread(targetThreadId, controller.signal, revision)
  }, [closeRelatedPage, loadThread])

  useEffect(() => {
    const controller = new AbortController()
    requestControllerRef.current = controller
    const revision = ++requestRevisionRef.current
    Promise.all([
      ragService.listThreads(subjectId, controller.signal),
      ragService.getProfile(subjectId, controller.signal),
    ])
      .then(async ([nextThreads, nextProfile]) => {
        if (controller.signal.aborted || revision !== requestRevisionRef.current) return
        setThreads(nextThreads)
        setProfile(nextProfile)
        const latest = nextThreads[0]?.id ?? null
        setThreadId(latest)
        if (latest) await loadThread(latest, controller.signal, revision)
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(apiErrorMessage(caught, copy.askAi.loadFailed))
      })
      .finally(() => {
        if (!controller.signal.aborted && revision === requestRevisionRef.current) {
          setLoadedSubjectId(subjectId)
        }
      })
    return () => {
      controller.abort()
      pageControllerRef.current?.abort()
    }
  }, [closeRelatedPage, loadThread, subjectId])

  const hasActiveJob = !loading && jobs.some((job) => job.status === 'queued' || job.status === 'running')
  useEffect(() => {
    if (!threadId || !hasActiveJob) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let activePollController: AbortController | null = null
    const revision = requestRevisionRef.current
    const poll = async () => {
      const controller = new AbortController()
      activePollController = controller
      await loadThread(threadId, controller.signal, revision)
      if (activePollController === controller) activePollController = null
      if (!stopped) timer = setTimeout(poll, 2_000)
    }
    timer = setTimeout(poll, 2_000)
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
      activePollController?.abort()
    }
  }, [hasActiveJob, loadThread, threadId])

  const createConversation = async (): Promise<RagThread | null> => {
    if (!canSearch(profile)) return null
    setError(null)
    try {
      const thread = await ragService.createThread(subjectId)
      setThreads((current) => [thread, ...current])
      await selectThread(thread.id)
      return thread
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.askAi.loadFailed))
      return null
    }
  }

  const deleteConversation = async () => {
    if (!threadId || !confirm(copy.askAi.confirmDelete)) return
    try {
      await ragService.deleteThread(subjectId, threadId)
      const remaining = threads.filter((thread) => thread.id !== threadId)
      setThreads(remaining)
      await selectThread(remaining[0]?.id ?? null)
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.askAi.deleteFailed))
    }
  }

  const verifyCurrentProfile = async (): Promise<boolean> => {
    try {
      const current = await ragService.getProfile(subjectId)
      if (!profile || !sameProcessorProfile(profile, current)) {
        setProfile(current)
        setError(copy.askAi.profileChanged)
        return false
      }
      if (!canSearch(current)) {
        setProfile(current)
        setError(copy.askAi.profilePaused)
        return false
      }
      return true
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.askAi.profileUnavailable))
      return false
    }
  }

  const submitQuestion = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!canSearch(profile)) return
    const normalized = question.trim()
    if (!normalized || normalized.length > 4_000) return
    setSubmitting(true)
    setError(null)
    if (!await verifyCurrentProfile()) {
      setSubmitting(false)
      return
    }
    let targetThreadId = threadId
    if (!targetThreadId) targetThreadId = (await createConversation())?.id ?? null
    if (!targetThreadId) {
      setSubmitting(false)
      return
    }
    const key = submissionKey ?? crypto.randomUUID()
    setSubmissionKey(key)
    try {
      await ragService.ask(subjectId, targetThreadId, normalized, key)
      setQuestion('')
      setSubmissionKey(null)
      await loadThread(targetThreadId)
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.askAi.submitFailed))
    } finally {
      setSubmitting(false)
    }
  }

  const cancelJob = async (job: RagAnswerJob) => {
    try {
      const updated = await ragService.cancelJob(subjectId, job.thread_id, job.id)
      setJobs((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.askAi.unavailable))
    }
  }

  const retryJob = async (job: RagAnswerJob) => {
    if (!canSearch(profile) || job.ask_policy !== 'related_knowledge_navigation_v8' || retrySubmitting) return
    setRetrySubmitting(true)
    setError(null)
    if (!await verifyCurrentProfile()) {
      setRetrySubmitting(false)
      setRetryCandidate(null)
      return
    }
    const key = retryKeysRef.current.get(job.id) ?? crypto.randomUUID()
    retryKeysRef.current.set(job.id, key)
    try {
      const updated = await ragService.retryJob(subjectId, job.thread_id, job.id, key)
      setJobs((current) => current.map((item) => item.id === updated.id ? updated : item))
      retryKeysRef.current.delete(job.id)
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.askAi.unavailable))
    } finally {
      setRetrySubmitting(false)
      setRetryCandidate(null)
    }
  }

  const openRelatedPage = async (job: RagAnswerJob, excerpt: RagRelatedExcerpt) => {
    pageTriggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const target = { threadId: job.thread_id, jobId: job.id, excerptOrder: excerpt.excerpt_order }
    const revision = ++pageRevisionRef.current
    const threadRevision = requestRevisionRef.current
    pageControllerRef.current?.abort()
    const controller = new AbortController()
    pageControllerRef.current = controller
    pageTargetRef.current = target
    setPageTarget(target)
    setRelatedPage(null)
    setPageError(false)
    setPageLoading(true)
    try {
      const page = await ragService.getRelatedPage(subjectId, job.thread_id, job.id, excerpt.excerpt_order, controller.signal)
      if (!controller.signal.aborted && revision === pageRevisionRef.current && threadRevision === requestRevisionRef.current) {
        setRelatedPage(page)
      }
    } catch {
      if (!controller.signal.aborted && revision === pageRevisionRef.current && threadRevision === requestRevisionRef.current) {
        setPageError(true)
        await loadThread(job.thread_id)
      }
    } finally {
      if (!controller.signal.aborted && revision === pageRevisionRef.current && threadRevision === requestRevisionRef.current) {
        setPageLoading(false)
      }
    }
  }

  const latestJob = loading ? null : jobs[0] ?? null
  const latestQuestion = messages.find((message) => message.id === latestJob?.question_message_id)
  const relatedExcerpts = latestQuestion && !latestQuestion.hidden
    ? visibleRelatedExcerpts(latestJob ?? undefined)
    : []
  const priorJobsByQuestion = new Map(jobs.filter((job) => job.id !== latestJob?.id).map((job) => [job.question_message_id, job]))
  const pageStart = relatedPage?.reference_start
  const pageEnd = relatedPage?.reference_end
  const exactPageReference = Boolean(
    relatedPage && typeof pageStart === 'number' && typeof pageEnd === 'number'
    && Number.isInteger(pageStart) && Number.isInteger(pageEnd)
    && pageStart >= 0 && pageEnd > pageStart && pageEnd <= relatedPage.page_content.length
    && relatedPage.page_content.slice(pageStart, pageEnd).replace(/\s+/g, ' ').trim()
      === relatedPage.source_quote.replace(/\s+/g, ' ').trim(),
  )

  return (
    <section aria-labelledby="ask-ai-heading" className="min-w-0">
      <Card className="min-w-0 overflow-hidden border-slate-200 shadow-sm">
        <CardHeader className="border-b bg-slate-50/70">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <CardTitle id="ask-ai-heading" className="flex items-center gap-2 text-xl">
                <Bot className="h-5 w-5 text-blue-600" aria-hidden="true" />
                {copy.askAi.title}
              </CardTitle>
              <CardDescription className="mt-1 max-w-2xl">{copy.askAi.description}</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" className="min-h-11" disabled={loading || !canSearch(profile)} onClick={() => void createConversation()}>
                <MessageCirclePlus className="mr-1 h-4 w-4" aria-hidden="true" />{copy.askAi.newConversation}
              </Button>
              {!loading && threadId ? <Button type="button" size="sm" variant="ghost" className="min-h-11 text-red-700 hover:bg-red-50 hover:text-red-800" onClick={() => void deleteConversation()}><Trash2 className="mr-1 h-4 w-4" aria-hidden="true" />{copy.askAi.deleteConversation}</Button> : null}
            </div>
          </div>
          {!loading && threads.length > 0 ? (
            <div className="max-w-sm">
              <label htmlFor="rag-thread" className="text-xs font-medium text-slate-600">{copy.askAi.conversation}</label>
              <select id="rag-thread" className="mt-1 min-h-11 w-full rounded-md border bg-white px-3 text-sm" value={threadId ?? ''} onChange={(event) => void selectThread(event.target.value)}>
                {threads.map((thread, index) => <option key={thread.id} value={thread.id}>{copy.askAi.conversation} {threads.length - index}</option>)}
              </select>
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="min-w-0 space-y-4 p-4 sm:p-6">
          {!loading && profile && !canSearch(profile) ? (
            <p className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">{copy.askAi.paused}</p>
          ) : null}
          {!loading && error ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-amber-200 bg-amber-50 p-3" role="alert">
              <span className="min-w-0 break-words text-sm text-amber-900">{error}</span>
              {threadId ? <Button variant="outline" size="sm" onClick={() => void loadThread(threadId)}>{copy.common.retry}</Button> : null}
            </div>
          ) : null}
          {loading ? <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{copy.common.loading}</p> : null}

          <div className="max-h-[34rem] min-h-48 space-y-4 overflow-y-auto overflow-x-hidden rounded-lg border bg-white p-3 sm:p-4" aria-live="polite" aria-label={copy.askAi.conversation}>
            {!loading && messages.map((message) => {
              const questionJob = priorJobsByQuestion.get(message.id)
              const priorRelated = message.hidden ? [] : visibleRelatedExcerpts(questionJob)
              return <Fragment key={message.id}>
              <article className="ml-auto min-w-0 max-w-[90%] sm:max-w-[78%]">
                <div className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-500">
                  <UserRound className="h-3.5 w-3.5" aria-hidden="true" />{copy.askAi.you}
                </div>
                <div className="min-w-0 rounded-2xl bg-blue-600 px-4 py-3 text-sm text-white">
                  <p className="whitespace-pre-wrap break-words">{message.hidden ? copy.askAi.hiddenMessage : message.content}</p>
                </div>
              </article>
              {questionJob?.status === 'failed' ? (
                <div className="min-w-0 rounded border bg-slate-50 p-3 text-sm" role="status">
                  <p className="font-medium">{jobStatusLabel(questionJob)}</p>
                  <p className="mt-1 break-words text-xs text-red-700">{copy.askAi.sourceFailure}</p>
                </div>
              ) : null}
              {questionJob?.status === 'completed' && questionJob.result_kind === 'related_knowledge'
                && priorRelated.length === 0 && !message.hidden ? (
                  <p className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700" role="status">
                    {copy.askAi.relatedUnavailable}{' '}
                    <a className="font-medium text-blue-700 underline" href="#published-knowledge">{copy.askAi.browsePublishedKnowledge}</a>
                  </p>
                ) : null}
              {questionJob?.status === 'completed' && questionJob.result_kind === 'no_match' ? (
                <p className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700" role="status">
                  {questionJob.search_mode === 'not_searched' ? copy.askAi.searchNotRun : copy.askAi.noMatch}{' '}
                  <a className="font-medium text-blue-700 underline" href="#published-knowledge">{copy.askAi.browsePublishedKnowledge}</a>
                </p>
              ) : null}
              {questionJob?.status === 'completed' && questionJob.result_kind === 'clarification_needed' ? (
                <p className="min-w-0 rounded border border-blue-200 bg-blue-50 p-3 text-sm text-slate-800" role="status">
                  {copy.askAi.clarificationNeeded}{' '}
                  <a className="font-medium text-blue-700 underline" href="#published-knowledge">{copy.askAi.browsePublishedKnowledge}</a>
                </p>
              ) : null}
              {questionJob?.search_mode === 'lexical_fallback' ? <p className="rounded border bg-blue-50 p-3 text-sm text-slate-700">{copy.askAi.lexicalFallback}</p> : null}
              <RelatedKnowledgePanel excerpts={priorRelated} headingId={`ask-related-knowledge-${message.id}`} onOpenPage={(excerpt) => { if (questionJob) void openRelatedPage(questionJob, excerpt) }} />
              </Fragment>
            })}
            {!loading && messages.length === 0 ? <p className="py-12 text-center text-sm text-muted-foreground">{threadId ? copy.askAi.noMessages : copy.askAi.noConversation}</p> : null}
          </div>

          {latestJob ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded border bg-slate-50 p-3" role="status" aria-live="polite">
              <div className="min-w-0">
                <p className="text-sm font-medium">{jobStatusLabel(latestJob)}</p>
                {latestJob.search_mode === 'lexical_fallback' ? <p className="mt-1 text-xs text-slate-700">{copy.askAi.lexicalFallback}</p> : null}
                {latestJob.status === 'failed'
                  ? <p className="break-words text-xs text-red-700">{copy.askAi.sourceFailure}</p>
                  : null}
                {latestJob.status === 'completed' && (latestJob.result_kind === 'no_match' || latestJob.result_kind === 'clarification_needed'
                  || (latestJob.result_kind === 'related_knowledge' && relatedExcerpts.length === 0))
                  ? <a className="text-xs font-medium text-blue-700 underline" href="#published-knowledge">{copy.askAi.browsePublishedKnowledge}</a>
                  : null}
                {(latestJob.status === 'queued' || latestJob.status === 'running') ? <p className="text-xs text-muted-foreground">{copy.askAi.polling}</p> : null}
              </div>
              <div className="flex gap-2">
                {latestJob.can_cancel ? <Button type="button" variant="outline" size="sm" onClick={() => void cancelJob(latestJob)}>{copy.askAi.cancel}</Button> : null}
                {latestJob.can_retry && latestJob.ask_policy === 'related_knowledge_navigation_v8' && canSearch(profile) ? <Button type="button" variant="outline" size="sm" onClick={() => setRetryCandidate(latestJob)}>{copy.askAi.retry}</Button> : null}
              </div>
            </div>
          ) : null}

          <RelatedKnowledgePanel excerpts={relatedExcerpts} headingId="ask-related-knowledge-heading" onOpenPage={(excerpt) => { if (latestJob) void openRelatedPage(latestJob, excerpt) }} />

          <form className="space-y-2" onSubmit={(event) => void submitQuestion(event)}>
            <p className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-slate-700">
              {!loading && profile?.ask_policy === 'related_knowledge_navigation_v8'
                && profile.source_judge_transfers_literal_subject_context === true
                && profile.source_judge_transfers_published_content
                && profile.source_judge_transfers_page_images
                && profile.source_judge_provider && profile.source_judge_model
                ? copy.askAi.literalSubjectSourceJudgeDisclosure(
                    profile.active_embedding_provider ?? profile.embedding_provider,
                    profile.active_embedding_model ?? profile.embedding_model,
                    profile.source_judge_provider,
                    profile.source_judge_model,
                    profile.chat_retention_days,
                  )
                : !loading && (profile?.ask_policy === 'related_knowledge_navigation_v4'
                || profile?.ask_policy === 'related_knowledge_navigation_v5'
                || profile?.ask_policy === 'related_knowledge_navigation_v6')
                && profile.source_judge_transfers_published_content
                && profile.source_judge_provider && profile.source_judge_model
                ? copy.askAi.sourceJudgeDisclosure(
                    profile.active_embedding_provider ?? profile.embedding_provider,
                    profile.active_embedding_model ?? profile.embedding_model,
                    profile.source_judge_provider,
                    profile.source_judge_model,
                    profile.chat_retention_days,
                    profile.source_judge_transfers_page_images,
                  )
                : !loading && (profile?.ask_policy === 'related_knowledge_v1'
                || profile?.ask_policy === 'related_knowledge_navigation_v2'
                || profile?.ask_policy === 'related_knowledge_navigation_v3')
                ? copy.askAi.sourceProviderDisclosure(
                    profile.active_embedding_provider ?? profile.embedding_provider,
                    profile.active_embedding_model ?? profile.embedding_model,
                    profile.chat_retention_days,
                  )
                : profile ? copy.askAi.legacyModeUnavailable : copy.askAi.profileUnavailable}
            </p>
            <label htmlFor="rag-question" className="text-sm font-medium">{copy.askAi.questionLabel}</label>
            <textarea id="rag-question" className="min-h-28 w-full resize-y rounded-md border bg-white px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600" maxLength={4_000} value={question} disabled={!canSearch(profile)} placeholder={copy.askAi.questionPlaceholder} onChange={(event) => { setQuestion(event.target.value); setSubmissionKey(null) }} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">{copy.askAi.characterCount(question.length)} · {copy.askAi.historyRetained}</p>
              <Button type="submit" className="min-h-11 min-w-28" disabled={loading || submitting || !question.trim() || hasActiveJob || !canSearch(profile)}>
                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : <Send className="mr-2 h-4 w-4" aria-hidden="true" />}
                {submitting ? copy.askAi.sending : submissionKey ? copy.askAi.retryAsk : copy.askAi.ask}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Dialog open={retryCandidate !== null} onOpenChange={(open) => { if (!open && !retrySubmitting) setRetryCandidate(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.askAi.retryDialogTitle}</DialogTitle>
            <DialogDescription>{retryCandidate?.ask_policy === 'related_knowledge_navigation_v8'
              ? copy.askAi.retryLiteralSubjectDialogDescription
              : retryCandidate?.ask_policy === 'related_knowledge_navigation_v6'
                ? copy.askAi.retryVisualDialogDescription : copy.askAi.retryDialogDescription}</DialogDescription>
          </DialogHeader>
          {retryCandidate ? (
            <div className="space-y-2 text-sm" aria-live="polite">
              <p>{retryCandidate.estimated_additional_cost_microusd === null
                ? copy.askAi.estimatedAdditionalCostUnavailable
                : copy.askAi.estimatedAdditionalCost(formatMicrousd(retryCandidate.estimated_additional_cost_microusd))}</p>
              <p>{retryCandidate.previous_attempt_cost_microusd === null
                ? copy.askAi.previousAttemptCostUnknown
                : copy.askAi.previousAttemptCost(formatMicrousd(retryCandidate.previous_attempt_cost_microusd))}</p>
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={retrySubmitting} onClick={() => setRetryCandidate(null)}>{copy.common.cancel}</Button>
            <Button type="button" disabled={retrySubmitting || !retryCandidate} onClick={() => { if (retryCandidate) void retryJob(retryCandidate) }}>
              {retrySubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
              {copy.askAi.confirmRetry}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={pageTarget !== null} onOpenChange={(open) => { if (!open) closeRelatedPage() }}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] max-w-4xl overflow-y-auto [scrollbar-gutter:stable]" onCloseAutoFocus={(event) => {
          event.preventDefault()
          if (pageTriggerRef.current?.isConnected) pageTriggerRef.current.focus()
          else document.getElementById('rag-question')?.focus()
          pageTriggerRef.current = null
        }}>
          <DialogHeader>
            <DialogTitle>{copy.askAi.pageDialogTitle}</DialogTitle>
            <DialogDescription>{copy.askAi.pageDialogDescription}</DialogDescription>
          </DialogHeader>
          {pageLoading ? <p role="status" className="flex items-center gap-2 text-sm"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{copy.askAi.pageLoading}</p> : null}
          {pageError ? <p role="alert" className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{copy.askAi.pageUnavailable}</p> : null}
          {relatedPage ? (
            <div className="min-w-0 space-y-4 text-sm">
              <p className="break-words font-medium text-blue-800">{copy.askAi.citationLabel(relatedPage.document_title, relatedPage.page_number, relatedPage.section)}</p>
              <section aria-labelledby="related-page-reference" className="min-w-0 rounded border border-amber-200 bg-amber-50 p-3">
                <h3 id="related-page-reference" className="font-semibold">{copy.askAi.pageReference}</h3>
                <blockquote className="mt-2 whitespace-pre-wrap break-words border-l-4 border-amber-300 pl-3">{relatedPage.source_quote}</blockquote>
              </section>
              {pageTarget ? <Suspense fallback={<p role="status">{copy.askAi.pdfLoading}</p>}>
                <OriginalPdfPage key={`${pageTarget.jobId}-${pageTarget.excerptOrder}`} subjectId={subjectId}
                  threadId={pageTarget.threadId} jobId={pageTarget.jobId} excerptOrder={pageTarget.excerptOrder}
                  initialPageNumber={relatedPage.page_number} onAccessChanged={onPageAccessChanged} />
              </Suspense> : null}
              {!exactPageReference ? <p className="text-xs text-amber-900">{copy.askAi.pageReferenceNotLocated}</p> : null}
              <section aria-labelledby="related-page-text" className="min-w-0">
                <h3 id="related-page-text" className="font-semibold">{copy.askAi.citedPageText(relatedPage.page_number)}</h3>
                <p className="mt-2 whitespace-pre-wrap break-words rounded border bg-slate-50 p-3 text-slate-800">
                  {exactPageReference && typeof pageStart === 'number' && typeof pageEnd === 'number' ? (
                    <>
                      {relatedPage.page_content.slice(0, pageStart)}
                      <mark className="bg-yellow-200 text-slate-950">{relatedPage.page_content.slice(pageStart, pageEnd)}</mark>
                      {relatedPage.page_content.slice(pageEnd)}
                    </>
                  ) : relatedPage.page_content}
                </p>
              </section>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  )
}
