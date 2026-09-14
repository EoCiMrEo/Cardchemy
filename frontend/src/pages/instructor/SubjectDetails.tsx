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
import { EditSubjectDialog } from '@/components/subjects/EditSubjectDialog'
import { InviteStudentDialog } from '@/components/subjects/InviteStudentDialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useGenerationJobs } from '@/hooks/useGenerationJobs'
import { apiErrorMessage } from '@/services/errors'
import { flashcardService } from '@/services/flashcards'
import { subjectService } from '@/services/subjects'

interface SubjectSummary {
  id: string
  name: string
  description?: string
}

interface SetSummary {
  id: string
  title: string
  source_pdf_name: string | null
  is_published: boolean
  flashcard_count: number
}

export default function SubjectDetails() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [subject, setSubject] = useState<SubjectSummary | null>(null)
  const [sets, setSets] = useState<SetSummary[]>([])
  const [loading, setLoading] = useState(true)

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
  const [editingSet, setEditingSet] = useState<SetSummary | null>(null)
  const [isEditSetOpen, setIsEditSetOpen] = useState(false)
  const [isInviteOpen, setIsInviteOpen] = useState(false)

  const refreshSets = useCallback(async () => {
    if (!id) return
    const nextSets = await subjectService.getSets(id)
    setSets(nextSets)
  }, [id])

  const handleJobCompleted = useCallback(() => {
    void refreshSets()
  }, [refreshSets])

  const generation = useGenerationJobs(id ?? null, handleJobCompleted)

  const loadData = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const [subjectData, setsData] = await Promise.all([
        subjectService.getSubject(id),
        subjectService.getSets(id),
      ])
      setSubject({ ...subjectData, description: subjectData.description ?? undefined })
      setSets(setsData)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void loadData()
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
      setUploadMessage(`The selected PDF exceeds the ${limits.max_upload_bytes}-byte limit.`)
      return
    }
    if (limits && (cardCount < limits.min_card_count || cardCount > limits.max_card_count)) {
      setUploadMessage('The card count is outside the current server limits.')
      return
    }

    const key = submissionKey ?? crypto.randomUUID()
    setSubmissionKey(key)
    const controller = new AbortController()
    uploadControllerRef.current = controller
    setUploading(true)
    setUploadMessage('Reserving a durable generation job…')
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
      uploadJobIdRef.current = reserved.id
      generation.trackJob(reserved)
      setUploadMessage('Uploading the PDF within the configured byte limit…')
      const queued = await flashcardService.uploadGenerationSource(
        reserved.id,
        file,
        controller.signal,
      )
      generation.trackJob(queued)
      setUploadMessage('Upload complete. The worker will continue in the background.')
      setSubmissionKey(null)
      setFile(null)
      setSetTitle('')
      setFileInputKey((value) => value + 1)
      uploadJobIdRef.current = null
    } catch (error) {
      setUploadMessage(
        apiErrorMessage(
          error,
          'The upload did not finish. Retrying this form will reuse the same job safely.',
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
        setUploadMessage(apiErrorMessage(error, 'The upload stopped, but cancellation failed.'))
      }
    }
    generation.refreshJobs()
  }

  const handleDeleteSubject = async () => {
    if (!id || !confirm('Are you sure? This deletes the subject, its sets, and active jobs.')) return
    setLoading(true)
    try {
      await subjectService.deleteSubject(id)
      navigate('/dashboard')
    } catch {
      setLoading(false)
    }
  }

  const handleDeleteSet = async (setId: string, event: React.MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    if (!id || !confirm('Are you sure you want to delete this flashcard set?')) return
    await subjectService.deleteSet(id, setId)
    setSets((current) => current.filter((set) => set.id !== setId))
  }

  const openEditSet = (event: React.MouseEvent, set: SetSummary) => {
    event.preventDefault()
    event.stopPropagation()
    setEditingSet(set)
    setIsEditSetOpen(true)
  }

  if (loading) return <div className="p-8"><Loader2 className="animate-spin" /></div>

  const limits = generation.limits
  const submissionDisabled = Boolean(
    limits && !limits.generation_available,
  )
  const unavailableMessage = limits?.unavailable_reasons.map((reason) => reason.message).join(' ')

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link to="/dashboard" aria-label="Back to dashboard">
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </Link>
        </Button>
        <div className="flex-1">
          <div className="flex justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">{subject?.name}</h1>
              <p className="text-muted-foreground">{subject?.description || 'No description'}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setIsInviteOpen(true)}>
                <UserPlus className="mr-1 h-4 w-4" aria-hidden="true" /> Invite
              </Button>
              <Button variant="outline" size="sm" onClick={() => setIsEditSubjectOpen(true)}>
                <Pencil className="mr-1 h-4 w-4" aria-hidden="true" /> Edit
              </Button>
              <Button
                variant="destructive"
                size="sm"
                className="bg-red-700 text-white hover:bg-red-800"
                onClick={() => void handleDeleteSubject()}
              >
                <Trash2 className="mr-1 h-4 w-4" aria-hidden="true" /> Delete
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between border-b pb-4">
        <h2 className="text-xl font-semibold">Flashcard Sets</h2>
        <Button onClick={() => setIsUploadOpen((open) => !open)} disabled={uploading}>
          <Upload className="mr-2 h-4 w-4" aria-hidden="true" /> Generate Flashcards Set
        </Button>
      </div>

      {isUploadOpen ? (
        <Card className="border-dashed bg-slate-50">
          <CardHeader>
            <CardTitle>Generate Flashcards from PDF</CardTitle>
            <CardDescription>
              Upload returns quickly; durable processing continues if you leave this page.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={(event) => void handleUpload(event)} className="max-w-md space-y-4">
              <div>
                <label htmlFor="generation-set-title" className="text-sm font-medium">Set Title</label>
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
                  Number of Cards
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
                <label htmlFor="generation-pdf" className="text-sm font-medium">PDF File</label>
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
                    Up to {(limits.max_upload_bytes / 1024 / 1024).toFixed(0)} MB and {limits.max_pages} pages.
                    OCR is {limits.ocr_enabled ? 'enabled' : 'disabled'}.
                    {' '}AI: {limits.ai_provider} / {limits.ai_model}; cost estimates are
                    {limits.ai_pricing_configured ? ' enabled' : ' unavailable until pricing is configured'}.
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

              <div className="flex gap-2">
                <Button type="submit" disabled={uploading || submissionDisabled} className="flex-1">
                  {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                  {uploading ? 'Uploading…' : submissionKey ? 'Retry Upload' : 'Generate with AI'}
                </Button>
                {uploading ? (
                  <Button type="button" variant="outline" onClick={() => void stopUpload()}>
                    Stop
                  </Button>
                ) : null}
              </div>
              {submissionDisabled ? (
                <p className="text-sm text-amber-700" role="alert">
                  {unavailableMessage || 'Generation is temporarily unavailable.'}
                </p>
              ) : null}
            </form>
          </CardContent>
        </Card>
      ) : null}

      {generation.loading ? <p className="text-sm text-muted-foreground">Loading generation jobs…</p> : null}
      {generation.statusMessage ? (
        <p className="text-sm text-amber-700" role="status">{generation.statusMessage}</p>
      ) : null}
      {generation.jobs.length > 0 ? (
        <section aria-labelledby="generation-jobs-heading" className="space-y-3">
          <h2 id="generation-jobs-heading" className="text-lg font-semibold">Generation Jobs</h2>
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

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sets.map((set) => (
          <Card key={set.id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-lg">
                <span className="flex min-w-0 items-center gap-2">
                  <FileText className="h-4 w-4 shrink-0 text-blue-500" aria-hidden="true" />
                  <span className="truncate">{set.title}</span>
                </span>
                <span className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    aria-label={`Edit ${set.title}`}
                    onClick={(event) => openEditSet(event, set)}
                  >
                    <Pencil className="h-3 w-3" aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-red-500 hover:bg-red-50 hover:text-red-600"
                    aria-label={`Delete ${set.title}`}
                    onClick={(event) => void handleDeleteSet(set.id, event)}
                  >
                    <Trash2 className="h-3 w-3" aria-hidden="true" />
                  </Button>
                </span>
              </CardTitle>
              <CardDescription>Generated from {set.source_pdf_name || 'Manual'}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between text-sm">
                <span className={`rounded-full px-2 py-1 ${set.is_published ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                  {set.is_published ? 'Published' : 'Draft'}
                </span>
                <span className="text-muted-foreground">{set.flashcard_count || 0} cards</span>
              </div>
              <Button asChild variant="secondary" className="mt-4 w-full">
                <Link to={`/sets/${set.id}`}>View &amp; Edit Cards</Link>
              </Button>
            </CardContent>
          </Card>
        ))}

        {sets.length === 0 ? (
          <div className="col-span-full py-12 text-center text-muted-foreground">
            <BrainCircuit className="mx-auto mb-4 h-12 w-12 opacity-20" aria-hidden="true" />
            <p>No flashcard sets yet. Upload a PDF to generate one.</p>
          </div>
        ) : null}
      </div>

      {subject ? (
        <EditSubjectDialog
          open={isEditSubjectOpen}
          onOpenChange={setIsEditSubjectOpen}
          subject={subject}
          onSuccess={(updatedSubject) => {
            setSubject({
              ...updatedSubject,
              description: updatedSubject.description ?? undefined,
            })
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
          onOpenChange={setIsEditSetOpen}
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
