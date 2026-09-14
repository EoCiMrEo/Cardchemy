import { useState, useEffect } from "react"
import { subjectService } from "@/services/subjects"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Plus, BookOpen, Loader2, ArrowRight } from "lucide-react"
import { Link } from "react-router-dom"

export default function InstructorDashboard() {
  const [subjects, setSubjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [newSubjectName, setNewSubjectName] = useState("")
  const [creatingLoading, setCreatingLoading] = useState(false)
  useEffect(() => {
    loadSubjects()
  }, [])

  const loadSubjects = async () => {
    try {
      setLoading(true)
      const data = await subjectService.getSubjects()
      setSubjects(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateSubject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSubjectName.trim()) return

    try {
      setCreatingLoading(true)
      await subjectService.createSubject({ name: newSubjectName })
      setNewSubjectName("")
      setIsCreating(false)
      loadSubjects()
    } catch (e) {
      console.error(e)
    } finally {
      setCreatingLoading(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Your Subjects</h1>
          <p className="text-muted-foreground mt-1">Manage your courses and flashcards.</p>
        </div>
        <Button onClick={() => setIsCreating(!isCreating)}>
          <Plus className="mr-2 h-4 w-4" /> New Subject
        </Button>
      </div>

      {isCreating && (
        <Card className="max-w-md animate-accordion-down">
          <CardHeader>
            <CardTitle className="text-lg">Create New Subject</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateSubject} className="flex gap-2">
              <Input 
                placeholder="e.g. Mathematics 101" 
                value={newSubjectName}
                onChange={(e) => setNewSubjectName(e.target.value)}
                autoFocus
              />
              <Button type="submit" disabled={creatingLoading}>
                {creatingLoading ? <Loader2 className="animate-spin" /> : "Create"}
              </Button>
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
                  <BookOpen className="h-5 w-5 text-primary" />
                  {subject.name}
                </CardTitle>
                <CardDescription>
                  {subject.flashcard_set_count || 0} sets • {subject.student_count || 0} students
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center text-sm text-primary font-medium mt-4">
                  View details <ArrowRight className="ml-1 h-4 w-4" />
                </div>
              </CardContent>
             </Card>
          </Link>
        ))}

        {subjects.length === 0 && !loading && (
          <div className="col-span-full text-center py-12 text-muted-foreground bg-white rounded-lg border border-dashed">
            <h3 className="text-lg font-medium">No subjects yet</h3>
            <p>Create your first subject to get started.</p>
          </div>
        )}
      </div>
    </div>
  )
}
