import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { subjectService } from "@/services/subjects"
import { studyService } from "@/services/study"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { ChevronLeft, FileText, Brain, Loader2, CheckCircle2, Trophy } from "lucide-react"
import type { SetProgress } from "@/services/types"

export default function StudentSubjectDetails() {
  const { id } = useParams<{ id: string }>()
  const [subject, setSubject] = useState<any>(null)
  const [sets, setSets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [progressMap, setProgressMap] = useState<Record<string, SetProgress>>({})

  useEffect(() => {
    if (id) loadData()
  }, [id])

  const loadData = async () => {
    try {
      setLoading(true)
      const [subData, setsData] = await Promise.all([
        subjectService.getSubject(id!),
        subjectService.getSets(id!)
      ])
      setSubject(subData)
      setSets(setsData)
      
      // Fetch progress for each published set
      const progressResults: Record<string, SetProgress> = {}
      await Promise.all(
        setsData
          .filter((s: any) => s.is_published)
          .map(async (set: any) => {
            try {
              const progress = await studyService.getSetProgress(set.id)
              progressResults[set.id] = progress
            } catch (e) {
              // Ignore errors for individual sets
              console.error(`Failed to load progress for set ${set.id}`, e)
            }
          })
      )
      setProgressMap(progressResults)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="p-8"><Loader2 className="animate-spin" /></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/dashboard">
          <Button variant="ghost" size="icon">
            <ChevronLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{subject?.name}</h1>
          <p className="text-muted-foreground">{subject?.description}</p>
        </div>
      </div>

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
                  <FileText className="h-4 w-4 text-blue-500" />
                  {set.title}
                  {isComplete && (
                    <span className="ml-auto">
                      <Trophy className="h-5 w-5 text-yellow-500" />
                    </span>
                  )}
                </CardTitle>
                <CardDescription>
                   {totalCards} cards
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                  {/* Progress Section */}
                  {progress && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Progress</span>
                        <span className={`font-semibold ${isComplete ? 'text-green-600' : 'text-slate-700'}`}>
                          {studiedCount}/{totalCards}
                          {isComplete && (
                            <CheckCircle2 className="inline-block ml-1 h-4 w-4 text-green-500" />
                          )}
                        </span>
                      </div>
                      <Progress 
                        value={progressPercent} 
                        className={`h-2 ${isComplete ? '[&>div]:bg-green-500' : ''}`}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{progressPercent}% complete</span>
                        <span>{masteryPercent}% mastery</span>
                        {!isComplete && progress.new > 0 && (
                          <span className="text-blue-500">{progress.new} new</span>
                        )}
                      </div>
                    </div>
                  )}
                  
                  <Link to={`/study/${set.id}`}>
                      <Button className={`w-full gap-2 group ${isComplete ? 'bg-green-600 hover:bg-green-700' : ''}`}>
                          <Brain className="h-4 w-4 group-hover:text-yellow-300 transition-colors" />
                          {isComplete ? "Review Again" : "Study Now"}
                      </Button>
                  </Link>
              </CardContent>
            </Card>
          )
        })}
        
        {sets.length === 0 && !loading && (
            <div className="col-span-full py-12 text-center text-muted-foreground">
                <p>No flashcard sets published yet.</p>
            </div>
        )}
      </div>
    </div>
  )
}
