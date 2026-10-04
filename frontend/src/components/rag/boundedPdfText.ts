import type { PDFPageProxy } from 'pdfjs-dist'

type TextContent = Awaited<ReturnType<PDFPageProxy['getTextContent']>>

export const MAX_PDF_TEXT_ITEMS = 10_000
export const MAX_PDF_TEXT_CHARACTERS = 100_000
const MAX_PDF_TEXT_STYLES = 2_000

export type BoundedPdfText =
  | { exceeded: false; content: TextContent; text: string }
  | { exceeded: true; content: null; text: '' }

/** Stop a pathological text stream before creating thousands of DOM nodes. */
export async function readBoundedPdfText(reader: ReadableStreamDefaultReader<TextContent>): Promise<BoundedPdfText> {
  const items: TextContent['items'] = []
  const styles = Object.create(null) as TextContent['styles']
  const textParts: string[] = []
  let characters = 0
  let styleCount = 0
  let lang: string | null = null

  while (true) {
    const next = await reader.read()
    if (next.done) return { exceeded: false, content: { items, styles, lang }, text: textParts.join('').trim() }
    const chunk = next.value
    if (items.length + chunk.items.length > MAX_PDF_TEXT_ITEMS) break
    for (const item of chunk.items) {
      if ('str' in item) {
        characters += item.str.length
        if (characters > MAX_PDF_TEXT_CHARACTERS) break
        textParts.push(item.str, item.hasEOL ? '\n' : ' ')
      }
    }
    if (characters > MAX_PDF_TEXT_CHARACTERS) break
    for (const name in chunk.styles) {
      if (!Object.hasOwn(chunk.styles, name)) continue
      if (!Object.hasOwn(styles, name)) styleCount += 1
      if (styleCount > MAX_PDF_TEXT_STYLES) break
      styles[name] = chunk.styles[name]
    }
    if (styleCount > MAX_PDF_TEXT_STYLES) break
    items.push(...chunk.items)
    lang = chunk.lang ?? lang
  }
  // The full PDF still renders; its bounded canonical extraction remains below.
  // PDF.js requires an Error reason so its worker stream closes consistently.
  void reader.cancel(new Error('pdf_text_limit')).catch(() => {})
  return { exceeded: true, content: null, text: '' }
}
