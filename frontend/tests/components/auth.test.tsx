import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { ProtectedRoute, RoleRoute } from '@/components/auth/RouteGuards'
import type { User } from '@/services/types'

const mocks = vi.hoisted(() => ({ refresh: vi.fn(), profile: vi.fn(), logout: vi.fn(), clear: vi.fn(), set: vi.fn() }))
vi.mock('@/services/api', () => ({ refreshAccessToken: mocks.refresh, clearAccessToken: mocks.clear, setAccessToken: mocks.set }))
vi.mock('@/services/auth', () => ({ authService: { getProfile: mocks.profile, logout: mocks.logout } }))
const student: User = { id: 'student', email: 'student@example.com', role: 'student', full_name: 'Student', created_at: '2026-01-01' }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
function Account() {
  const { user, isLoading, login, logout, checkAuth } = useAuth()
  return <><p>{isLoading ? 'Loading' : user?.email ?? 'Anonymous'}</p>
    <button onClick={() => void login('explicit-token').catch(() => undefined)}>Log in</button>
    <button onClick={() => void logout().catch(() => undefined)}>Log out</button>
    <button onClick={() => void checkAuth()}>Recheck</button></>
}
beforeEach(() => { mocks.refresh.mockReset().mockResolvedValue('refresh-token'); mocks.profile.mockReset().mockResolvedValue(student); mocks.logout.mockReset().mockResolvedValue({ message: 'ok' }) })
describe('account lifecycle', () => {
  it('loads the profile after refreshing and clears an ended session', async () => {
    render(<AuthProvider><Account /></AuthProvider>)
    expect(screen.getByText('Loading')).toBeTruthy()
    await screen.findByText(student.email)
    expect(mocks.refresh).toHaveBeenCalledTimes(1)
    act(() => { window.dispatchEvent(new Event('auth:session-ended')) })
    expect(screen.getByText('Anonymous')).toBeTruthy()
  })
  it('clears credentials when bootstrap refresh fails', async () => {
    mocks.refresh.mockRejectedValue(new Error('expired'))
    render(<AuthProvider><Account /></AuthProvider>)
    await screen.findByText('Anonymous')
    expect(mocks.clear).toHaveBeenCalledTimes(1)
    expect(mocks.profile).not.toHaveBeenCalled()
  })
  it('prevents a stale bootstrap profile from restoring a logged-out account', async () => {
    const profile = deferred<User>(); mocks.profile.mockReturnValue(profile.promise)
    render(<AuthProvider><Account /></AuthProvider>)
    await waitFor(() => expect(mocks.profile).toHaveBeenCalled())
    fireEvent.click(screen.getByText('Log out'))
    await screen.findByText('Anonymous')
    await act(async () => { profile.resolve(student); await profile.promise })
    expect(screen.getByText('Anonymous')).toBeTruthy()
  })
  it('uses the explicit login profile instead of a superseded refresh', async () => {
    const refresh = deferred<string>(); mocks.refresh.mockReturnValue(refresh.promise)
    render(<AuthProvider><Account /></AuthProvider>)
    fireEvent.click(screen.getByText('Log in'))
    await screen.findByText(student.email)
    await act(async () => { refresh.resolve('stale'); await refresh.promise })
    expect(mocks.set).toHaveBeenCalledWith('explicit-token')
    expect(mocks.profile).toHaveBeenCalledTimes(1)
    expect(screen.getByText(student.email)).toBeTruthy()
  })
  it('clears an explicit login whose profile request fails', async () => {
    render(<AuthProvider><Account /></AuthProvider>); await screen.findByText(student.email)
    mocks.profile.mockRejectedValueOnce(new Error('profile failed'))
    fireEvent.click(screen.getByText('Log in')); await screen.findByText('Anonymous')
    expect(mocks.clear).toHaveBeenCalledTimes(1)
  })
  it('retains the account when logout cannot be confirmed and permits a recheck', async () => {
    render(<AuthProvider><Account /></AuthProvider>); await screen.findByText(student.email)
    mocks.logout.mockRejectedValueOnce(new Error('offline'))
    fireEvent.click(screen.getByText('Log out')); await waitFor(() => expect(mocks.logout).toHaveBeenCalled())
    expect(screen.getByText(student.email)).toBeTruthy()
    fireEvent.click(screen.getByText('Recheck'))
    expect(screen.getByText('Loading')).toBeTruthy()
    await screen.findByText(student.email)
    expect(mocks.refresh).toHaveBeenCalledTimes(2)
  })
})
describe('route permissions', () => {
  function route(role?: 'instructor' | 'student') {
    render(<MemoryRouter initialEntries={['/protected']}><AuthProvider><Routes>
      <Route path="/protected" element={role ? <RoleRoute role={role}><p>Protected content</p></RoleRoute> : <ProtectedRoute><p>Protected content</p></ProtectedRoute>} />
      <Route path="/login" element={<p>Login destination</p>} /><Route path="/dashboard" element={<p>Dashboard destination</p>} />
    </Routes></AuthProvider></MemoryRouter>)
  }
  it('waits for account loading before redirecting', async () => {
    const refresh = deferred<string>(); mocks.refresh.mockReturnValue(refresh.promise); route()
    expect(screen.getByRole('status')).toBeTruthy(); expect(screen.queryByText('Login destination')).toBeNull()
    await act(async () => { refresh.resolve('token') }); await screen.findByText('Protected content')
  })
  it('redirects unauthenticated accounts to login', async () => { mocks.refresh.mockRejectedValue(new Error('expired')); route(); await screen.findByText('Login destination') })
  it('allows the required role', async () => { route('student'); await screen.findByText('Protected content') })
  it('redirects the wrong role to the dashboard', async () => { route('instructor'); await screen.findByText('Dashboard destination') })
  it('sends an unauthenticated role route to login', async () => { mocks.refresh.mockRejectedValue(new Error('expired')); route('instructor'); await screen.findByText('Login destination') })
})
