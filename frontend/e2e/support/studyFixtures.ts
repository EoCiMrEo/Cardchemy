import type {
  StudyAnswerResponse,
  StudyCard,
  StudySessionResponse,
} from '../../src/services/types'
import { fixtures } from './mockApi'

export const studyCards: [StudyCard, StudyCard] = [
  {
    id: fixtures.cards[0].id,
    set_id: fixtures.cards[0].set_id,
    front_content: fixtures.cards[0].front_content,
    options: fixtures.cards[0].options,
    card_type: 'multiple_choice',
  },
  {
    id: fixtures.cards[1].id,
    set_id: fixtures.cards[1].set_id,
    front_content: fixtures.cards[1].front_content,
    options: fixtures.cards[1].options,
    card_type: 'multiple_choice',
  },
]

export function studySession(
  cards: StudyCard[] = studyCards,
  timeLimit: number | null = null,
): StudySessionResponse {
  return {
    cards,
    total_due: cards.length,
    new_cards: cards.length,
    review_cards: 0,
    time_limit: timeLimit,
  }
}

export function answerResponse(
  card: StudyCard,
  selectedOption: string | null,
): StudyAnswerResponse {
  const correctOptionIndex = card.id === fixtures.cards[1].id ? 2 : 1
  const correctOption = card.options[correctOptionIndex]
  return {
    progress: {
      id: `progress-${card.id}`,
      flashcard_id: card.id,
      status: 'learning',
      ease_factor: 2.5,
      interval_days: 1,
      next_review: '2026-09-16T00:00:00Z',
      last_reviewed: '2026-09-15T00:00:00Z',
      correct_count: selectedOption === correctOption ? 1 : 0,
      incorrect_count: selectedOption === correctOption ? 0 : 1,
    },
    is_correct: selectedOption === correctOption,
    quality: selectedOption === correctOption ? 5 : 1,
    correct_option: correctOption,
    correct_option_index: correctOptionIndex,
  }
}
