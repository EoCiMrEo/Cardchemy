import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import SetView from '@/pages/instructor/SetView'
import { EditSetDialog } from '@/components/sets/EditSetDialog'
import type { Flashcard, FlashcardSet } from '@/services/types'
import { copy } from '@/i18n/en'

const mocks = vi.hoisted(() => ({ getSet: vi.fn(), cards: vi.fn(), updateCard: vi.fn(), updateSet: vi.fn() }))
vi.mock('@/services/subjects', () => ({ subjectService: { getSet: mocks.getSet, updateSet: mocks.updateSet } }))
vi.mock('@/services/flashcards', () => ({ flashcardService: { getCards: mocks.cards, updateCard: mocks.updateCard } }))
const set: FlashcardSet = { id: 'set-1', subject_id: 'subject-1', title: 'Biology', description: null, source_pdf_name: null, generation_job_id: null, is_published: false, time_limit: null, created_at: '2026-01-01', flashcard_count: 1, approved_count: 0 }
const card: Flashcard = { id: 'card-1', set_id: set.id, front_content: 'What is Alpha?', options: ['Alpha', 'Beta', 'Gamma', 'Delta'], card_type: 'multiple_choice', back_content: 'Alpha', quality_score: 0.9, is_approved: false, source_snippet: null, source_page: null, source_section: null, created_at: '2026-01-01' }
beforeEach(() => { mocks.getSet.mockReset().mockResolvedValue(set); mocks.cards.mockReset().mockResolvedValue([card]); mocks.updateCard.mockReset().mockResolvedValue({ ...card, front_content: 'Edited question', back_content: 'Beta' }); mocks.updateSet.mockReset().mockResolvedValue(set) })
function review() { return render(<MemoryRouter initialEntries={['/sets/set-1']}><Routes><Route path="/sets/:id" element={<SetView />} /></Routes></MemoryRouter>) }
it('validates question and unique options before any card write, then saves the selected answer', async () => {
  review(); fireEvent.click(await screen.findByRole('button', { name: `Edit ${card.front_content}` }))
  const front = screen.getByRole('textbox', { name: copy.setReview.front })
  fireEvent.change(front, { target: { value: '' } }); fireEvent.click(screen.getByRole('button', { name: copy.setReview.save }))
  expect(screen.getByRole('alert').textContent).toBe(copy.setReview.validationFront); expect(mocks.updateCard).not.toHaveBeenCalled()
  fireEvent.change(front, { target: { value: ' Edited question ' } })
  const option = screen.getByRole('textbox', { name: copy.setReview.optionLabel(1) })
  fireEvent.change(option, { target: { value: 'ALPHA' } }); fireEvent.click(screen.getByRole('button', { name: copy.setReview.save }))
  expect(screen.getByRole('alert').textContent).toBe(copy.setReview.validationUnique)
  fireEvent.change(option, { target: { value: '' } }); fireEvent.click(screen.getByRole('button', { name: copy.setReview.save }))
  expect(screen.getByRole('alert').textContent).toBe(copy.setReview.validationOptions)
  fireEvent.change(option, { target: { value: 'Beta' } }); fireEvent.click(screen.getByRole('radio', { name: copy.setReview.correctAnswer(1) }))
  fireEvent.click(screen.getByRole('button', { name: copy.setReview.save })); await screen.findByText('Edited question')
  expect(mocks.updateCard).toHaveBeenCalledWith(card.id, { front_content: 'Edited question', back_content: 'Beta', options: card.options })
})
it('retains draft edits after a failed save and supports recovery', async () => {
  mocks.updateCard.mockRejectedValueOnce(new Error('offline')); review()
  fireEvent.click(await screen.findByRole('button', { name: `Edit ${card.front_content}` })); fireEvent.click(screen.getByRole('button', { name: copy.setReview.save }))
  await screen.findByRole('alert'); expect((screen.getByRole('textbox', { name: copy.setReview.front }) as HTMLTextAreaElement).value).toBe(card.front_content)
  fireEvent.click(screen.getByRole('button', { name: copy.setReview.save })); await screen.findByText('Edited question'); expect(mocks.updateCard).toHaveBeenCalledTimes(2)
})
it('keeps set settings open after failure and saves a null timer deliberately', async () => {
  const success = vi.fn(); const close = vi.fn(); mocks.updateSet.mockRejectedValueOnce(new Error('offline'))
  render(<EditSetDialog open onOpenChange={close} subjectId={set.subject_id} set={set} onSuccess={success} />)
  fireEvent.change(screen.getByLabelText(copy.editSet.titleLabel), { target: { value: ' New title ' } })
  fireEvent.click(screen.getByRole('button', { name: copy.common.saveChanges })); await screen.findByRole('alert'); expect(close).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: copy.common.saveChanges })); await screen.findByRole('dialog')
  await vi.waitFor(() => expect(success).toHaveBeenCalledTimes(1)); expect(close).toHaveBeenCalledWith(false)
  expect(mocks.updateSet).toHaveBeenLastCalledWith(set.subject_id, set.id, { title: 'New title', description: null, is_published: false, time_limit: null })
})
