import api from './api'
import type { PublishedKnowledgeDocument, PublishedKnowledgePage, PublishedKnowledgeSearchHit, RagOriginalPdfMetadata } from './types'

const root = (subjectId: string) => `/subjects/${subjectId}/published-knowledge`

export const publishedKnowledgeService = {
  async list(subjectId: string, signal?: AbortSignal): Promise<PublishedKnowledgeDocument[]> {
    const response = await api.get<{ documents: PublishedKnowledgeDocument[] }>(`${root(subjectId)}/documents`, { signal })
    return response.data.documents
  },

  async search(subjectId: string, query: string, signal?: AbortSignal): Promise<PublishedKnowledgeSearchHit[]> {
    const response = await api.get<{ pages: PublishedKnowledgeSearchHit[] }>(`${root(subjectId)}/search`, {
      params: { q: query }, signal,
    })
    return response.data.pages
  },

  async page(subjectId: string, documentId: string, pageNumber: number, signal?: AbortSignal): Promise<PublishedKnowledgePage> {
    const response = await api.get<PublishedKnowledgePage>(
      `${root(subjectId)}/documents/${documentId}/pages/${pageNumber}`, { signal },
    )
    return response.data
  },

  async metadata(subjectId: string, documentId: string, signal?: AbortSignal): Promise<RagOriginalPdfMetadata> {
    const response = await api.head(`${root(subjectId)}/documents/${documentId}/original-pdf`, { signal, timeout: 15_000 })
    const byteLength = Number(response.headers['content-length'])
    const pageCount = Number(response.headers['x-pdf-page-count'])
    if (!Number.isSafeInteger(byteLength) || byteLength <= 0 || byteLength > 100 * 1024 * 1024
      || !Number.isSafeInteger(pageCount) || pageCount <= 0 || pageCount > 100
      || response.headers['accept-ranges'] !== 'bytes') throw new Error('invalid_pdf_metadata')
    return { byte_length: byteLength, page_count: pageCount }
  },

  async range(subjectId: string, documentId: string, begin: number, end: number,
    totalBytes: number, signal?: AbortSignal): Promise<ArrayBuffer> {
    if (!Number.isSafeInteger(totalBytes) || totalBytes <= 0 || totalBytes > 100 * 1024 * 1024
      || !Number.isSafeInteger(begin) || !Number.isSafeInteger(end) || begin < 0 || end <= begin
      || end > totalBytes || end - begin > 8 * 1024 * 1024) throw new Error('invalid_pdf_range')
    const response = await api.get<ArrayBuffer>(`${root(subjectId)}/documents/${documentId}/original-pdf`, {
      responseType: 'arraybuffer', headers: { Range: `bytes=${begin}-${end - 1}` }, signal, timeout: 15_000,
    })
    if (response.status !== 206 || !(response.data instanceof ArrayBuffer) || response.data.byteLength !== end - begin
      || response.headers['content-range'] !== `bytes ${begin}-${end - 1}/${totalBytes}`) throw new Error('invalid_pdf_range_response')
    return response.data
  },
}
