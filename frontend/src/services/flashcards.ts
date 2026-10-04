import api from './api'
import type {
  ApproveAllResponse,
  Flashcard,
  FlashcardUpdate,
  GenerationJob,
  GenerationJobCreate,
  GenerationJobList,
  GenerationLimits,
  KnowledgeDuplicateChoice,
} from './types'

export const flashcardService = {
  async getCards(setId: string, signal?: AbortSignal): Promise<Flashcard[]> {
    const response = await api.get<Flashcard[]>(`/flashcards/sets/${setId}/cards`, { signal })
    return response.data
  },

  async createGenerationJob(
    data: GenerationJobCreate,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): Promise<GenerationJob> {
    const response = await api.post<GenerationJob>('/flashcards/generation-jobs', data, {
      headers: { 'Idempotency-Key': idempotencyKey },
      signal,
    })
    return response.data
  },

  async uploadGenerationSource(
    jobId: string,
    file: File,
    signal?: AbortSignal,
  ): Promise<GenerationJob> {
    const response = await api.put<GenerationJob>(
      `/flashcards/generation-jobs/${jobId}/source`,
      file,
      {
        headers: { 'Content-Type': 'application/pdf' },
        signal,
        timeout: 120_000,
      },
    )
    return response.data
  },

  async listGenerationJobs(subjectId: string, signal?: AbortSignal): Promise<GenerationJob[]> {
    const response = await api.get<GenerationJobList>('/flashcards/generation-jobs', {
      params: { subject_id: subjectId },
      signal,
    })
    return response.data.jobs
  },

  async getGenerationJob(jobId: string, signal?: AbortSignal): Promise<GenerationJob> {
    const response = await api.get<GenerationJob>(`/flashcards/generation-jobs/${jobId}`, {
      signal,
    })
    return response.data
  },

  async cancelGenerationJob(jobId: string): Promise<GenerationJob> {
    const response = await api.post<GenerationJob>(
      `/flashcards/generation-jobs/${jobId}/cancel`,
    )
    return response.data
  },

  async chooseKnowledgeDuplicate(
    jobId: string,
    choice: KnowledgeDuplicateChoice,
    idempotencyKey: string,
  ): Promise<GenerationJob> {
    const response = await api.post<GenerationJob>(
      `/flashcards/generation-jobs/${jobId}/knowledge-choice`,
      { choice },
      { headers: { 'Idempotency-Key': idempotencyKey } },
    )
    return response.data
  },

  async chooseValidatedCardCount(
    jobId: string,
    cardCount: number,
    idempotencyKey: string,
  ): Promise<GenerationJob> {
    const response = await api.post<GenerationJob>(
      `/flashcards/generation-jobs/${jobId}/card-choice`,
      { card_count: cardCount },
      { headers: { 'Idempotency-Key': idempotencyKey } },
    )
    return response.data
  },

  async retryGenerationJob(jobId: string, idempotencyKey: string, acknowledgeAdditionalCost: boolean): Promise<GenerationJob> {
    const response = await api.post<GenerationJob>(
      `/flashcards/generation-jobs/${jobId}/retry`,
      acknowledgeAdditionalCost ? { acknowledge_additional_cost: true } : undefined,
      { headers: { 'Idempotency-Key': idempotencyKey } },
    )
    return response.data
  },

  async getGenerationLimits(signal?: AbortSignal): Promise<GenerationLimits> {
    const response = await api.get<GenerationLimits>('/flashcards/generation-limits', { signal })
    return response.data
  },

  async updateCard(id: string, data: FlashcardUpdate): Promise<Flashcard> {
    const response = await api.put<Flashcard>(`/flashcards/${id}`, data)
    return response.data
  },

  async deleteCard(id: string): Promise<void> {
    await api.delete<void>(`/flashcards/${id}`)
  },

  async approveAll(setId: string): Promise<ApproveAllResponse> {
    const response = await api.post<ApproveAllResponse>(`/flashcards/sets/${setId}/approve-all`)
    return response.data
  },
}
