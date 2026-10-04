import { PDFDataRangeTransport } from 'pdfjs-dist'

export const PDF_RANGE_CHUNK_BYTES = 256 * 1024

type RangeLoader = (begin: number, end: number, signal: AbortSignal) => Promise<ArrayBuffer>

/** Serial authenticated range requests; never hand a bearer token or source URL to PDF.js. */
export class AuthenticatedPdfRangeTransport extends PDFDataRangeTransport {
  private controller = new AbortController()
  private pending: Promise<void> = Promise.resolve()
  private requestedBytes = 0
  private requestCount = 0
  private loader: RangeLoader
  private onFailure: (caught: unknown) => void

  constructor(length: number, initialData: Uint8Array, loader: RangeLoader, onFailure: (caught: unknown) => void) {
    super(length, initialData, false)
    this.loader = loader
    this.onFailure = onFailure
    this.requestedBytes = initialData.byteLength
  }

  override requestDataRange(begin: number, end: number): void {
    this.pending = this.pending.then(async () => {
      if (this.controller.signal.aborted) return
      if (!Number.isSafeInteger(begin) || !Number.isSafeInteger(end) || begin < 0 || end <= begin || end > this.length) {
        throw new Error('invalid_pdf_range')
      }
      for (let offset = begin; offset < end; offset += PDF_RANGE_CHUNK_BYTES) {
        const nextEnd = Math.min(offset + PDF_RANGE_CHUNK_BYTES, end)
        this.requestedBytes += nextEnd - offset
        this.requestCount += 1
        // Bound pathological repeated PDF requests as well as individual response size.
        if (this.requestedBytes > this.length * 2 || this.requestCount > 800) throw new Error('pdf_range_budget')
        const data = await this.loader(offset, nextEnd, this.controller.signal)
        if (this.controller.signal.aborted) return
        this.onDataRange(offset, new Uint8Array(data))
      }
    }).catch((caught: unknown) => {
      if (!this.controller.signal.aborted) {
        this.controller.abort()
        this.onFailure(caught)
      }
    })
  }

  override abort(): void {
    this.controller.abort()
  }
}
