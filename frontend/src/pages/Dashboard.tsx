import { useAuth } from "@/context/AuthContext"
import InstructorDashboard from "./instructor/InstructorDashboard"
import StudentDashboard from "./student/StudentDashboard"
import { Button } from "@/components/ui/button"

export default function Dashboard() {
  const { user, logout } = useAuth()

  if (user?.role === 'instructor') {
      return (
          <div className="min-h-screen bg-gray-50">
            <header className="bg-white border-b sticky top-0 z-10">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                <h1 className="text-xl font-bold text-gray-900">Flashcard Generator</h1>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-600">
                    {user?.email}
                  </span>
                  <Button variant="outline" size="sm" onClick={logout}>
                    Logout
                  </Button>
                </div>
              </div>
            </header>
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <InstructorDashboard />
            </main>
          </div>
      )
  }

  if (user?.role === 'student') {
      return (
          <div className="min-h-screen bg-gray-50">
            <header className="bg-white border-b sticky top-0 z-10">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                <h1 className="text-xl font-bold text-gray-900">Flashcard Generator</h1>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-600">
                    {user?.email}
                  </span>
                  <Button variant="outline" size="sm" onClick={logout}>
                    Logout
                  </Button>
                </div>
              </div>
            </header>
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <StudentDashboard />
            </main>
          </div>
      )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
             Unknown Role: {user?.role}. <Button onClick={logout}>Logout</Button>
        </div>
    </div>
  )
}
