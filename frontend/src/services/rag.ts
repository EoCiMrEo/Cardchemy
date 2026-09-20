import api from './api'
import type { RagAnswerJob, RagHistory, RagProfile, RagSource, RagThread } from './types'

export const ragService = {
  async getProfile(subjectId: string, signal?: AbortSignal): Promise<RagProfile> {
    const response = await api.get<RagProfile>(`/subjects/${subjectId}/rag/profile`, { signal })
    return response.data
  },

  async listThreads(subjectId: string, signal?: AbortSignal): Promise<RagThread[]> {
    const response = await api.get<{ threads: RagThread[] }>(
      `/subjects/${subjectId}/rag/threads`,
      { signal },
    )
    return response.data.threads
  },

  async createThread(subjectId: string, signal?: AbortSignal): Promise<RagThread> {
    const response = await api.post<RagThread>(
      `/subjects/${subjectId}/rag/threads`,
      undefined,
      { signal },
    )
    return response.data
  },

  async getHistory(subjectId: string, threadId: string, signal?: AbortSignal): Promise<RagHistory> {
    const response = await api.get<RagHistory>(
      `/subjects/${subjectId}/rag/threads/${threadId}`,
      { signal },
    )
    return response.data
  },

  async deleteThread(subjectId: string, threadId: string): Promise<void> {
    await api.delete(`/subjects/${subjectId}/rag/threads/${threadId}`)
  },

  async listJobs(
    subjectId: string,
    threadId: string,
    signal?: AbortSignal,
  ): Promise<RagAnswerJob[]> {
    const response = await api.get<{ jobs: RagAnswerJob[] }>(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs`,
      { signal },
    )
    return response.data.jobs
  },

  async ask(
    subjectId: string,
    threadId: string,
    question: string,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): Promise<RagAnswerJob> {
    const response = await api.post<RagAnswerJob>(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs`,
      { question, document_ids: [] },
      { headers: { 'Idempotency-Key': idempotencyKey }, signal },
    )
    return response.data
  },

  async getJob(
    subjectId: string,
    threadId: string,
    jobId: string,
    signal?: AbortSignal,
  ): Promise<RagAnswerJob> {
    const response = await api.get<RagAnswerJob>(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs/${jobId}`,
      { signal },
    )
    return response.data
  },

  async cancelJob(subjectId: string, threadId: string, jobId: string): Promise<RagAnswerJob> {
    const response = await api.post<RagAnswerJob>(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs/${jobId}/cancel`,
    )
    return response.data
  },

  async retryJob(
    subjectId: string,
    threadId: string,
    jobId: string,
    idempotencyKey: string,
  ): Promise<RagAnswerJob> {
    const response = await api.post<RagAnswerJob>(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs/${jobId}/retry`,
      undefined,
      { headers: { 'Idempotency-Key': idempotencyKey } },
    )
    return response.data
  },

  async getSources(
    subjectId: string,
    threadId: string,
    messageId: string,
    signal?: AbortSignal,
  ): Promise<RagSource[]> {
    const response = await api.get<RagSource[]>(
      `/subjects/${subjectId}/rag/threads/${threadId}/messages/${messageId}/sources`,
      { signal },
    )
    return response.data
  },
}
