import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { subjectService } from "@/services/subjects"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChevronLeft, FileText, Play, Brain, Loader2 } from "lucide-react"

export default function StudentSubjectDetails() {
  const { id } = useParams<{ id: string }>()
  const [subject, setSubject] = useState<any>(null)
  const [sets, setSets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

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
        {sets.map((set) => (
          <Card key={set.id}>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-500" />
                {set.title}
              </CardTitle>
              <CardDescription>
                 {set.flashcard_count || '?'} cards
              </CardDescription>
            </CardHeader>
            <CardContent>
                <Link to={`/study/${set.id}`}>
                    <Button className="w-full gap-2 group">
                        <Brain className="h-4 w-4 group-hover:text-yellow-300 transition-colors" />
                        Study Now
                    </Button>
                </Link>
                {/* Add progress bar here later */}
            </CardContent>
          </Card>
        ))}
        
        {sets.length === 0 && !loading && (
            <div className="col-span-full py-12 text-center text-muted-foreground">
                <p>No flashcard sets published yet.</p>
            </div>
        )}
      </div>
    </div>
  )
}
