export type UserRole = 'instructor' | 'student'

export type IsoDateTime = string

export interface User {
  id: string
  email: string
  role: UserRole
  full_name: string | null
  created_at: IsoDateTime
}

export interface AccessTokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface StudentRegistration {
  email: string
  password: string
  full_name?: string | null
  invite_token: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface ApiMessage {
  message: string
}

export interface PasswordForgotRequest {
  email: string
}

export interface PasswordResetRequest {
  token: string
  new_password: string
}

export interface Subject {
  id: string
  name: string
  description: string | null
  instructor_id: string
  created_at: IsoDateTime
  flashcard_set_count: number
  student_count: number
}

export interface SubjectCreate {
  name: string
  description?: string | null
}

export interface SubjectUpdate {
  name?: string
  description?: string | null
}

export interface FlashcardSet {
  id: string
  subject_id: string
  title: string
  description: string | null
  source_pdf_name: string | null
  generation_job_id: string | null
  is_published: boolean
  time_limit: number | null
  created_at: IsoDateTime
  flashcard_count: number
  approved_count: number
}

export interface FlashcardSetCreate {
  title: string
  description?: string | null
}

export interface FlashcardSetUpdate {
  title?: string
  description?: string | null
  is_published?: boolean
  time_limit?: number | null
}

export interface InvitationResponse {
  token: string
  subject_id: string
  expires_at: IsoDateTime
}

export interface InvitationCreate {
  expires_in_hours: number
}

export interface InvitationAccept {
  token: string
}

export interface JoinCourseResponse {
  message: string
  subject_name: string
}

export interface ApproveAllResponse {
  approved_count: number
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
  quality_score: number
  is_approved: boolean
  source_snippet: string | null
  source_page: number | null
  source_section: string | null
  created_at: IsoDateTime
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
  next_review: IsoDateTime | null
  last_reviewed: IsoDateTime | null
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

export type GenerationJobStatus =
  | 'awaiting_upload'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface GenerationJob {
  id: string
  subject_id: string
  flashcard_set_id: string | null
  status: GenerationJobStatus
  progress: number
  stage: string
  requested_card_count: number
  generated_card_count: number | null
  ai_provider: string
  ai_model: string
  estimated_input_tokens: number
  estimated_output_tokens: number
  actual_input_tokens: number | null
  actual_output_tokens: number | null
  estimated_cost_microusd: number | null
  actual_cost_microusd: number | null
  usage_estimated: boolean
  accepted_card_count: number
  rejected_card_count: number
  limit_reason_code: string | null
  limit_reason_message: string | null
  source_pdf_name: string
  attempt_count: number
  max_attempts: number
  error_code: string | null
  error_message: string | null
  cancellation_requested_at: IsoDateTime | null
  source_retry_expires_at: IsoDateTime | null
  created_at: IsoDateTime
  started_at: IsoDateTime | null
  completed_at: IsoDateTime | null
  updated_at: IsoDateTime
  can_cancel: boolean
  can_retry: boolean
}

export interface GenerationJobCreate {
  subject_id: string
  set_title: string
  set_description?: string | null
  source_pdf_name: string
  card_count: number
}

export interface GenerationJobList {
  jobs: GenerationJob[]
}

export interface GenerationLimits {
  generation_available: boolean
  ai_provider: string
  ai_model: string
  ai_pricing_configured: boolean
  unavailable_reasons: Array<{ code: string; message: string }>
  max_upload_bytes: number
  max_pages: number
  max_extracted_chars: number
  min_card_count: number
  max_card_count: number
  daily_jobs_per_user: number
  daily_cards_per_user: number
  daily_upload_bytes_per_user: number
  max_active_jobs_per_user: number
  daily_jobs_remaining: number
  daily_cards_remaining: number
  daily_upload_bytes_remaining: number
  active_job_slots_remaining: number
  deployment_queue_slots_remaining: number
  quota_resets_at: IsoDateTime
  failed_source_retention_hours: number
  upload_reservation_minutes: number
  ocr_enabled: boolean
}
