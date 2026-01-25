import { useState, useEffect } from "react"
import { subjectService } from "@/services/subjects"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { BookOpen, ArrowRight, Loader2, Play } from "lucide-react"
import { Link } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"

export default function StudentDashboard() {
  const [subjects, setSubjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [inviteCode, setInviteCode] = useState("")
  // const [joining, setJoining] = useState(false) // implement invite acceptance later
  const { user } = useAuth()

  useEffect(() => {
    loadSubjects()
  }, [])

  const loadSubjects = async () => {
    try {
      setLoading(true)
      const data = await subjectService.getSubjects() // Returns enrolled subjects for students
      setSubjects(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="p-8"><Loader2 className="animate-spin" /></div>

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">My Courses</h1>
          <p className="text-muted-foreground mt-1">Select a subject to start studying.</p>
        </div>
        {/* Placeholder for "Join with Code" button */}
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {subjects.map((subject) => (
          <Link key={subject.id} to={`/subjects/${subject.id}`}>
             <Card className="hover:shadow-md transition-shadow cursor-pointer h-full border-l-4 border-l-primary">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-primary" />
                  {subject.name}
                </CardTitle>
                <CardDescription>
                  {subject.description || "No description"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center text-sm font-medium mt-4 bg-primary/5 text-primary p-2 rounded justify-between">
                  <span>Start Learning</span>
                  <Play className="h-4 w-4 fill-current" />
                </div>
              </CardContent>
             </Card>
          </Link>
        ))}

        {subjects.length === 0 && !loading && (
          <div className="col-span-full text-center py-12 text-muted-foreground bg-white rounded-lg border border-dashed">
            <h3 className="text-lg font-medium">Not enrolled in any courses</h3>
            <p className="mt-2">Ask your instructor for an invite link to join a course.</p>
          </div>
        )}
      </div>
    </div>
  )
}
