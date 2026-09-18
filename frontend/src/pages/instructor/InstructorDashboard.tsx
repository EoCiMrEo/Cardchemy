import { useCallback, useEffect, useRef, useState } from "react"
import { subjectService } from "@/services/subjects"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Plus, BookOpen, Loader2, ArrowRight } from "lucide-react"
import { Link } from "react-router-dom"
import { PageError } from "@/components/feedback/PageError"
import { apiErrorMessage } from "@/services/errors"
import type { Subject } from "@/services/types"
import { copy } from "@/i18n/en"

export default function InstructorDashboard() {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [ready, setReady] = useState(false)
  const loading = !ready
  const loadControllerRef = useRef<AbortController | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [newSubjectName, setNewSubjectName] = useState("")
  const [creatingLoading, setCreatingLoading] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const loadSubjects = useCallback(() => {
    loadControllerRef.current?.abort()
    const controller = new AbortController()
    loadControllerRef.current = controller
    return subjectService.getSubjects(controller.signal).then((data) => {
      if (controller.signal.aborted) return
      setSubjects(data)
      setLoadError(null)
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) setLoadError(apiErrorMessage(caught, copy.dashboard.loadSubjectsFailed))
    }).finally(() => {
      if (!controller.signal.aborted) setReady(true)
    })
  }, [])

  const reloadSubjects = () => {
    setReady(false)
    void loadSubjects()
  }

  useEffect(() => {
    void loadSubjects()
    return () => {
      loadControllerRef.current?.abort()
    }
  }, [loadSubjects])

  const handleCreateSubject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSubjectName.trim()) return

    setCreateError(null)
    try {
      setCreatingLoading(true)
      await subjectService.createSubject({ name: newSubjectName })
      setNewSubjectName("")
      setIsCreating(false)
      setReady(false)
      await loadSubjects()
    } catch (caught: unknown) {
      setCreateError(apiErrorMessage(caught, copy.dashboard.createSubjectFailed))
    } finally {
      setCreatingLoading(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center p-8" role="status" aria-label={copy.common.loading}><Loader2 className="animate-spin" aria-hidden="true" /></div>
  }

  if (loadError) return <PageError message={loadError} onRetry={reloadSubjects} />

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="break-words text-3xl font-bold tracking-tight">{copy.dashboard.instructorTitle}</h1>
          <p className="mt-1 break-words text-muted-foreground">{copy.dashboard.instructorDescription}</p>
        </div>
        <Button className="w-full sm:w-auto" onClick={() => setIsCreating((creating) => !creating)}>
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" /> {copy.dashboard.newSubject}
        </Button>
      </div>

      {isCreating && (
        <Card className="max-w-md animate-accordion-down">
          <CardHeader>
            <CardTitle className="text-lg">{copy.dashboard.createSubject}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateSubject} className="space-y-2">
              <label htmlFor="new-subject-name" className="sr-only">{copy.dashboard.subjectName}</label>
              <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="new-subject-name"
                placeholder={copy.dashboard.subjectPlaceholder}
                value={newSubjectName}
                onChange={(e) => setNewSubjectName(e.target.value)}
                autoFocus
                className="min-w-0 flex-1"
              />
              <Button type="submit" disabled={creatingLoading}>
                {creatingLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                {creatingLoading ? copy.dashboard.creating : copy.dashboard.create}
              </Button>
              </div>
              {createError ? <p className="text-sm text-destructive" role="alert">{createError}</p> : null}
            </form>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {subjects.map((subject) => (
          <Link key={subject.id} to={`/subjects/${subject.id}`} className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
             <Card className="h-full cursor-pointer transition-shadow hover:shadow-md motion-reduce:transition-none">
              <CardHeader className="pb-2">
                <CardTitle className="flex min-w-0 items-start gap-2">
                  <BookOpen className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                  <span className="min-w-0 break-words">{subject.name}</span>
                </CardTitle>
                <CardDescription>
                  {copy.dashboard.subjectCounts(subject.flashcard_set_count, subject.student_count)}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center text-sm text-primary font-medium mt-4">
                  {copy.dashboard.viewDetails} <ArrowRight className="ml-1 h-4 w-4" aria-hidden="true" />
                </div>
              </CardContent>
             </Card>
          </Link>
        ))}

        {subjects.length === 0 && !loading && (
          <div className="col-span-full text-center py-12 text-muted-foreground bg-white rounded-lg border border-dashed">
            <h3 className="text-lg font-medium">{copy.dashboard.noSubjects}</h3>
            <p>{copy.dashboard.noSubjectsDescription}</p>
          </div>
        )}
      </div>
    </div>
  )
}
