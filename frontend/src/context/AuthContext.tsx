import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

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
  const authOperation = useRef(0)

  const clearSessionState = useCallback(() => {
    clearAccessToken()
    setUser(null)
  }, [])

  const clearSession = useCallback(() => {
    authOperation.current += 1
    clearSessionState()
    setIsLoading(false)
  }, [clearSessionState])

  const handleSessionEnded = useCallback(() => {
    // The API layer has already cleared its in-memory token exactly once.
    authOperation.current += 1
    setUser(null)
    setIsLoading(false)
  }, [])

  const login = useCallback(async (accessToken: string) => {
    const operation = ++authOperation.current
    setIsLoading(true)
    setAccessToken(accessToken)
    try {
      const profile = await authService.getProfile()
      if (authOperation.current === operation) {
        setUser(profile)
        setIsLoading(false)
      }
    } catch (error) {
      if (authOperation.current === operation) clearSession()
      throw error
    }
  }, [clearSession])

  const logout = useCallback(async () => {
    const operation = ++authOperation.current
    try {
      await authService.logout()
      if (authOperation.current === operation) clearSession()
    } catch (error) {
      if (authOperation.current === operation) setIsLoading(false)
      throw error
    }
  }, [clearSession])

  const restoreSession = useCallback(() => {
    const operation = ++authOperation.current
    return refreshAccessToken().then(() => {
      if (authOperation.current !== operation) return
      return authService.getProfile().then((profile) => {
        if (authOperation.current === operation) setUser(profile)
      })
    }).catch(() => {
      if (authOperation.current === operation) clearSessionState()
    }).finally(() => {
      if (authOperation.current === operation) setIsLoading(false)
    })
  }, [clearSessionState])

  const checkAuth = useCallback(async () => {
    setIsLoading(true)
    await restoreSession()
  }, [restoreSession])

  useEffect(() => {
    void restoreSession()
    return () => {
      authOperation.current += 1
    }
  }, [restoreSession])

  useEffect(() => {
    window.addEventListener('auth:session-ended', handleSessionEnded)
    return () => window.removeEventListener('auth:session-ended', handleSessionEnded)
  }, [handleSessionEnded])

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
