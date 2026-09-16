import type { ApiCall, MockResponse } from './mockApi'

export const generationLimits = {
  generation_available: true,
  ai_provider: 'test-provider',
  ai_model: 'test-model',
  ai_pricing_configured: true,
  unavailable_reasons: [],
  max_upload_bytes: 10_000_000,
  max_pages: 100,
  max_extracted_chars: 100_000,
  min_card_count: 1,
  max_card_count: 100,
  daily_jobs_per_user: 10,
  daily_cards_per_user: 1_000,
  daily_upload_bytes_per_user: 100_000_000,
  max_active_jobs_per_user: 3,
  daily_jobs_remaining: 10,
  daily_cards_remaining: 1_000,
  daily_upload_bytes_remaining: 100_000_000,
  active_job_slots_remaining: 3,
  deployment_queue_slots_remaining: 10,
  quota_resets_at: '2026-09-16T00:00:00Z',
  failed_source_retention_hours: 24,
  upload_reservation_minutes: 15,
  ocr_enabled: false,
}

export function generationResponse(call: ApiCall): MockResponse | undefined {
  if (call.method === 'GET' && call.path === '/flashcards/generation-jobs') {
    return { json: { jobs: [] } }
  }
  if (call.method === 'GET' && call.path === '/flashcards/generation-limits') {
    return { json: generationLimits }
  }
  return undefined
}

