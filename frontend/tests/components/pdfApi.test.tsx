import { beforeEach, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ head: vi.fn(), get: vi.fn() }))
vi.mock('@/services/api', () => ({ default: mocks }))
import { ragService } from '@/services/rag'

beforeEach(() => { mocks.head.mockReset(); mocks.get.mockReset() })

it('reads bounded PDF metadata through the authenticated service with abort and timeout', async () => {
  mocks.head.mockResolvedValue({ headers: { 'content-length': '4096', 'x-pdf-page-count': '12', 'accept-ranges': 'bytes' } })
  const signal = new AbortController().signal
  expect(await ragService.getOriginalPdfMetadata('s', 't', 'j', 2, signal)).toEqual({ byte_length: 4096, page_count: 12 })
  expect(mocks.head).toHaveBeenCalledWith('/subjects/s/rag/threads/t/answer-jobs/j/related-excerpts/2/original-pdf', { signal, timeout: 15000 })
})

it('rejects missing, oversized and malformed metadata', async () => {
  for (const headers of [
    {}, { 'content-length': String(101 * 1024 * 1024), 'x-pdf-page-count': '1', 'accept-ranges': 'bytes' },
    { 'content-length': '4096', 'x-pdf-page-count': '0', 'accept-ranges': 'bytes' },
    { 'content-length': '4096', 'x-pdf-page-count': '12', 'accept-ranges': 'none' },
  ]) {
    mocks.head.mockResolvedValue({ headers })
    await expect(ragService.getOriginalPdfMetadata('s', 't', 'j', 1)).rejects.toThrow('invalid_pdf_metadata')
  }
})

it('accepts only exact 206 PDF ranges and refuses a full-file response', async () => {
  const data = new ArrayBuffer(16)
  mocks.get.mockResolvedValue({ status: 206, data, headers: { 'content-range': 'bytes 8-23/100' } })
  expect(await ragService.getOriginalPdfRange('s', 't', 'j', 1, 8, 24, 100)).toBe(data)
  expect(mocks.get).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ responseType: 'arraybuffer', headers: { Range: 'bytes=8-23' } }))
  for (const response of [
    { status: 200, data, headers: { 'content-range': 'bytes 8-23/100' } },
    { status: 206, data, headers: { 'content-range': 'bytes 8-23/101' } },
    { status: 206, data: new ArrayBuffer(15), headers: { 'content-range': 'bytes 8-23/100' } },
  ]) {
    mocks.get.mockResolvedValue(response)
    await expect(ragService.getOriginalPdfRange('s', 't', 'j', 1, 8, 24, 100)).rejects.toThrow('invalid_pdf_range_response')
  }
})

it('rejects invalid and oversized ranges before making any request', async () => {
  for (const [begin, end, total] of [[-1, 10, 100], [10, 10, 100], [0, 101, 100], [0, 9 * 1024 * 1024, 10 * 1024 * 1024]]) {
    await expect(ragService.getOriginalPdfRange('s', 't', 'j', 1, begin, end, total)).rejects.toThrow('invalid_pdf_range')
  }
  expect(mocks.get).not.toHaveBeenCalled()
})
