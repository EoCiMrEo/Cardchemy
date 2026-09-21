import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, FileText, Loader2, MessageCirclePlus, Send, Trash2, UserRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { ragService } from '@/services/rag'
import type { RagAnswerJob, RagMessage, RagProfile, RagSource, RagThread } from '@/services/types'

interface AskAiPanelProps {
  subjectId: string
}

export function AskAiPanel({ subjectId }: AskAiPanelProps) {
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
  const [selectedSource, setSelectedSource] = useState<RagSource | null>(null)
  const requestRevisionRef = useRef(0)
  const requestControllerRef = useRef<AbortController | null>(null)
  const retryKeysRef = useRef(new Map<string, string>())
  const loading = loadedSubjectId !== subjectId

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
      setMessages(history.messages)
      setJobs(nextJobs)
      setError(null)
    } catch (caught: unknown) {
      if (!signal?.aborted && revision === requestRevisionRef.current) {
        setError(apiErrorMessage(caught, copy.askAi.loadFailed))
      }
    }
  }, [subjectId])

  const selectThread = useCallback(async (targetThreadId: string | null) => {
    requestRevisionRef.current += 1
    const revision = requestRevisionRef.current
    requestControllerRef.current?.abort()
    const controller = new AbortController()
    requestControllerRef.current = controller
    setThreadId(targetThreadId)
    setMessages([])
    setJobs([])
    setError(null)
    if (targetThreadId) await loadThread(targetThreadId, controller.signal, revision)
  }, [loadThread])

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
    return () => controller.abort()
  }, [loadThread, subjectId])

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

  const submitQuestion = async (event: React.FormEvent) => {
    event.preventDefault()
    const normalized = question.trim()
    if (!normalized || normalized.length > 4_000) return
    setSubmitting(true)
    setError(null)
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
    const key = retryKeysRef.current.get(job.id) ?? crypto.randomUUID()
    retryKeysRef.current.set(job.id, key)
    try {
      const updated = await ragService.retryJob(subjectId, job.thread_id, job.id, key)
      setJobs((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.askAi.unavailable))
    }
  }

  const latestJob = loading ? null : jobs[0] ?? null
  const visibleSource = loading ? null : selectedSource

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
              <Button type="button" size="sm" variant="outline" className="min-h-11" disabled={loading} onClick={() => void createConversation()}>
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
          {!loading && error ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-amber-200 bg-amber-50 p-3" role="alert">
              <span className="min-w-0 break-words text-sm text-amber-900">{error}</span>
              {threadId ? <Button variant="outline" size="sm" onClick={() => void loadThread(threadId)}>{copy.common.retry}</Button> : null}
            </div>
          ) : null}
          {loading ? <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{copy.common.loading}</p> : null}

          <div className="max-h-[34rem] min-h-48 space-y-4 overflow-y-auto overflow-x-hidden rounded-lg border bg-white p-3 sm:p-4" aria-live="polite" aria-label={copy.askAi.conversation}>
            {!loading && messages.map((message) => (
              <article key={message.id} className={`min-w-0 ${message.role === 'user' ? 'ml-auto max-w-[90%] sm:max-w-[78%]' : 'mr-auto max-w-[96%] sm:max-w-[88%]'}`}>
                <div className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-500">
                  {message.role === 'user' ? <UserRound className="h-3.5 w-3.5" aria-hidden="true" /> : <Bot className="h-3.5 w-3.5" aria-hidden="true" />}
                  {message.role === 'user' ? copy.askAi.you : copy.askAi.assistant}
                </div>
                <div className={`min-w-0 rounded-2xl px-4 py-3 text-sm ${message.role === 'user' ? 'bg-blue-600 text-white' : 'border bg-slate-50 text-slate-900'}`}>
                  <p className="whitespace-pre-wrap break-words">{message.hidden ? copy.askAi.hiddenMessage : message.content}</p>
                  {message.outcome === 'abstained' ? <p className="mt-2 text-xs font-medium text-amber-800">{copy.askAi.abstained}</p> : null}
                </div>
                {!message.hidden && message.sources.length > 0 ? (
                  <div className="mt-2 flex min-w-0 flex-wrap gap-2" aria-label={copy.askAi.citations}>
                    {message.sources.map((source) => (
                      <button key={`${message.id}-${source.citation_order}`} type="button" className="min-h-11 max-w-full rounded-full border border-blue-200 bg-blue-50 px-3 py-2 text-left text-xs font-medium text-blue-800 hover:bg-blue-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 motion-reduce:transition-none" onClick={() => setSelectedSource(source)}>
                        <FileText className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
                        <span className="break-words">{copy.askAi.citationLabel(source.document_title, source.page_number, source.section)}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
            {!loading && messages.length === 0 ? <p className="py-12 text-center text-sm text-muted-foreground">{threadId ? copy.askAi.noMessages : copy.askAi.noConversation}</p> : null}
          </div>

          {latestJob ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded border bg-slate-50 p-3" role="status" aria-live="polite">
              <div className="min-w-0">
                <p className="text-sm font-medium">{latestJob.status === 'queued' ? copy.askAi.queued : latestJob.status === 'running' ? copy.askAi.running : latestJob.status === 'completed' ? copy.askAi.completed : latestJob.status === 'failed' ? copy.askAi.failed : copy.askAi.cancelled}</p>
                {latestJob.error_message ? <p className="break-words text-xs text-red-700">{latestJob.error_message}</p> : null}
                {(latestJob.status === 'queued' || latestJob.status === 'running') ? <p className="text-xs text-muted-foreground">{copy.askAi.polling}</p> : null}
              </div>
              <div className="flex gap-2">
                {latestJob.can_cancel ? <Button type="button" variant="outline" size="sm" onClick={() => void cancelJob(latestJob)}>{copy.askAi.cancel}</Button> : null}
                {latestJob.can_retry ? <Button type="button" variant="outline" size="sm" onClick={() => void retryJob(latestJob)}>{copy.askAi.retry}</Button> : null}
              </div>
            </div>
          ) : null}

          <form className="space-y-2" onSubmit={(event) => void submitQuestion(event)}>
            <p className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-slate-700">
              {!loading && profile
                ? copy.askAi.providerDisclosure(profile.answer_provider, profile.answer_model, profile.chat_retention_days)
                : copy.askAi.profileUnavailable}
            </p>
            <label htmlFor="rag-question" className="text-sm font-medium">{copy.askAi.questionLabel}</label>
            <textarea id="rag-question" className="min-h-28 w-full resize-y rounded-md border bg-white px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600" maxLength={4_000} value={question} placeholder={copy.askAi.questionPlaceholder} onChange={(event) => { setQuestion(event.target.value); setSubmissionKey(null) }} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">{copy.askAi.characterCount(question.length)} · {copy.askAi.historyRetained}</p>
              <Button type="submit" className="min-h-11 min-w-28" disabled={loading || submitting || !question.trim() || hasActiveJob || !profile?.answer_available}>
                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : <Send className="mr-2 h-4 w-4" aria-hidden="true" />}
                {submitting ? copy.askAi.sending : submissionKey ? copy.askAi.retryAsk : copy.askAi.ask}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Dialog open={visibleSource !== null} onOpenChange={(open) => { if (!open) setSelectedSource(null) }}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{copy.askAi.citationDialogTitle}</DialogTitle>
            <DialogDescription>{copy.askAi.citationDialogDescription}</DialogDescription>
          </DialogHeader>
          {visibleSource ? <div className="min-w-0 space-y-4 text-sm"><p className="font-medium text-blue-800">{copy.askAi.citationLabel(visibleSource.document_title, visibleSource.page_number, visibleSource.section)}</p><div><h3 className="font-semibold">{copy.askAi.supportedClaim}</h3><p className="mt-1 whitespace-pre-wrap break-words text-slate-700">{visibleSource.claim_text}</p></div><div><h3 className="font-semibold">{copy.askAi.sourceQuote}</h3><blockquote className="mt-1 whitespace-pre-wrap break-words border-l-4 border-blue-200 bg-blue-50 p-3 text-slate-800">{visibleSource.source_quote}</blockquote></div></div> : <p>{copy.askAi.sourceUnavailable}</p>}
        </DialogContent>
      </Dialog>
    </section>
  )
}
