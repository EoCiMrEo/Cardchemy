import { expect, it } from 'vitest'
import type { PDFPageProxy } from 'pdfjs-dist'

import { MAX_PDF_TEXT_CHARACTERS, MAX_PDF_TEXT_ITEMS, readBoundedPdfText } from '@/components/rag/boundedPdfText'

type TextContent = Awaited<ReturnType<PDFPageProxy['getTextContent']>>

function textChunk(value: string, hasEOL = false): TextContent {
  return { items: [{ str: value, hasEOL }], styles: {}, lang: 'en' } as TextContent
}

it('collects bounded PDF text and styles for a selectable layer and readable alternative', async () => {
  const stream = new ReadableStream<TextContent>({
    start(controller) {
      controller.enqueue(textChunk('First', true))
      controller.enqueue(textChunk('Second'))
      controller.close()
    },
  })
  const result = await readBoundedPdfText(stream.getReader())
  expect(result).toMatchObject({ exceeded: false, text: 'First\nSecond' })
  expect(result.content?.items).toHaveLength(2)
})

it('cancels oversized text before creating a text layer or retaining its content', async () => {
  let cancelled = false
  let cancellationReason: unknown
  const stream = new ReadableStream<TextContent>({
    pull(controller) { controller.enqueue(textChunk('x'.repeat(MAX_PDF_TEXT_CHARACTERS + 1))) },
    cancel(reason) { cancelled = true; cancellationReason = reason },
  })
  const result = await readBoundedPdfText(stream.getReader())
  expect(result).toEqual({ exceeded: true, content: null, text: '' })
  await expect.poll(() => cancelled).toBe(true)
  expect(cancellationReason).toBeInstanceOf(Error)
  expect((cancellationReason as Error).message).toBe('pdf_text_limit')
})

it('caps item count even when individual items are short', async () => {
  const item = textChunk('x').items[0]
  const stream = new ReadableStream<TextContent>({
    pull(controller) { controller.enqueue({ items: Array(MAX_PDF_TEXT_ITEMS + 1).fill(item), styles: {}, lang: null }) },
  })
  const result = await readBoundedPdfText(stream.getReader())
  expect(result.exceeded).toBe(true)
})
