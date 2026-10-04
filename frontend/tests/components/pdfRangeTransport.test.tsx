import { expect, it, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({ received: vi.fn() }))
vi.mock('pdfjs-dist', () => ({
  PDFDataRangeTransport: class {
    length: number
    onDataRange = mocks.received
    constructor(length: number) { this.length = length }
  },
}))

import { AuthenticatedPdfRangeTransport, PDF_RANGE_CHUNK_BYTES } from '@/components/rag/pdfRangeTransport'

beforeEach(() => mocks.received.mockReset())

it('serializes PDF ranges and divides larger requests into bounded pieces', async () => {
  const length = PDF_RANGE_CHUNK_BYTES * 3
  let active = 0
  let maximumActive = 0
  const loader = vi.fn(async (begin: number, end: number) => {
    active += 1
    maximumActive = Math.max(maximumActive, active)
    await Promise.resolve()
    active -= 1
    return new ArrayBuffer(end - begin)
  })
  const failure = vi.fn()
  const transport = new AuthenticatedPdfRangeTransport(length, new Uint8Array(1), loader, failure)
  transport.requestDataRange(0, PDF_RANGE_CHUNK_BYTES * 2)
  transport.requestDataRange(PDF_RANGE_CHUNK_BYTES * 2, length)
  await vi.waitFor(() => expect(mocks.received).toHaveBeenCalledTimes(3))
  expect(maximumActive).toBe(1)
  expect(loader.mock.calls.map(([begin, end]) => end - begin)).toEqual(Array(3).fill(PDF_RANGE_CHUNK_BYTES))
  expect(failure).not.toHaveBeenCalled()
})

it('aborts in-flight work and never delivers cancelled bytes or issues queued requests', async () => {
  let finish: ((value: ArrayBuffer) => void) | undefined
  const loader = vi.fn((begin: number, end: number, signal: AbortSignal) => {
    expect(end).toBeGreaterThan(begin)
    expect(signal.aborted).toBe(false)
    return new Promise<ArrayBuffer>((resolve) => { finish = resolve })
  })
  const failure = vi.fn()
  const transport = new AuthenticatedPdfRangeTransport(100, new Uint8Array(1), loader, failure)
  transport.requestDataRange(0, 20)
  transport.requestDataRange(20, 40)
  await vi.waitFor(() => expect(loader).toHaveBeenCalledTimes(1))
  const signal = loader.mock.calls[0][2]
  transport.abort()
  expect(signal.aborted).toBe(true)
  finish?.(new ArrayBuffer(20))
  await Promise.resolve()
  await Promise.resolve()
  expect(mocks.received).not.toHaveBeenCalled()
  expect(loader).toHaveBeenCalledTimes(1)
  expect(failure).not.toHaveBeenCalled()
})

it('reports one request failure and fences subsequent work', async () => {
  const loader = vi.fn().mockRejectedValue(new Error('safe_test_failure'))
  const failure = vi.fn()
  const transport = new AuthenticatedPdfRangeTransport(100, new Uint8Array(1), loader, failure)
  transport.requestDataRange(0, 20)
  transport.requestDataRange(20, 40)
  await vi.waitFor(() => expect(failure).toHaveBeenCalledTimes(1))
  expect(loader).toHaveBeenCalledTimes(1)
  expect(mocks.received).not.toHaveBeenCalled()
})

it('rejects malformed ranges and pathological repeated byte requests', async () => {
  const invalidLoader = vi.fn()
  const invalidFailure = vi.fn()
  const invalid = new AuthenticatedPdfRangeTransport(10, new Uint8Array(1), invalidLoader, invalidFailure)
  invalid.requestDataRange(0, 11)
  await vi.waitFor(() => expect(invalidFailure).toHaveBeenCalledTimes(1))
  expect(invalidLoader).not.toHaveBeenCalled()

  const loader = vi.fn(async (begin: number, end: number) => new ArrayBuffer(end - begin))
  const failure = vi.fn()
  const repeated = new AuthenticatedPdfRangeTransport(10, new Uint8Array(1), loader, failure)
  repeated.requestDataRange(0, 10)
  repeated.requestDataRange(0, 10)
  await vi.waitFor(() => expect(failure).toHaveBeenCalledTimes(1))
  expect(loader).toHaveBeenCalledTimes(1)
})
