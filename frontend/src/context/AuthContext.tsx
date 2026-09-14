import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { clearAccessToken, refreshAccessToken, setAccessToken } from '../services/api'
import { authService } from '../services/auth'
import type { User } from '../services/types'


interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (accessToken: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const clearSession = useCallback(() => {
    clearAccessToken()
    setUser(null)
  }, [])

  const login = useCallback(async (accessToken: string) => {
    setAccessToken(accessToken)
    try {
      const profile = await authService.getProfile()
      setUser(profile)
    } catch (error) {
      clearSession()
      throw error
    }
  }, [clearSession])

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } finally {
      clearSession()
    }
  }, [clearSession])

  const checkAuth = useCallback(async () => {
    setIsLoading(true)
    try {
      await refreshAccessToken()
      setUser(await authService.getProfile())
    } catch {
      clearSession()
    } finally {
      setIsLoading(false)
    }
  }, [clearSession])

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  useEffect(() => {
    window.addEventListener('auth:session-ended', clearSession)
    return () => window.removeEventListener('auth:session-ended', clearSession)
  }, [clearSession])

  const value = useMemo(
    () => ({ user, isLoading, login, logout, checkAuth }),
    [user, isLoading, login, logout, checkAuth],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components -- colocated hook is the public context API
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
