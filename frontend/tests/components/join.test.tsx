import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import JoinCourse from '@/pages/JoinCourse'
import { copy } from '@/i18n/en'

const mocks = vi.hoisted(() => ({ join: vi.fn(), auth: { user: null as { role: string } | null, isLoading: false } }))
vi.mock('@/context/AuthContext', () => ({ useAuth: () => mocks.auth }))
vi.mock('@/services/subjects', () => ({ subjectService: { joinCourse: mocks.join } }))
beforeEach(() => { mocks.auth.user = { role: 'student' }; mocks.auth.isLoading = false; mocks.join.mockReset().mockResolvedValue({ subject_name: 'Biology', message: 'Enrolled' }) })
function mount(query = '?token=invitation') {
  return render(<MemoryRouter initialEntries={['/join' + query]}><Routes><Route path="/join" element={<JoinCourse />} /><Route path="/register" element={<p>Registration destination</p>} /><Route path="/dashboard" element={<p>Dashboard destination</p>} /></Routes></MemoryRouter>)
}
it('joins as a student and navigates to the dashboard', async () => {
  mount(); await screen.findByText('Biology'); expect(mocks.join).toHaveBeenCalledWith('invitation', expect.any(AbortSignal))
  fireEvent.click(screen.getByRole('button', { name: copy.join.goToDashboard })); await screen.findByText('Dashboard destination')
})
it('offers recovery after a transient join failure', async () => {
  mocks.join.mockRejectedValueOnce(new Error('offline')); mount()
  fireEvent.click(await screen.findByRole('button', { name: copy.join.retry })); await screen.findByText('Biology'); expect(mocks.join).toHaveBeenCalledTimes(2)
})
it('redirects a guest to invitation registration', async () => { mocks.auth.user = null; mount(); await screen.findByText('Registration destination'); expect(mocks.join).not.toHaveBeenCalled() })
it('blocks instructors without sending an enrollment request', async () => { mocks.auth.user = { role: 'instructor' }; mount(); expect(screen.getByRole('alert').textContent).toBe(copy.join.instructorBlocked); expect(mocks.join).not.toHaveBeenCalled() })
it('blocks missing invitation tokens', () => { mount(''); expect(screen.getByRole('alert').textContent).toBe(copy.join.missingToken); expect(mocks.join).not.toHaveBeenCalled() })
it('waits for authentication and ignores responses after unmount', async () => {
  mocks.auth.isLoading = true; const view = mount(); expect(mocks.join).not.toHaveBeenCalled(); view.unmount()
  mocks.auth.isLoading = false
  let resolve!: (value: { subject_name: string; message: string }) => void
  mocks.join.mockReturnValue(new Promise(r => { resolve = r })); const second = mount()
  const signal = mocks.join.mock.calls[0][1] as AbortSignal; second.unmount(); expect(signal.aborted).toBe(true)
  await act(async () => { resolve({ subject_name: 'stale', message: 'stale' }) }); expect(screen.queryByText('stale')).toBeNull()
})
