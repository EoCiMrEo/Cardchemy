import { useState, useEffect } from "react"
import { subjectService } from "@/services/subjects"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { BookOpen, ArrowRight, Loader2, Play, UserPlus } from "lucide-react"
import { Link } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
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

export default function StudentDashboard() {
  const [subjects, setSubjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [joinDialogOpen, setJoinDialogOpen] = useState(false)
  const [joinToken, setJoinToken] = useState("")
  const [joining, setJoining] = useState(false)
  const [joinError, setJoinError] = useState("")
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

  const handleJoinCourse = async () => {
    if (!joinToken.trim()) return
    
    setJoining(true)
    setJoinError("")
    
    try {
      await subjectService.joinCourse(joinToken.trim())
      setJoinDialogOpen(false)
      setJoinToken("")
      await loadSubjects() // Refresh the list
    } catch (err: any) {
      setJoinError(err.response?.data?.detail || "Failed to join course")
    } finally {
      setJoining(false)
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
        
        <Dialog open={joinDialogOpen} onOpenChange={setJoinDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <UserPlus className="h-4 w-4" />
              Join Course
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Join a Course</DialogTitle>
              <DialogDescription>
                Enter the invite token provided by your instructor to join a course.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <Input
                placeholder="Paste invite token here"
                value={joinToken}
                onChange={(e) => setJoinToken(e.target.value)}
                disabled={joining}
              />
              {joinError && (
                <p className="text-sm text-destructive">{joinError}</p>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setJoinDialogOpen(false)} disabled={joining}>
                Cancel
              </Button>
              <Button onClick={handleJoinCourse} disabled={joining || !joinToken.trim()}>
                {joining ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Join Course
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
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
