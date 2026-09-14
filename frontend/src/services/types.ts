export type UserRole = 'instructor' | 'student'

export interface User {
  id: string
  email: string
  role: UserRole
  full_name?: string | null
  created_at: string
}

export interface AccessTokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface StudentRegistration {
  email: string
  password: string
  full_name?: string
  invite_token: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface ApiMessage {
  message: string
}

export interface InvitationResponse {
  token: string
  subject_id: string
  expires_at: string
}

export type ProgressStatus = 'new' | 'learning' | 'review' | 'mastered'

export interface StudyCard {
  id: string
  set_id: string
  front_content: string
  options: [string, string, string, string]
  card_type: 'multiple_choice'
}

export interface Flashcard extends StudyCard {
  back_content: string
  confidence_score: number
  is_approved: boolean
  source_chunk?: string | null
  created_at: string
}

export type StudyAnswerRequest =
  | { flashcard_id: string; selected_option: string | null; selected_option_index?: never }
  | { flashcard_id: string; selected_option_index: number; selected_option?: never }

export interface StudyProgress {
  id: string
  flashcard_id: string
  status: ProgressStatus
  ease_factor: number
  interval_days: number
  next_review: string | null
  last_reviewed: string | null
  correct_count: number
  incorrect_count: number
}

export interface StudyAnswerResponse {
  progress: StudyProgress
  is_correct: boolean
  quality: 1 | 5
  correct_option: string
  correct_option_index: number
}

export interface StudySessionResponse {
  cards: StudyCard[]
  total_due: number
  new_cards: number
  review_cards: number
  time_limit: number | null
}

export interface SetProgress {
  total: number
  new: number
  learning: number
  review: number
  mastered: number
  studied: number
  correct_count: number
  completion_percentage: number
  mastery_percentage: number
}

export interface StudySyncResponse {
  synced_count: number
}

export interface FlashcardUpdate {
  front_content?: string
  back_content?: string
  options?: [string, string, string, string]
  card_type?: 'multiple_choice'
  is_approved?: boolean
}
