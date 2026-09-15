import { useCallback, useEffect, useState } from "react"
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
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [newSubjectName, setNewSubjectName] = useState("")
  const [creatingLoading, setCreatingLoading] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const loadSubjects = useCallback(async () => {
    setLoadError(null)
    try {
      setLoading(true)
      const data = await subjectService.getSubjects()
      setSubjects(data)
    } catch (caught: unknown) {
      setLoadError(apiErrorMessage(caught, copy.dashboard.loadSubjectsFailed))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadSubjects()
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
      await loadSubjects()
    } catch (caught: unknown) {
      setCreateError(apiErrorMessage(caught, copy.dashboard.createSubjectFailed))
    } finally {
      setCreatingLoading(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center p-8" role="status" aria-label={copy.common.loading}><Loader2 className="animate-spin" /></div>
  }

  if (loadError) return <PageError message={loadError} onRetry={() => void loadSubjects()} />

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{copy.dashboard.instructorTitle}</h1>
          <p className="text-muted-foreground mt-1">{copy.dashboard.instructorDescription}</p>
        </div>
        <Button onClick={() => setIsCreating(!isCreating)}>
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
              <div className="flex gap-2">
              <Input
                id="new-subject-name"
                placeholder={copy.dashboard.subjectPlaceholder}
                value={newSubjectName}
                onChange={(e) => setNewSubjectName(e.target.value)}
                autoFocus
              />
              <Button type="submit" disabled={creatingLoading}>
                {creatingLoading ? <Loader2 className="animate-spin" aria-hidden="true" /> : copy.dashboard.create}
              </Button>
              </div>
              {createError ? <p className="text-sm text-destructive" role="alert">{createError}</p> : null}
            </form>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {subjects.map((subject) => (
          <Link key={subject.id} to={`/subjects/${subject.id}`}>
             <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-primary" aria-hidden="true" />
                  {subject.name}
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
