import { useCallback, useEffect, useRef, useState } from 'react'
import { BookOpen, FileUp, Loader2, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { knowledgeService } from '@/services/knowledge'
import { ragService } from '@/services/rag'
import type { KnowledgeDocument, RagProfile } from '@/services/types'

interface KnowledgeAreaProps {
  subjectId: string
}

export function KnowledgeArea({ subjectId }: KnowledgeAreaProps) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [profile, setProfile] = useState<RagProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [revisionTarget, setRevisionTarget] = useState<KnowledgeDocument | null>(null)
  const [submissionKey, setSubmissionKey] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState<string | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const pollControllerRef = useRef<AbortController | null>(null)

  const loadDocuments = useCallback(async (signal?: AbortSignal, quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const next = await knowledgeService.listDocuments(subjectId, signal)
      if (signal?.aborted) return
      setDocuments(next)
      setLoadError(null)
    } catch (caught: unknown) {
      if (!signal?.aborted) setLoadError(apiErrorMessage(caught, copy.knowledge.loadFailed))
    } finally {
      if (!signal?.aborted && !quiet) setLoading(false)
    }
  }, [subjectId])

  useEffect(() => {
    const controller = new AbortController()
    ragService.getProfile(subjectId, controller.signal)
      .then((nextProfile) => {
        if (!controller.signal.aborted) setProfile(nextProfile)
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setActionError(apiErrorMessage(caught, copy.knowledge.loadFailed))
        }
      })
    return () => controller.abort()
  }, [subjectId])

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false
    const poll = async () => {
      pollControllerRef.current?.abort()
      const controller = new AbortController()
      pollControllerRef.current = controller
      await loadDocuments(controller.signal, documents.length > 0)
      if (!stopped) timer = setTimeout(poll, 5_000)
    }
    void poll()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
      pollControllerRef.current?.abort()
    }
  }, [loadDocuments, documents.length])

  const resetLogicalUpload = () => {
    setSubmissionKey(null)
    setUploadMessage(null)
  }

  const startRevision = (document: KnowledgeDocument) => {
    setRevisionTarget(document)
    setTitle(document.title)
    setFile(null)
    setFileInputKey((value) => value + 1)
    resetLogicalUpload()
  }

  const cancelRevision = () => {
    setRevisionTarget(null)
    setTitle('')
    setFile(null)
    setFileInputKey((value) => value + 1)
    resetLogicalUpload()
  }

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!file || !title.trim()) return
    const key = submissionKey ?? crypto.randomUUID()
    setSubmissionKey(key)
    setUploading(true)
    setUploadMessage(null)
    setActionError(null)
    const controller = new AbortController()
    try {
      const job = await knowledgeService.createUpload({
        subject_id: subjectId,
        document_id: revisionTarget?.id ?? null,
        title: title.trim(),
        source_pdf_name: file.name,
      }, key, controller.signal)
      await knowledgeService.uploadSource(job.id, file, controller.signal)
      setUploadMessage(copy.knowledge.uploadQueued)
      setSubmissionKey(null)
      setRevisionTarget(null)
      setTitle('')
      setFile(null)
      setFileInputKey((value) => value + 1)
      await loadDocuments(undefined, true)
    } catch (caught: unknown) {
      setUploadMessage(apiErrorMessage(caught, copy.knowledge.uploadFailed))
    } finally {
      setUploading(false)
    }
  }

  const mutate = async (
    document: KnowledgeDocument,
    operation: () => Promise<KnowledgeDocument | void>,
  ) => {
    setBusyDocumentId(document.id)
    setActionError(null)
    try {
      const updated = await operation()
      if (updated) {
        setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item))
      } else {
        setDocuments((current) => current.filter((item) => item.id !== document.id))
      }
    } catch (caught: unknown) {
      setActionError(apiErrorMessage(caught, copy.knowledge.actionFailed))
    } finally {
      setBusyDocumentId(null)
    }
  }

  const hasActiveWork = documents.some((document) =>
    document.index_job?.status === 'queued' || document.index_job?.status === 'running'
    || document.content_revision?.status === 'processing'
    || document.content_revision?.status === 'pending_index',
  )

  return (
    <section aria-labelledby="knowledge-heading" className="space-y-4">
      <div className="flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h2 id="knowledge-heading" className="flex items-center gap-2 text-xl font-semibold">
            <BookOpen className="h-5 w-5 text-blue-600" aria-hidden="true" />
            {copy.knowledge.title}
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{copy.knowledge.description}</p>
        </div>
      </div>

      <Card className="border-blue-100 bg-blue-50/40">
        <CardHeader>
          <CardTitle className="text-base">
            {revisionTarget ? copy.knowledge.reuploadSelected(revisionTarget.title) : copy.knowledge.uploadDocument}
          </CardTitle>
          <CardDescription className="text-slate-600">
            {revisionTarget ? copy.knowledge.reuploadHelp : copy.knowledge.storedPagesHelp}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {profile ? (
            <p className="mb-4 rounded border border-blue-200 bg-white p-3 text-sm text-slate-700">
              {copy.knowledge.providerDisclosure(profile.embedding_provider, profile.embedding_model)}
            </p>
          ) : null}
          <form className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end" onSubmit={(event) => void handleUpload(event)}>
            <div className="min-w-0">
              <label htmlFor="knowledge-title" className="text-sm font-medium">{copy.knowledge.uploadTitle}</label>
              <Input
                id="knowledge-title"
                value={title}
                maxLength={255}
                placeholder={copy.knowledge.uploadTitlePlaceholder}
                onChange={(event) => { setTitle(event.target.value); resetLogicalUpload() }}
                required
              />
            </div>
            <div className="min-w-0">
              <label htmlFor="knowledge-pdf" className="text-sm font-medium">{copy.knowledge.pdfFile}</label>
              <Input
                key={fileInputKey}
                id="knowledge-pdf"
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => { setFile(event.target.files?.[0] ?? null); resetLogicalUpload() }}
                required
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={uploading || !profile?.embedding_available} className="min-h-11">
                {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : <FileUp className="mr-2 h-4 w-4" aria-hidden="true" />}
                {uploading ? copy.knowledge.uploading : submissionKey ? copy.knowledge.retryUpload : copy.knowledge.submitUpload}
              </Button>
              {revisionTarget ? <Button type="button" variant="outline" className="min-h-11" onClick={cancelRevision}>{copy.knowledge.cancelRevision}</Button> : null}
            </div>
          </form>
          {uploadMessage ? <p className="mt-3 text-sm text-blue-800" role="status" aria-live="polite">{uploadMessage}</p> : null}
        </CardContent>
      </Card>

      {actionError ? <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{actionError}</div> : null}
      {loadError ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-amber-200 bg-amber-50 p-3" role="alert">
          <span className="text-sm text-amber-900">{loadError}</span>
          <Button variant="outline" size="sm" onClick={() => void loadDocuments()}>{copy.common.retry}</Button>
        </div>
      ) : null}
      {loading ? <p className="text-sm text-muted-foreground" role="status">{copy.common.loading}</p> : null}
      {hasActiveWork ? <p className="flex items-center gap-2 text-sm text-blue-700" role="status"><RefreshCw className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />{copy.knowledge.polling}</p> : null}

      <div className="space-y-3">
        {documents.map((document) => {
          const content = document.content_revision
          const index = document.index_revision
          const busy = busyDocumentId === document.id
          return (
            <Card key={document.id} className="min-w-0 overflow-hidden">
              <CardContent className="p-4 sm:p-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 items-start gap-2">
                      <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" aria-hidden="true" />
                      <div className="min-w-0">
                        <h3 className="break-words font-semibold">{document.title}</h3>
                        <p className="break-all text-xs text-muted-foreground">{document.source_pdf_name}</p>
                      </div>
                    </div>
                    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                      <div><dt className="font-medium text-slate-500">{copy.knowledge.captureState}</dt><dd>{content ? `${copy.knowledge.state(content.status)} · ${copy.knowledge.revision(content.revision_no)} · ${copy.knowledge.pages(content.page_count)}` : copy.knowledge.state('processing')}</dd></div>
                      <div><dt className="font-medium text-slate-500">{copy.knowledge.indexState}</dt><dd>{index ? `${copy.knowledge.state(index.status)} · ${copy.knowledge.chunks(index.embedded_count, index.chunk_count)}` : copy.knowledge.state('pending_index')}</dd></div>
                      <div><dt className="font-medium text-slate-500">{copy.knowledge.reviewState}</dt><dd>{content?.reviewed_at ? copy.knowledge.reviewed : copy.knowledge.awaitingReview}</dd></div>
                      <div><dt className="font-medium text-slate-500">{copy.knowledge.publicationState}</dt><dd className={content?.published_at ? 'font-medium text-emerald-700' : 'text-slate-700'}>{content?.published_at ? copy.knowledge.published : copy.knowledge.private}</dd></div>
                    </dl>
                    {content?.error_message || index?.error_message || document.index_job?.error_message ? (
                      <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-800" role="alert">{content?.error_message ?? index?.error_message ?? document.index_job?.error_message}</p>
                    ) : null}
                    {document.requires_pdf_reupload ? <p className="mt-3 text-sm text-amber-800">{copy.knowledge.rawSourceUnavailable}</p> : <p className="mt-3 text-xs text-muted-foreground">{copy.knowledge.storedPagesHelp}</p>}
                  </div>
                  <div className="flex max-w-full flex-wrap gap-2 xl:max-w-sm xl:justify-end">
                    {document.can_review_publish ? <Button size="sm" disabled={busy} onClick={() => void mutate(document, () => knowledgeService.reviewPublish(subjectId, document.id))}>{copy.knowledge.reviewPublish}</Button> : null}
                    {document.can_unpublish ? <Button size="sm" variant="outline" disabled={busy} onClick={() => { if (confirm(copy.knowledge.confirmUnpublish)) void mutate(document, () => knowledgeService.unpublish(subjectId, document.id)) }}>{copy.knowledge.unpublish}</Button> : null}
                    {document.can_retry_index ? <Button size="sm" variant="outline" disabled={busy} onClick={() => void mutate(document, () => knowledgeService.retryIndex(subjectId, document.id))}><RefreshCw className="mr-1 h-4 w-4" aria-hidden="true" />{copy.knowledge.retryIndex}</Button> : null}
                    <Button size="sm" variant="outline" disabled={busy || uploading} onClick={() => startRevision(document)}>{copy.knowledge.uploadRevision}</Button>
                    <Button size="sm" variant="ghost" className="text-red-700 hover:bg-red-50 hover:text-red-800" disabled={busy} onClick={() => { if (confirm(copy.knowledge.confirmRemove)) void mutate(document, () => knowledgeService.remove(subjectId, document.id)) }}><Trash2 className="mr-1 h-4 w-4" aria-hidden="true" />{copy.knowledge.remove}</Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
        {!loading && documents.length === 0 ? <div className="rounded border border-dashed p-8 text-center text-sm text-muted-foreground">{copy.knowledge.empty}</div> : null}
      </div>
    </section>
  )
}
