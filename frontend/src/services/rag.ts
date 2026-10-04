import api from './api'
import type { RagAnswerJob, RagHistory, RagOriginalPdfMetadata, RagProfile, RagRelatedPage, RagSource, RagThread } from './types'

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
      { signal, params: { limit: 100 } },
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

  async getRelatedPage(
    subjectId: string,
    threadId: string,
    jobId: string,
    excerptOrder: number,
    signal?: AbortSignal,
  ): Promise<RagRelatedPage> {
    const response = await api.get<RagRelatedPage>(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs/${jobId}/related-excerpts/${excerptOrder}/page`,
      { signal },
    )
    return response.data
  },

  async getOriginalPdfMetadata(
    subjectId: string,
    threadId: string,
    jobId: string,
    excerptOrder: number,
    signal?: AbortSignal,
  ): Promise<RagOriginalPdfMetadata> {
    const response = await api.head(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs/${jobId}/related-excerpts/${excerptOrder}/original-pdf`,
      { signal, timeout: 15_000 },
    )
    const byteLength = Number(response.headers['content-length'])
    const pageCount = Number(response.headers['x-pdf-page-count'])
    if (!Number.isSafeInteger(byteLength) || byteLength <= 0 || byteLength > 100 * 1024 * 1024
      || !Number.isSafeInteger(pageCount) || pageCount <= 0
      || response.headers['accept-ranges'] !== 'bytes') throw new Error('invalid_pdf_metadata')
    return { byte_length: byteLength, page_count: pageCount }
  },

  async getOriginalPdfRange(
    subjectId: string,
    threadId: string,
    jobId: string,
    excerptOrder: number,
    begin: number,
    end: number,
    totalBytes: number,
    signal?: AbortSignal,
  ): Promise<ArrayBuffer> {
    if (!Number.isSafeInteger(totalBytes) || totalBytes <= 0 || totalBytes > 100 * 1024 * 1024
      || !Number.isSafeInteger(begin) || !Number.isSafeInteger(end) || begin < 0 || end <= begin
      || end > totalBytes || end - begin > 8 * 1024 * 1024) throw new Error('invalid_pdf_range')
    const response = await api.get<ArrayBuffer>(
      `/subjects/${subjectId}/rag/threads/${threadId}/answer-jobs/${jobId}/related-excerpts/${excerptOrder}/original-pdf`,
      { responseType: 'arraybuffer', headers: { Range: `bytes=${begin}-${end - 1}` }, signal, timeout: 15_000 },
    )
    if (response.status !== 206 || !(response.data instanceof ArrayBuffer) || response.data.byteLength !== end - begin
      || response.headers['content-range'] !== `bytes ${begin}-${end - 1}/${totalBytes}`) throw new Error('invalid_pdf_range_response')
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
