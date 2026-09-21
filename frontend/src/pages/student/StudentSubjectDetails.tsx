import { useCallback, useEffect, useRef, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { subjectService } from "@/services/subjects"
import { studyService } from "@/services/study"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { ChevronLeft, FileText, Brain, Loader2, CheckCircle2, Trophy } from "lucide-react"
import type { FlashcardSet, SetProgress, Subject } from "@/services/types"
import { PageError } from "@/components/feedback/PageError"
import { apiErrorMessage } from "@/services/errors"
import { copy } from "@/i18n/en"
import { AskAiPanel } from "@/components/rag/AskAiPanel"

export default function StudentSubjectDetails() {
  const { id } = useParams<{ id: string }>()
  return <StudentSubjectContent key={id} />
}

function StudentSubjectContent() {
  const { id } = useParams<{ id: string }>()
  const [subject, setSubject] = useState<Subject | null>(null)
  const [sets, setSets] = useState<FlashcardSet[]>([])
  const [loadedId, setLoadedId] = useState<string | null>(null)
  const loading = loadedId !== id
  const loadControllerRef = useRef<AbortController | null>(null)
  const [progressMap, setProgressMap] = useState<Record<string, SetProgress>>({})
  const [loadError, setLoadError] = useState<string | null>(null)
  const [progressWarning, setProgressWarning] = useState<string | null>(null)

  const loadData = useCallback(() => {
    if (!id) return Promise.resolve()
    loadControllerRef.current?.abort()
    const controller = new AbortController()
    loadControllerRef.current = controller
    const { signal } = controller
    return Promise.all([
      subjectService.getSubject(id, signal),
      subjectService.getSets(id, signal),
    ]).then(([subData, setsData]) => {
      if (signal.aborted) return
      setLoadError(null)
      setSubject(subData)
      setSets(setsData)
      return Promise.allSettled(
        setsData.filter((set) => set.is_published)
          .map(async (set) => [set.id, await studyService.getSetProgress(set.id, signal)] as const),
      ).then((progressResults) => {
        if (signal.aborted) return
        const successful = progressResults.flatMap((result) => result.status === 'fulfilled' ? [result.value] : [])
        setProgressMap(Object.fromEntries(successful))
        setProgressWarning(successful.length !== progressResults.length ? copy.studentSubject.progressPartial : null)
      })
    }).catch((caught: unknown) => {
      if (!signal.aborted) setLoadError(apiErrorMessage(caught, copy.studentSubject.loadFailed))
    }).finally(() => {
      if (!signal.aborted) setLoadedId(id)
    })
  }, [id])

  const reloadData = () => {
    setLoadedId(null)
    void loadData()
  }

  useEffect(() => {
    void loadData()
    return () => loadControllerRef.current?.abort()
  }, [loadData])

  if (loading) return <div className="p-8" role="status" aria-label={copy.common.loading}><Loader2 className="animate-spin" /></div>

  if (loadError) return <PageError message={loadError} onRetry={reloadData} />

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link to="/dashboard" aria-label={copy.common.backToDashboard}>
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{subject?.name}</h1>
          <p className="text-muted-foreground">{subject?.description}</p>
        </div>
      </div>

      {progressWarning ? (
        <div className="flex items-center justify-between gap-4 rounded border border-amber-200 bg-amber-50 p-3" role="alert">
          <p className="text-sm text-amber-800">{progressWarning}</p>
          <Button type="button" variant="outline" size="sm" onClick={reloadData}>{copy.common.retry}</Button>
        </div>
      ) : null}

      {id ? <AskAiPanel subjectId={id} /> : null}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sets.map((set) => {
          const progress = progressMap[set.id]
          const totalCards = progress?.total ?? set.flashcard_count ?? 0
          const studiedCount = progress?.studied ?? 0
          const progressPercent = Math.round(progress?.completion_percentage ?? 0)
          const masteryPercent = Math.round(progress?.mastery_percentage ?? 0)
          const isComplete = progressPercent === 100 && totalCards > 0
          
          return (
            <Card key={set.id} className={isComplete ? "border-green-300 bg-green-50/50" : ""}>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="h-4 w-4 text-blue-500" aria-hidden="true" />
                  {set.title}
                  {isComplete && (
                    <span className="ml-auto">
                      <Trophy className="h-5 w-5 text-yellow-500" aria-hidden="true" />
                    </span>
                  )}
                </CardTitle>
                <CardDescription>
                   {copy.subject.cardCount(totalCards)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                  {/* Progress Section */}
                  {progress && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">{copy.studentSubject.progress}</span>
                        <span className={`font-semibold ${isComplete ? 'text-green-600' : 'text-slate-700'}`}>
                          {studiedCount}/{totalCards}
                          {isComplete && (
                            <CheckCircle2 className="inline-block ml-1 h-4 w-4 text-green-500" aria-hidden="true" />
                          )}
                        </span>
                      </div>
                      <Progress 
                        value={progressPercent} 
                        className={`h-2 ${isComplete ? '[&>div]:bg-green-500' : ''}`}
                        aria-label={copy.studentSubject.progressFor(set.title)}
                        aria-valuetext={copy.studentSubject.progressValue(progressPercent, masteryPercent)}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{copy.studentSubject.complete(progressPercent)}</span>
                        <span>{copy.studentSubject.mastery(masteryPercent)}</span>
                        {!isComplete && progress.new > 0 && (
                          <span className="text-blue-700">{copy.studentSubject.newCards(progress.new)}</span>
                        )}
                      </div>
                    </div>
                  )}
                  
                  <Button asChild className={`w-full gap-2 group ${isComplete ? 'bg-green-600 hover:bg-green-700' : ''}`}>
                    <Link to={isComplete ? `/study/${set.id}?mode=review_all` : `/study/${set.id}`}>
                      <Brain className="h-4 w-4 transition-colors motion-reduce:transition-none group-hover:text-yellow-300" aria-hidden="true" />
                      {isComplete ? copy.studentSubject.reviewAgain : copy.studentSubject.studyNow}
                    </Link>
                  </Button>
              </CardContent>
            </Card>
          )
        })}
        
        {sets.length === 0 && !loading && (
            <div className="col-span-full py-12 text-center text-muted-foreground">
                <p>{copy.studentSubject.noPublishedSets}</p>
            </div>
        )}
      </div>
    </div>
  )
}
