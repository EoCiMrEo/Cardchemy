import { useCallback, useEffect, useRef, useState } from "react"
import { subjectService } from "@/services/subjects"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { BookOpen, Loader2, Play, UserPlus } from "lucide-react"
import { Link } from "react-router-dom"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { PageError } from "@/components/feedback/PageError"
import { apiErrorMessage } from "@/services/errors"
import type { Subject } from "@/services/types"
import { copy } from "@/i18n/en"

export default function StudentDashboard() {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [ready, setReady] = useState(false)
  const loading = !ready
  const loadControllerRef = useRef<AbortController | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [joinDialogOpen, setJoinDialogOpen] = useState(false)
  const [joinToken, setJoinToken] = useState("")
  const [joining, setJoining] = useState(false)
  const [joinError, setJoinError] = useState("")
  const joinControllerRef = useRef<AbortController | null>(null)

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
      joinControllerRef.current?.abort()
      joinControllerRef.current = null
    }
  }, [loadSubjects])

  const handleJoinCourse = async () => {
    if (!joinToken.trim()) return
    
    setJoining(true)
    setJoinError("")
    const controller = new AbortController()
    joinControllerRef.current = controller
    
    try {
      await subjectService.joinCourse(joinToken.trim(), controller.signal)
      if (controller.signal.aborted) return
      setJoinDialogOpen(false)
      setJoinToken("")
      setReady(false)
      await loadSubjects() // Refresh the list
    } catch (caught: unknown) {
      if (!controller.signal.aborted) {
        setJoinError(apiErrorMessage(caught, copy.join.failed))
      }
    } finally {
      if (joinControllerRef.current === controller) {
        joinControllerRef.current = null
        setJoining(false)
      }
    }
  }

  const changeJoinDialog = (open: boolean) => {
    setJoinDialogOpen(open)
    if (!open) {
      joinControllerRef.current?.abort()
      joinControllerRef.current = null
      setJoining(false)
    }
  }

  if (loading) return <div className="p-8" role="status" aria-label={copy.common.loading}><Loader2 className="animate-spin" aria-hidden="true" /></div>

  if (loadError) return <PageError message={loadError} onRetry={reloadSubjects} />

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="break-words text-3xl font-bold tracking-tight">{copy.dashboard.studentTitle}</h1>
          <p className="mt-1 break-words text-muted-foreground">{copy.dashboard.studentDescription}</p>
        </div>
        
        <Dialog open={joinDialogOpen} onOpenChange={changeJoinDialog}>
          <DialogTrigger asChild>
            <Button className="w-full gap-2 sm:w-auto">
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              {copy.dashboard.joinCourse}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{copy.dashboard.joinDialogTitle}</DialogTitle>
              <DialogDescription>
                {copy.dashboard.joinDialogDescription}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <label htmlFor="join-token" className="sr-only">{copy.dashboard.inviteToken}</label>
              <Input
                id="join-token"
                placeholder={copy.dashboard.inviteTokenPlaceholder}
                value={joinToken}
                onChange={(e) => setJoinToken(e.target.value)}
                disabled={joining}
              />
              {joinError ? (
                <p className="text-sm text-destructive" role="alert">{joinError}</p>
              ) : null}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => changeJoinDialog(false)} disabled={joining}>
                {copy.common.cancel}
              </Button>
              <Button onClick={handleJoinCourse} disabled={joining || !joinToken.trim()}>
                {joining ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                {copy.dashboard.joinCourse}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {subjects.map((subject) => (
          <Link key={subject.id} to={`/subjects/${subject.id}`} className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
             <Card className="h-full cursor-pointer border-l-4 border-l-primary transition-shadow hover:shadow-md motion-reduce:transition-none">
              <CardHeader className="pb-2">
                <CardTitle className="flex min-w-0 items-start gap-2">
                  <BookOpen className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                  <span className="min-w-0 break-words">{subject.name}</span>
                </CardTitle>
                <CardDescription className="break-words">
                  {subject.description || copy.common.noDescription}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center text-sm font-medium mt-4 bg-primary/5 text-primary p-2 rounded justify-between">
                  <span>{copy.dashboard.startLearning}</span>
                  <Play className="h-4 w-4 fill-current" aria-hidden="true" />
                </div>
              </CardContent>
             </Card>
          </Link>
        ))}

        {subjects.length === 0 && !loading && (
          <div className="col-span-full text-center py-12 text-muted-foreground bg-white rounded-lg border border-dashed">
            <h3 className="text-lg font-medium">{copy.dashboard.noCourses}</h3>
            <p className="mt-2">{copy.dashboard.noCoursesDescription}</p>
          </div>
        )}
      </div>
    </div>
  )
}
