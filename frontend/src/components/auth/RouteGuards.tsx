import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { copy } from '@/i18n/en'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return <div className="flex min-h-dvh items-center justify-center" role="status">{copy.routing.loadingAccount}</div>
  if (!user) return <Navigate to="/login" />
  return <>{children}</>
}

export function RoleRoute({ children, role }: { children: React.ReactNode; role: 'instructor' | 'student' }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return <div className="flex min-h-dvh items-center justify-center" role="status">{copy.routing.loadingAccount}</div>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}
