import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  BrainCircuit,
  ChevronLeft,
  FileText,
  Loader2,
  Pencil,
  Trash2,
  Upload,
  UserPlus,
} from 'lucide-react'

import { GenerationJobCard } from '@/components/generation/GenerationJobCard'
import { EditSetDialog } from '@/components/sets/EditSetDialog'
import { KnowledgeArea } from '@/components/knowledge/KnowledgeArea'
import { AskAiPanel } from '@/components/rag/AskAiPanel'
import { EditSubjectDialog } from '@/components/subjects/EditSubjectDialog'
import { InviteStudentDialog } from '@/components/subjects/InviteStudentDialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useGenerationJobs } from '@/hooks/useGenerationJobs'
import { apiErrorMessage } from '@/services/errors'
import { flashcardService } from '@/services/flashcards'
import { subjectService } from '@/services/subjects'
import type { FlashcardSet, Subject } from '@/services/types'
import { PageError } from '@/components/feedback/PageError'
import { copy } from '@/i18n/en'

export default function SubjectDetails() {
  const { id } = useParams<{ id: string }>()
  return <SubjectDetailsContent key={id} />
}

function SubjectDetailsContent() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [subject, setSubject] = useState<Subject | null>(null)
  const [sets, setSets] = useState<FlashcardSet[]>([])
  const [loadedId, setLoadedId] = useState<string | null>(null)
  const loading = loadedId !== id
  const loadControllerRef = useRef<AbortController | null>(null)
  const refreshControllerRef = useRef<AbortController | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [setTitle, setSetTitle] = useState('')
  const [cardCount, setCardCount] = useState(20)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState<string | null>(null)
  const [submissionKey, setSubmissionKey] = useState<string | null>(null)
  const uploadControllerRef = useRef<AbortController | null>(null)
  const uploadJobIdRef = useRef<string | null>(null)

  const [isEditSubjectOpen, setIsEditSubjectOpen] = useState(false)
  const [editingSet, setEditingSet] = useState<FlashcardSet | null>(null)
  const [isEditSetOpen, setIsEditSetOpen] = useState(false)
  const [isInviteOpen, setIsInviteOpen] = useState(false)

  const refreshSets = useCallback(async () => {
    if (!id) return
    refreshControllerRef.current?.abort()
    const controller = new AbortController()
    refreshControllerRef.current = controller
    try {
      const nextSets = await subjectService.getSets(id, controller.signal)
      if (!controller.signal.aborted) setSets(nextSets)
    } catch (caught: unknown) {
      if (!controller.signal.aborted) setActionError(apiErrorMessage(caught, copy.subject.loadFailed))
    }
  }, [id])

  const handleJobCompleted = useCallback(() => {
    void refreshSets()
  }, [refreshSets])

  const generation = useGenerationJobs(id ?? null, handleJobCompleted)

  const loadData = useCallback(() => {
    if (!id) return Promise.resolve()
    loadControllerRef.current?.abort()
    const controller = new AbortController()
    loadControllerRef.current = controller
    return Promise.all([
      subjectService.getSubject(id, controller.signal),
      subjectService.getSets(id, controller.signal),
    ]).then(([subjectData, setsData]) => {
      if (controller.signal.aborted) return
      setLoadError(null)
      setSubject(subjectData)
      setSets(setsData)
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) setLoadError(apiErrorMessage(caught, copy.subject.loadFailed))
    }).finally(() => {
      if (!controller.signal.aborted) setLoadedId(id)
    })
  }, [id])

  const reloadData = () => {
    setLoadedId(null)
    void loadData()
  }

  useEffect(() => {
    void loadData()
    return () => {
      loadControllerRef.current?.abort()
      refreshControllerRef.current?.abort()
    }
  }, [loadData])

  useEffect(() => () => uploadControllerRef.current?.abort(), [])

  const resetLogicalSubmission = () => {
    setSubmissionKey(null)
    setUploadMessage(null)
  }

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!id || !file || !setTitle.trim() || uploading) return
    const limits = generation.limits
    if (limits && file.size > limits.max_upload_bytes) {
      setUploadMessage(copy.subject.selectedFileTooLarge(limits.max_upload_bytes))
      return
    }
    if (limits && (cardCount < limits.min_card_count || cardCount > limits.max_card_count)) {
      setUploadMessage(copy.subject.cardCountOutsideLimits)
      return
    }

    const key = submissionKey ?? crypto.randomUUID()
    setSubmissionKey(key)
    const controller = new AbortController()
    uploadControllerRef.current = controller
    setUploading(true)
    setUploadMessage(copy.subject.reservingJob)
    try {
      const reserved = await flashcardService.createGenerationJob(
        {
          subject_id: id,
          set_title: setTitle,
          source_pdf_name: file.name,
          card_count: cardCount,
        },
        key,
        controller.signal,
      )
      if (controller.signal.aborted) return
      uploadJobIdRef.current = reserved.id
      generation.trackJob(reserved)
      setUploadMessage(copy.subject.uploadingPdf)
      const queued = await flashcardService.uploadGenerationSource(
        reserved.id,
        file,
        controller.signal,
      )
      if (controller.signal.aborted) return
      generation.trackJob(queued)
      setUploadMessage(copy.subject.uploadComplete)
      setSubmissionKey(null)
      setFile(null)
      setSetTitle('')
      setFileInputKey((value) => value + 1)
      uploadJobIdRef.current = null
    } catch (error) {
      if (controller.signal.aborted) return
      setUploadMessage(
        apiErrorMessage(
          error,
          copy.subject.uploadFailed,
        ),
      )
      generation.refreshJobs()
    } finally {
      uploadControllerRef.current = null
      setUploading(false)
    }
  }

  const stopUpload = async () => {
    uploadControllerRef.current?.abort()
    const jobId = uploadJobIdRef.current
    if (jobId) {
      try {
        await generation.cancelJob(jobId)
      } catch (error) {
        setUploadMessage(apiErrorMessage(error, copy.subject.uploadStoppedCancelFailed))
      }
    }
    generation.refreshJobs()
  }

  const handleDeleteSubject = async () => {
    if (!id || !confirm(copy.subject.confirmDelete)) return
    setActionError(null)
    setLoadedId(null)
    try {
      await subjectService.deleteSubject(id)
      navigate('/dashboard')
    } catch (caught: unknown) {
      setActionError(apiErrorMessage(caught, copy.subject.deleteFailed))
      setLoadedId(id)
    }
  }

  const handleDeleteSet = async (setId: string, event: React.MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    if (!id || !confirm(copy.subject.confirmDeleteSet)) return
    setActionError(null)
    try {
      await subjectService.deleteSet(id, setId)
      setSets((current) => current.filter((set) => set.id !== setId))
    } catch (caught: unknown) {
      setActionError(apiErrorMessage(caught, copy.subject.deleteSetFailed))
    }
  }

  const openEditSet = (event: React.MouseEvent, set: FlashcardSet) => {
    event.preventDefault()
    event.stopPropagation()
    setEditingSet(set)
    setIsEditSetOpen(true)
  }

  if (loading) return <div className="p-8" role="status" aria-label={copy.common.loading}><Loader2 className="animate-spin" aria-hidden="true" /></div>

  if (loadError) return <PageError message={loadError} onRetry={reloadData} />

  const limits = generation.limits
  const submissionDisabled = Boolean(
    limits && !limits.generation_available,
  )
  const unavailableMessage = limits?.unavailable_reasons.map((reason) => reason.message).join(' ')

  return (
    <div className="space-y-6">
      <div className="flex min-w-0 items-start gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link to="/dashboard" aria-label={copy.common.backToDashboard}>
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </Link>
        </Button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h1 className="break-words text-2xl font-bold">{subject?.name}</h1>
              <p className="break-words text-muted-foreground">{subject?.description || copy.common.noDescription}</p>
            </div>
            <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end">
              <Button variant="outline" size="sm" onClick={() => setIsInviteOpen(true)}>
                <UserPlus className="mr-1 h-4 w-4" aria-hidden="true" /> {copy.subject.invite}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setIsEditSubjectOpen(true)}>
                <Pencil className="mr-1 h-4 w-4" aria-hidden="true" /> {copy.subject.edit}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                className="bg-red-700 text-white hover:bg-red-800"
                onClick={() => void handleDeleteSubject()}
              >
                <Trash2 className="mr-1 h-4 w-4" aria-hidden="true" /> {copy.common.delete}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {actionError ? (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{actionError}</div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <h2 className="text-xl font-semibold">{copy.subject.flashcardSets}</h2>
        <Button onClick={() => setIsUploadOpen((open) => !open)} disabled={uploading}>
          <Upload className="mr-2 h-4 w-4" aria-hidden="true" /> {copy.subject.generateSet}
        </Button>
      </div>

      {isUploadOpen ? (
        <Card className="border-dashed bg-slate-50">
          <CardHeader>
            <CardTitle>{copy.subject.generationTitle}</CardTitle>
            <CardDescription>
              {copy.subject.generationDescription}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={(event) => void handleUpload(event)} className="max-w-md space-y-4">
              <div>
                <label htmlFor="generation-set-title" className="text-sm font-medium">{copy.subject.setTitle}</label>
                <Input
                  id="generation-set-title"
                  value={setTitle}
                  onChange={(event) => {
                    setSetTitle(event.target.value)
                    resetLogicalSubmission()
                  }}
                  maxLength={255}
                  required
                />
              </div>
              <div>
                <label htmlFor="generation-card-count" className="text-sm font-medium">
                  {copy.subject.numberOfCards}
                </label>
                <Input
                  id="generation-card-count"
                  type="number"
                  min={limits?.min_card_count ?? 1}
                  max={limits?.max_card_count ?? 100}
                  value={cardCount}
                  onChange={(event) => {
                    setCardCount(Number(event.target.value))
                    resetLogicalSubmission()
                  }}
                  required
                />
              </div>
              <div>
                <label htmlFor="generation-pdf" className="text-sm font-medium">{copy.subject.pdfFile}</label>
                <Input
                  key={fileInputKey}
                  id="generation-pdf"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] ?? null)
                    resetLogicalSubmission()
                  }}
                  required
                />
                {limits ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {copy.subject.fileLimit((limits.max_upload_bytes / 1024 / 1024).toFixed(0), limits.max_pages)}{' '}
                    {copy.subject.ocrStatus(limits.ocr_enabled)}{' '}
                    {copy.subject.aiStatus(limits.ai_provider, limits.ai_model, limits.ai_pricing_configured)}
                  </p>
                ) : null}
              </div>

              {uploadMessage ? (
                <p
                  className="rounded bg-blue-50 p-2 text-sm text-blue-700"
                  role={uploading ? 'status' : 'alert'}
                  aria-live="polite"
                >
                  {uploadMessage}
                </p>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={uploading || submissionDisabled} className="flex-[1_1_12rem]">
                  {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                  {uploading ? copy.subject.uploading : submissionKey ? copy.subject.retryUpload : copy.subject.generateWithAi}
                </Button>
                {uploading ? (
                  <Button type="button" variant="outline" onClick={() => void stopUpload()}>
                    {copy.subject.stop}
                  </Button>
                ) : null}
              </div>
              {submissionDisabled ? (
                <p className="text-sm text-amber-700" role="alert">
                  {unavailableMessage || copy.subject.generationUnavailable}
                </p>
              ) : null}
            </form>
          </CardContent>
        </Card>
      ) : null}

      {generation.loading ? <p className="text-sm text-muted-foreground">{copy.subject.loadingJobs}</p> : null}
      {generation.statusMessage ? (
        <p className="text-sm text-amber-700" role="status">{generation.statusMessage}</p>
      ) : null}
      {generation.jobs.length > 0 ? (
        <section aria-labelledby="generation-jobs-heading" className="space-y-3">
          <h2 id="generation-jobs-heading" className="text-lg font-semibold">{copy.subject.generationJobs}</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {generation.jobs.map((job) => (
              <GenerationJobCard
                key={job.id}
                job={job}
                onCancel={generation.cancelJob}
                onRetry={generation.retryJob}
              />
            ))}
          </div>
        </section>
      ) : null}

      {id ? <KnowledgeArea subjectId={id} /> : null}

      {id ? <AskAiPanel subjectId={id} /> : null}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sets.map((set) => (
          <Card key={set.id} className="min-w-0">
            <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
              <div className="min-w-0 space-y-1.5">
                <CardTitle className="flex min-w-0 items-start gap-2 text-lg">
                  <span className="flex min-w-0 items-start gap-2">
                    <FileText className="h-4 w-4 shrink-0 text-blue-500" aria-hidden="true" />
                    <span className="break-words">{set.title}</span>
                  </span>
                </CardTitle>
                <CardDescription className="break-words">{copy.subject.generatedFrom(set.source_pdf_name || copy.subject.manualSource)}</CardDescription>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={copy.subject.editSet(set.title)}
                  onClick={(event) => openEditSet(event, set)}
                >
                  <Pencil className="h-3 w-3" aria-hidden="true" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-red-700 hover:bg-red-50 hover:text-red-800"
                  aria-label={copy.subject.deleteSet(set.title)}
                  onClick={(event) => void handleDeleteSet(set.id, event)}
                >
                  <Trash2 className="h-3 w-3" aria-hidden="true" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className={`rounded-full px-2 py-1 ${set.is_published ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                  {set.is_published ? copy.subject.published : copy.subject.draft}
                </span>
                <span className="text-muted-foreground">{copy.subject.cardCount(set.flashcard_count)}</span>
              </div>
              <Button asChild variant="secondary" className="mt-4 w-full">
                <Link to={`/sets/${set.id}`}>{copy.subject.viewEditCards}</Link>
              </Button>
            </CardContent>
          </Card>
        ))}

        {sets.length === 0 ? (
          <div className="col-span-full py-12 text-center text-muted-foreground">
            <BrainCircuit className="mx-auto mb-4 h-12 w-12 opacity-20" aria-hidden="true" />
            <p>{copy.subject.noSets}</p>
          </div>
        ) : null}
      </div>

      {subject ? (
        <EditSubjectDialog
          open={isEditSubjectOpen}
          onOpenChange={setIsEditSubjectOpen}
          subject={subject}
          onSuccess={(updatedSubject) => {
            setSubject(updatedSubject)
          }}
        />
      ) : null}
      {subject ? (
        <InviteStudentDialog
          open={isInviteOpen}
          onOpenChange={setIsInviteOpen}
          subjectId={id!}
          subjectName={subject.name}
        />
      ) : null}
      {editingSet ? (
        <EditSetDialog
          open={isEditSetOpen}
          onOpenChange={(open) => {
            setIsEditSetOpen(open)
            if (!open) setEditingSet(null)
          }}
          subjectId={id!}
          set={editingSet}
          onSuccess={() => {
            void refreshSets()
            setEditingSet(null)
          }}
        />
      ) : null}
    </div>
  )
}
