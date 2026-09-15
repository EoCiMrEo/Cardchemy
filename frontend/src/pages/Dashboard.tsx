import { useState } from "react"
import { useAuth } from "@/context/AuthContext"
import InstructorDashboard from "./instructor/InstructorDashboard"
import StudentDashboard from "./student/StudentDashboard"
import { Button } from "@/components/ui/button"
import { copy } from "@/i18n/en"
import { apiErrorMessage } from "@/services/errors"

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)

  const handleLogout = async () => {
    if (loggingOut) return
    setLogoutError(null)
    setLoggingOut(true)
    try {
      await logout()
    } catch (caught: unknown) {
      setLogoutError(apiErrorMessage(caught, copy.auth.logoutFailed))
    } finally {
      setLoggingOut(false)
    }
  }

  const logoutButton = (
    <Button variant="outline" size="sm" onClick={() => void handleLogout()} disabled={loggingOut}>
      {loggingOut ? copy.auth.loggingOut : copy.common.logout}
    </Button>
  )

  const logoutErrorNotice = logoutError ? (
    <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-center text-sm text-red-800" role="alert">
      {logoutError}
    </div>
  ) : null

  if (user?.role === 'instructor') {
      return (
          <div className="min-h-screen bg-gray-50">
            <header className="bg-white border-b sticky top-0 z-10">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                <h1 className="text-xl font-bold text-gray-900">{copy.common.appName}</h1>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-600">
                    {user?.email}
                  </span>
                  {logoutButton}
                </div>
              </div>
            </header>
            {logoutErrorNotice}
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
                <h1 className="text-xl font-bold text-gray-900">{copy.common.appName}</h1>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-600">
                    {user?.email}
                  </span>
                  {logoutButton}
                </div>
              </div>
            </header>
            {logoutErrorNotice}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <StudentDashboard />
            </main>
          </div>
      )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
             {copy.routing.unknownRole(user?.role ?? '')} {logoutButton}
        </div>
    </div>
  )
}
