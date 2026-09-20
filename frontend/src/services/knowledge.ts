import api from './api'
import type { GenerationJob, KnowledgeDocument, KnowledgeJobCreate } from './types'

export const knowledgeService = {
  async listDocuments(subjectId: string, signal?: AbortSignal): Promise<KnowledgeDocument[]> {
    const response = await api.get<{ documents: KnowledgeDocument[] }>(
      `/subjects/${subjectId}/knowledge/documents`,
      { signal },
    )
    return response.data.documents
  },

  async createUpload(
    data: KnowledgeJobCreate,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): Promise<GenerationJob> {
    const response = await api.post<GenerationJob>('/flashcards/knowledge-jobs', data, {
      headers: { 'Idempotency-Key': idempotencyKey },
      signal,
    })
    return response.data
  },

  async uploadSource(jobId: string, file: File, signal?: AbortSignal): Promise<GenerationJob> {
    const response = await api.put<GenerationJob>(
      `/flashcards/knowledge-jobs/${jobId}/source`,
      file,
      {
        headers: { 'Content-Type': 'application/pdf' },
        signal,
        timeout: 120_000,
      },
    )
    return response.data
  },

  async reviewPublish(subjectId: string, documentId: string): Promise<KnowledgeDocument> {
    const response = await api.post<KnowledgeDocument>(
      `/subjects/${subjectId}/knowledge/documents/${documentId}/review-publish`,
    )
    return response.data
  },

  async unpublish(subjectId: string, documentId: string): Promise<KnowledgeDocument> {
    const response = await api.post<KnowledgeDocument>(
      `/subjects/${subjectId}/knowledge/documents/${documentId}/unpublish`,
    )
    return response.data
  },

  async retryIndex(subjectId: string, documentId: string): Promise<KnowledgeDocument> {
    const response = await api.post<KnowledgeDocument>(
      `/subjects/${subjectId}/knowledge/documents/${documentId}/retry-index`,
    )
    return response.data
  },

  async remove(subjectId: string, documentId: string): Promise<void> {
    await api.delete(`/subjects/${subjectId}/knowledge/documents/${documentId}`)
  },
}
