import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import StudyMode from '@/pages/student/StudyMode'
import studyReducer from '@/store/slices/studySlice'
import type { StudyAnswerResponse, StudyCard } from '@/services/types'
import { copy } from '@/i18n/en'

const mocks = vi.hoisted(() => ({ session: vi.fn(), answer: vi.fn() }))
vi.mock('@/services/study', () => ({ studyService: { getStudySession: mocks.session, updateProgress: mocks.answer } }))
const card: StudyCard = { id: 'card-1', set_id: 'set-1', front_content: 'What is Alpha?', options: ['Alpha', 'Beta', 'Gamma', 'Delta'], card_type: 'multiple_choice' }
const result: StudyAnswerResponse = { is_correct: true, quality: 5, correct_option: 'Alpha', correct_option_index: 0, progress: { id: 'progress', flashcard_id: card.id, status: 'learning', ease_factor: 2.5, interval_days: 1, next_review: null, last_reviewed: null, correct_count: 1, incorrect_count: 0 } }
beforeEach(() => { mocks.session.mockReset().mockResolvedValue({ cards: [card], total_due: 1, new_cards: 1, review_cards: 0, time_limit: null }); mocks.answer.mockReset().mockResolvedValue(result) })
function mount(mode = '') {
  const store = configureStore({ reducer: { study: studyReducer } })
  const view = render(<Provider store={store}><MemoryRouter initialEntries={['/study/set-1' + mode]}><Routes><Route path="/study/:id" element={<StudyMode />} /></Routes></MemoryRouter></Provider>)
  return { store, ...view }
}
it('locks options until a durable answer is acknowledged and completes the session', async () => {
  let resolve!: (r: StudyAnswerResponse) => void; mocks.answer.mockReturnValue(new Promise<StudyAnswerResponse>(r => { resolve = r }))
  const { store } = mount(); const option = await screen.findByRole('button', { name: /Alpha/ })
  fireEvent.click(option); fireEvent.click(option)
  expect(mocks.answer).toHaveBeenCalledTimes(1); expect((option as HTMLButtonElement).disabled).toBe(true)
  expect(screen.queryByRole('button', { name: copy.study.nextQuestion })).toBeNull()
  await act(async () => { resolve(result) })
  fireEvent.click(await screen.findByRole('button', { name: copy.study.nextQuestion }))
  await screen.findByText(copy.study.sessionComplete); expect(store.getState().study.results[card.id]).toBe(true)
})
it('retries a failed answer with the same logical key and original option', async () => {
  mocks.answer.mockRejectedValueOnce(new Error('connection lost')).mockResolvedValueOnce(result)
  mount(); fireEvent.click(await screen.findByRole('button', { name: /Alpha/ }))
  const retry = await screen.findByRole('button', { name: copy.study.retrySave })
  expect(screen.queryByRole('button', { name: copy.study.nextQuestion })).toBeNull()
  fireEvent.click(retry); await screen.findByRole('button', { name: copy.study.nextQuestion })
  const [first, second] = mocks.answer.mock.calls
  expect(first[0]).toEqual({ flashcard_id: card.id, selected_option: 'Alpha' }); expect(second[0]).toEqual(first[0]); expect(second[1]).toBe(first[1])
})
it('submits a timed-out card only once using a null answer', async () => {
  vi.useFakeTimers(); mocks.session.mockResolvedValue({ cards: [card], time_limit: 2 })
  await act(async () => { mount() })
  await act(async () => { await vi.advanceTimersByTimeAsync(2_000) })
  expect(mocks.answer).toHaveBeenCalledTimes(1)
  expect(mocks.answer.mock.calls[0][0]).toEqual({ flashcard_id: card.id, selected_option: null })
  expect(screen.getByText(copy.study.timeout)).toBeTruthy()
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
  expect(mocks.answer).toHaveBeenCalledTimes(1)
})
it('cancels an in-flight answer when the card is unmounted', async () => {
  mocks.answer.mockReturnValue(new Promise(() => undefined)); const view = mount()
  fireEvent.click(await screen.findByRole('button', { name: /Alpha/ }))
  const signal = mocks.answer.mock.calls[0][2] as AbortSignal; expect(signal.aborted).toBe(false)
  view.unmount(); expect(signal.aborted).toBe(true)
})
it('recovers a session load failure using the requested review mode', async () => {
  mocks.session.mockRejectedValueOnce(new Error('offline')); mount('?mode=review_all')
  fireEvent.click(await screen.findByRole('button', { name: copy.common.retry })); await screen.findByText(card.front_content)
  expect(mocks.session).toHaveBeenLastCalledWith('set-1', 20, 'review_all')
})
it('shows an accessible caught-up state when there are no due cards', async () => {
  mocks.session.mockResolvedValue({ cards: [], time_limit: null }); mount(); await screen.findByRole('heading', { name: copy.study.allCaughtUp })
  await waitFor(() => expect(document.activeElement?.textContent).toBe(copy.study.allCaughtUp))
})
