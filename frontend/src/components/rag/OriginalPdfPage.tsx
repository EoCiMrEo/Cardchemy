import { useCallback, useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { getDocument, GlobalWorkerOptions, TextLayer } from 'pdfjs-dist'
import type { PDFDocumentLoadingTask, PDFDocumentProxy, PDFPageProxy, RenderTask } from 'pdfjs-dist'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

import { Button } from '@/components/ui/button'
import { copy } from '@/i18n/en'
import { ragService } from '@/services/rag'
import { publishedKnowledgeService } from '@/services/publishedKnowledge'
import { AuthenticatedPdfRangeTransport, PDF_RANGE_CHUNK_BYTES } from './pdfRangeTransport'
import { readBoundedPdfText } from './boundedPdfText'
import './originalPdfPage.css'

// The worker asset was previously served as octet-stream with immutable caching.
// Version its request once so browsers fetch the corrected JavaScript MIME type.
const workerUrl = new URL(pdfWorkerUrl, import.meta.url)
workerUrl.searchParams.set('mime', 'js-v1')
GlobalWorkerOptions.workerSrc = workerUrl.href
const MAX_CANVAS_PIXELS = 8_000_000
const PDF_FAILURE_CODES = new Set([
  'invalid_pdf_metadata', 'invalid_pdf_range', 'invalid_pdf_range_response',
  'pdf_range_budget', 'invalid_pdf_page', 'invalid_pdf_viewport',
])
const PDF_PARSER_ERRORS = new Set([
  'InvalidPDFException', 'MissingPDFException', 'PasswordException',
  'ResponseException', 'UnknownErrorException',
])

/** Content-free diagnostics for a viewer failure; never log the URL or exception. */
function reportPdfFailure(stage: string, caught: unknown): void {
  const status = isAxiosError(caught) ? caught.response?.status ?? null : null
  const message = caught instanceof Error ? caught.message : ''
  const code = PDF_FAILURE_CODES.has(message) ? message
    : caught instanceof Error && PDF_PARSER_ERRORS.has(caught.name) ? caught.name
      : /Setting up fake worker failed|Failed to fetch dynamically imported module|Failed to load module script/i.test(message)
        ? 'worker_module_load' : 'other'
  console.warn(`original_pdf_viewer_failure stage=${stage} status=${status ?? 'none'} code=${code}`)
}
type TextContent = Awaited<ReturnType<PDFPageProxy['getTextContent']>>
const accessDenied = (caught: unknown): boolean => isAxiosError(caught) && [401, 403, 404].includes(caught.response?.status ?? 0)

type OriginalPdfPageProps = {
  subjectId: string
  initialPageNumber: number
  onAccessChanged: () => void
} & (
  { documentId: string; threadId?: never; jobId?: never; excerptOrder?: never }
  | { documentId?: never; threadId: string; jobId: string; excerptOrder: number }
)

export default function OriginalPdfPage({ subjectId, documentId, threadId, jobId, excerptOrder, initialPageNumber, onAccessChanged }: OriginalPdfPageProps) {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null)
  const [pageNumber, setPageNumber] = useState(initialPageNumber)
  const [status, setStatus] = useState<'loading' | 'ready' | 'unavailable' | 'failed'>('loading')
  const [rendering, setRendering] = useState(true)
  const [pageText, setPageText] = useState('')
  const [textTooLarge, setTextTooLarge] = useState(false)
  // Wait for the real container width. Rendering at a temporary width causes a
  // cancelled PDF.js render and text stream as soon as ResizeObserver runs.
  const [width, setWidth] = useState(0)
  const [navigating, setNavigating] = useState(false)
  const metadataRef = useRef<{ byte_length: number; page_count: number } | null>(null)
  const navigationControllerRef = useRef<AbortController | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const surfaceRef = useRef<HTMLDivElement>(null)

  const verifyPage = useCallback((signal: AbortSignal) => documentId
    ? publishedKnowledgeService.page(subjectId, documentId, initialPageNumber, signal)
    : ragService.getRelatedPage(subjectId, threadId!, jobId!, excerptOrder!, signal),
  [documentId, subjectId, initialPageNumber, threadId, jobId, excerptOrder])
  const getMetadata = useCallback((signal: AbortSignal) => documentId
    ? publishedKnowledgeService.metadata(subjectId, documentId, signal)
    : ragService.getOriginalPdfMetadata(subjectId, threadId!, jobId!, excerptOrder!, signal),
  [documentId, subjectId, threadId, jobId, excerptOrder])
  const getRange = useCallback((begin: number, end: number, total: number, signal: AbortSignal) => documentId
    ? publishedKnowledgeService.range(subjectId, documentId, begin, end, total, signal)
    : ragService.getOriginalPdfRange(subjectId, threadId!, jobId!, excerptOrder!, begin, end, total, signal),
  [documentId, subjectId, threadId, jobId, excerptOrder])

  useEffect(() => {
    const controller = new AbortController()
    let loadingTask: PDFDocumentLoadingTask | null = null
    let transport: AuthenticatedPdfRangeTransport | null = null
    let failing = false
    const fail = async (caught: unknown, stage: string) => {
      if (controller.signal.aborted || failing) return
      failing = true
      reportPdfFailure(stage, caught)
      transport?.abort()
      void loadingTask?.destroy().catch(() => {})
      // An unavailable original can mean either absent PDF storage or revoked source access.
      // Recheck the authorized page before retaining any extracted text in the dialog.
      try {
        await verifyPage(controller.signal)
        if (!controller.signal.aborted) {
          setDocument(null)
          setPageText('')
          setTextTooLarge(false)
          setStatus(isAxiosError(caught) && caught.response?.status === 404 ? 'unavailable' : 'failed')
        }
      } catch (pageError: unknown) {
        if (!controller.signal.aborted) {
          if (accessDenied(pageError)) onAccessChanged()
          else {
            reportPdfFailure('page_recheck', pageError)
            setDocument(null)
            setPageText('')
            setTextTooLarge(false)
            setStatus('failed')
          }
        }
      }
    }
    const load = async () => {
      let stage = 'metadata'
      try {
        const metadata = await getMetadata(controller.signal)
        if (controller.signal.aborted) return
        metadataRef.current = metadata
        const loadRange = (begin: number, end: number, signal: AbortSignal) =>
          getRange(begin, end, metadata.byte_length, signal)
        stage = 'initial_range'
        const initial = await loadRange(0, Math.min(PDF_RANGE_CHUNK_BYTES, metadata.byte_length), controller.signal)
        if (controller.signal.aborted) return
        transport = new AuthenticatedPdfRangeTransport(metadata.byte_length, new Uint8Array(initial), loadRange, (caught) => { void fail(caught, 'range') })
        stage = 'pdf_load'
        loadingTask = getDocument({ range: transport, rangeChunkSize: PDF_RANGE_CHUNK_BYTES,
          disableAutoFetch: true, disableStream: true, enableXfa: false, useWasm: false,
          verbosity: 0, maxImageSize: MAX_CANVAS_PIXELS, canvasMaxAreaInBytes: MAX_CANVAS_PIXELS * 4 })
        const pdf = await loadingTask.promise
        if (controller.signal.aborted) return
        if (pdf.numPages !== metadata.page_count || !Number.isInteger(initialPageNumber) || initialPageNumber < 1 || initialPageNumber > pdf.numPages) {
          throw new Error('invalid_pdf_page')
        }
        setDocument(pdf)
        setStatus('ready')
      } catch (caught: unknown) {
        await fail(caught, stage)
      }
    }
    void load()
    return () => {
      controller.abort()
      transport?.abort()
      navigationControllerRef.current?.abort()
      void loadingTask?.destroy().catch(() => {})
    }
  }, [initialPageNumber, onAccessChanged, verifyPage, getMetadata, getRange])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.max(1, Math.min(860, entry.contentRect.width)))
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const surface = surfaceRef.current
    if (!document || !surface || width <= 0) return
    let stopped = false
    let renderTask: RenderTask | null = null
    let textLayer: TextLayer | null = null
    let textReader: ReadableStreamDefaultReader<TextContent> | null = null
    // A fresh canvas prevents a cancelled render racing a subsequent page/resize render.
    const canvas = window.document.createElement('canvas')
    const textContainer = window.document.createElement('div')
    canvas.setAttribute('aria-hidden', 'true')
    textContainer.className = 'lecture-pdf-text-layer'
    textContainer.setAttribute('aria-hidden', 'true')
    surface.replaceChildren(canvas, textContainer)
    const render = async () => {
      let stage = 'page_lookup'
      try {
        setRendering(true)
        setPageText('')
        setTextTooLarge(false)
        const page = await document.getPage(pageNumber)
        if (stopped) return
        const base = page.getViewport({ scale: 1 })
        const ratio = Math.min(window.devicePixelRatio || 1, 2)
        const scale = Math.min(width / base.width, Math.sqrt(MAX_CANVAS_PIXELS / (base.width * base.height)) / ratio)
        if (!Number.isFinite(scale) || scale <= 0) throw new Error('invalid_pdf_viewport')
        const viewport = page.getViewport({ scale })
        canvas.width = Math.max(1, Math.floor(viewport.width * ratio))
        canvas.height = Math.max(1, Math.floor(viewport.height * ratio))
        canvas.style.width = `${viewport.width}px`
        canvas.style.height = `${viewport.height}px`
        surface.style.width = `${viewport.width}px`
        surface.style.height = `${viewport.height}px`
        textContainer.style.setProperty('--total-scale-factor', String(viewport.scale))
        stage = 'canvas_setup'
        renderTask = page.render({ canvas, viewport, transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0] })
        // A resize may cancel the render while text is still streaming. Observe
        // its promise now, before awaiting text, so cancellation is not unhandled.
        const renderOutcome = renderTask.promise.then(
          () => ({ ok: true as const }),
          (caught: unknown) => ({ ok: false as const, caught }),
        )
        textReader = (page.streamTextContent() as ReadableStream<TextContent>).getReader()
        stage = 'text_read'
        const content = await readBoundedPdfText(textReader)
        if (stopped) return
        if (content.exceeded) {
          stage = 'canvas_render'
          const outcome = await renderOutcome
          if (!outcome.ok) throw outcome.caught
        } else {
          textLayer = new TextLayer({ textContentSource: content.content, container: textContainer, viewport })
          // Observe both promises immediately so a fast text-layer rejection is handled.
          const layerOutcome = textLayer.render().then(() => ({ ok: true as const }), (caught: unknown) => ({ ok: false as const, caught }))
          stage = 'canvas_render'
          const renderResult = await renderOutcome
          if (!renderResult.ok) throw renderResult.caught
          stage = 'text_layer'
          const outcome = await layerOutcome
          if (!outcome.ok) throw outcome.caught
        }
        if (stopped) return
        setPageText(content.text)
        setTextTooLarge(content.exceeded)
        setRendering(false)
      } catch (caught: unknown) {
        if (!stopped) {
          reportPdfFailure(stage, caught)
          void document.loadingTask.destroy().catch(() => {})
          setDocument(null)
          setPageText('')
          setTextTooLarge(false)
          setStatus('failed')
          setRendering(false)
        }
      }
    }
    void render()
    return () => {
      stopped = true
      renderTask?.cancel()
      textLayer?.cancel()
      // PDF.js requires an Error reason to close its worker-backed text stream.
      void textReader?.cancel(new Error('pdf_viewer_closed')).catch(() => {})
      surface.replaceChildren()
      canvas.width = 0
      canvas.height = 0
    }
  }, [document, pageNumber, width])

  const navigate = async (offset: number) => {
    if (navigating || rendering || !document) return
    const controller = new AbortController()
    navigationControllerRef.current?.abort()
    navigationControllerRef.current = controller
    setNavigating(true)
    const pdfFallback = (kind: 'unavailable' | 'failed') => {
      void document.loadingTask.destroy().catch(() => {})
      setDocument(null)
      setPageText('')
      setTextTooLarge(false)
      setRendering(false)
      setStatus(kind)
    }
    try {
      const [metadataResult, pageResult] = await Promise.allSettled([
        getMetadata(controller.signal),
        verifyPage(controller.signal),
      ])
      if (controller.signal.aborted) return
      if (pageResult.status === 'rejected' && accessDenied(pageResult.reason)) {
        onAccessChanged()
        return
      }
      if (metadataResult.status === 'rejected' && accessDenied(metadataResult.reason)
        && (!isAxiosError(metadataResult.reason) || metadataResult.reason.response?.status !== 404)) {
        onAccessChanged()
        return
      }
      if (pageResult.status === 'rejected') {
        pdfFallback('failed')
        return
      }
      if (metadataResult.status === 'rejected') {
        pdfFallback(isAxiosError(metadataResult.reason) && metadataResult.reason.response?.status === 404 ? 'unavailable' : 'failed')
        return
      }
      const metadata = metadataResult.value
      if (metadata.byte_length !== metadataRef.current?.byte_length || metadata.page_count !== document.numPages) {
        pdfFallback('failed')
        return
      }
      setRendering(true)
      setPageText('')
      setTextTooLarge(false)
      setPageNumber((current) => current + offset)
    } catch {
      if (!controller.signal.aborted) pdfFallback('failed')
    } finally {
      if (!controller.signal.aborted) setNavigating(false)
    }
  }

  return <div ref={containerRef} className="min-w-0 space-y-3">
    {status === 'loading' ? <p role="status" className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />{copy.askAi.pdfLoading}</p> : null}
    {status === 'unavailable' || status === 'failed' ? <p role={status === 'failed' ? 'alert' : 'status'} className="rounded border border-amber-200 bg-amber-50 p-3 text-amber-900">{status === 'unavailable' ? copy.askAi.pdfUnavailable : copy.askAi.pdfFailed}</p> : null}
    {status === 'ready' && document ? <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p role="status" className="text-sm font-medium">{copy.askAi.pdfPage(pageNumber, document.numPages)}</p>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" className="min-h-11" disabled={navigating || rendering || pageNumber <= 1} onClick={() => void navigate(-1)}><ChevronLeft aria-hidden="true" className="h-4 w-4" /><span>{copy.askAi.pdfPrevious}</span></Button>
          <Button type="button" variant="outline" size="sm" className="min-h-11" disabled={navigating || rendering || pageNumber >= document.numPages} onClick={() => void navigate(1)}><span>{copy.askAi.pdfNext}</span><ChevronRight aria-hidden="true" className="h-4 w-4" /></Button>
        </div>
      </div>
      {rendering ? <p role="status">{copy.askAi.pdfRendering}</p> : null}
    </> : null}
    <div className={status === 'ready' ? 'min-w-0 overflow-hidden rounded border bg-slate-100' : 'hidden'} role="img" aria-label={copy.askAi.pdfPage(pageNumber, document?.numPages ?? initialPageNumber)}>
      <div ref={surfaceRef} className="relative mx-auto bg-white" />
    </div>
    {status === 'ready' && !rendering ? <details className="rounded border p-3">
      <summary className="min-h-11 cursor-pointer font-medium">{copy.askAi.pdfPageText}</summary>
      <p className="mt-2 whitespace-pre-wrap break-words">{textTooLarge ? copy.askAi.pdfTextTooLarge : pageText || copy.askAi.pdfNoText}</p>
    </details> : null}
  </div>
}
