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
  invite_url: string
  delivery_queued: boolean
}

export interface InvitationCreate {
  expires_in_hours: number
  recipient_email?: string
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

export type StudySessionMode = 'due' | 'review_all'

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
  attempted_count: number
  attempted_percentage: number
  correct_count: number
  ever_correct_count: number
  progress_percentage: number
  accuracy_percentage: number
  completion_percentage: number
  mastery_percentage: number
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
  | 'awaiting_choice'
  | 'awaiting_card_choice'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type GenerationRejectionReason =
  | 'unknown_source'
  | 'chunk_quota'
  | 'quote_not_contiguous'
  | 'answer_not_in_quote'
  | 'unclear_question'
  | 'option_matches_question'
  | 'near_duplicate'

export interface GenerationQualityDiagnostics {
  manual_retry_number: number
  attempt_number: number
  raw_count: number
  grounded_count: number
  valid_count: number
  distinct_count: number
  accepted_count: number
  missing_count: number
  rejected_count: number
  refill_rounds_used: number
  uncertain_request_count: number
  rounds: Array<{
    round: number
    raw_count: number
    grounded_count: number
    valid_count: number
    distinct_count: number
    accepted_count: number
    missing_count: number
  }>
  rejections: Record<GenerationRejectionReason, number>
}

export interface GenerationJob {
  id: string
  subject_id: string
  job_kind: 'flashcards' | 'knowledge_only'
  document_id: string | null
  knowledge_content_revision_id: string | null
  knowledge_capture_status: 'not_requested' | 'pending' | 'captured' | 'reused' | 'unchanged' | 'failed' | 'removed'
  knowledge_upload_outcome: 'no_changes' | 'reused' | 'separate_copy' | null
  duplicate_candidate: {
    document_id: string
    title: string
    can_reuse: boolean
  } | null
  choice_expires_at: IsoDateTime | null
  knowledge_capture_error_code: string | null
  knowledge_capture_error_message: string | null
  flashcard_set_id: string | null
  status: GenerationJobStatus
  progress: number
  stage: string
  requested_card_count: number
  generated_card_count: number | null
  valid_candidate_count: number
  card_choice_expires_at: IsoDateTime | null
  selected_card_count: number | null
  can_accept_smaller_target: boolean
  latest_attempt_rejected_card_count: number
  latest_attempt_quality_diagnostics: GenerationQualityDiagnostics | null
  retry_estimated_additional_cost_microusd: number | null
  previous_attempt_cost_unknown: boolean
  ai_provider: string
  ai_model: string
  estimated_input_tokens: number
  estimated_output_tokens: number
  estimated_request_count: number
  provider_request_count: number
  provider_retry_count: number
  provider_rate_limit_wait_milliseconds: number
  cached_input_tokens: number
  provider_request_counts_by_stage: Record<string, number>
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

export type KnowledgeDuplicateChoice = 'reuse' | 'separate_copy'

export interface GenerationJobCreate {
  subject_id: string
  document_id?: string | null
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

export interface KnowledgeJobCreate {
  subject_id: string
  document_id?: string | null
  title: string
  source_pdf_name: string
}

export interface KnowledgeContentRevision {
  id: string
  revision_no: number
  status: 'processing' | 'pending_index' | 'ready' | 'extraction_failed' | 'cancelled'
  is_active: boolean
  page_count: number
  reviewed_at: IsoDateTime | null
  published_at: IsoDateTime | null
  error_code: string | null
  error_message: string | null
}

export interface KnowledgeIndexRevision {
  id: string
  revision_no: number
  status: 'pending_index' | 'indexing' | 'ready' | 'index_failed' | 'cancelled'
  is_active: boolean
  chunk_count: number
  embedded_count: number
  embedding_model: string
  embedding_space_revision: string
  error_code: string | null
  error_message: string | null
}

export interface KnowledgeIndexJob {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  attempt_count: number
  max_attempts: number
  error_code: string | null
  error_message: string | null
  created_at: IsoDateTime
  completed_at: IsoDateTime | null
}

export interface KnowledgeDocument {
  id: string
  subject_id: string
  title: string
  source_pdf_name: string
  created_at: IsoDateTime
  updated_at: IsoDateTime
  content_revision: KnowledgeContentRevision | null
  index_revision: KnowledgeIndexRevision | null
  index_job: KnowledgeIndexJob | null
  can_review_publish: boolean
  can_unpublish: boolean
  can_retry_index: boolean
  can_rebuild_from_pages: boolean
  requires_pdf_reupload: boolean
}

export interface RagThread {
  id: string
  subject_id: string
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface RagProfile {
  rag_enabled: boolean
  ask_enabled: boolean
  ask_policy: 'related_knowledge_navigation_v8' | 'related_knowledge_navigation_v7' | 'related_knowledge_navigation_v6' | 'related_knowledge_navigation_v5' | 'related_knowledge_navigation_v4' | 'related_knowledge_navigation_v3' | 'related_knowledge_navigation_v2' | 'related_knowledge_v1' | null
  ask_available: boolean
  answer_available: boolean
  answer_provider: string | null
  answer_model: string | null
  embedding_available: boolean
  embedding_provider: string
  embedding_model: string
  active_embedding_provider: string | null
  active_embedding_model: string | null
  active_embedding_space_matches: boolean
  source_judge_available: boolean
  source_judge_provider: string | null
  source_judge_model: string | null
  source_judge_transfers_published_content: boolean
  source_judge_thinking_level: 'LOW' | 'HIGH' | null
  source_judge_transfers_page_images: boolean
  source_judge_transfers_literal_subject_context: boolean
  source_judge_contract_version: string | null
  chat_retention_days: number
}

export interface RagSource {
  citation_order: number
  chunk_id: string
  document_id: string
  document_title: string
  content_revision_id: string
  index_revision_id: string
  page_number: number
  section: string | null
  claim_text: string
  source_quote: string
}

export interface RagMessage {
  id: string
  role: 'user' | 'assistant'
  outcome: 'answer' | 'abstained' | null
  abstention_kind: 'retrieval_insufficient' | 'model_abstained' | 'support_rejected' | null
  content: string | null
  hidden: boolean
  sources: RagSource[]
  created_at: IsoDateTime
  expires_at: IsoDateTime
}

export interface RagHistory {
  thread: RagThread
  messages: RagMessage[]
}

export interface RagRelatedExcerpt {
  excerpt_order: number
  document_title: string
  page_number: number
  section: string | null
  source_quote: string
}

export interface RagRelatedPage {
  document_title: string
  page_number: number
  section: string | null
  source_quote: string
  page_content: string
  reference_start: number | null
  reference_end: number | null
}

export interface RagOriginalPdfMetadata {
  byte_length: number
  page_count: number
}

export interface PublishedKnowledgeDocument {
  id: string
  title: string
  page_count: number
  has_original_pdf: boolean
}

export interface PublishedKnowledgeSearchHit {
  document_id: string
  document_title: string
  page_number: number
}

export interface PublishedKnowledgePage {
  document_title: string
  page_number: number
  page_content: string
  truncated: boolean
}

export interface RagAnswerJob {
  id: string
  thread_id: string
  subject_id: string
  question_message_id: string
  answer_message_id: string | null
  ask_policy: 'related_knowledge_navigation_v8' | 'related_knowledge_navigation_v7' | 'related_knowledge_navigation_v6' | 'related_knowledge_navigation_v5' | 'related_knowledge_navigation_v4' | 'related_knowledge_navigation_v3' | 'related_knowledge_navigation_v2' | 'related_knowledge_v1' | 'two_request_local_support_v1' | 'legacy_three_call_v1' | null
  search_mode: 'hybrid' | 'lexical_fallback' | 'not_searched'
  result_kind: 'related_knowledge' | 'no_match' | 'clarification_needed' | null
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  embedding_provider: string | null
  embedding_model: string | null
  source_judge_provider: string | null
  source_judge_model: string | null
  ai_provider: string | null
  ai_model: string | null
  retrieval_policy: string
  attempt_count: number
  manual_retry_count: number
  max_attempts: number
  estimated_input_tokens: number
  estimated_output_tokens: number
  actual_input_tokens: number | null
  actual_output_tokens: number | null
  provider_request_count: number
  provider_retry_count: number
  provider_rate_limit_wait_milliseconds: number
  estimated_cost_microusd: number | null
  actual_cost_microusd: number | null
  estimated_additional_cost_microusd: number | null
  previous_attempt_cost_microusd: number | null
  usage_estimated: boolean
  support_rejection_count: number
  related_excerpts: RagRelatedExcerpt[]
  error_code: string | null
  error_message: string | null
  failure_kind: 'provider_temporarily_unavailable' | 'provider_rejected' | 'invalid_output' | 'support_unavailable' | 'internal_failure' | null
  cancellation_requested_at: IsoDateTime | null
  created_at: IsoDateTime
  completed_at: IsoDateTime | null
  updated_at: IsoDateTime
  can_cancel: boolean
  can_retry: boolean
}
