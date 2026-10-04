import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { FileText, Loader2, Search } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { publishedKnowledgeService } from '@/services/publishedKnowledge'
import type { PublishedKnowledgeDocument, PublishedKnowledgePage, PublishedKnowledgeSearchHit } from '@/services/types'

const OriginalPdfPage = lazy(() => import('@/components/rag/OriginalPdfPage'))

export function PublishedKnowledgeBrowser({ subjectId }: { subjectId: string }) {
  const [documents, setDocuments] = useState<PublishedKnowledgeDocument[]>([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PublishedKnowledgeSearchHit[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [pageLoading, setPageLoading] = useState(false)
  const [page, setPage] = useState<(PublishedKnowledgePage & { documentId: string }) | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const listController = useRef<AbortController | null>(null)
  const searchController = useRef<AbortController | null>(null)
  const pageController = useRef<AbortController | null>(null)
  const trigger = useRef<HTMLElement | null>(null)
  const section = useRef<HTMLElement | null>(null)

  const load = useCallback(async () => {
    listController.current?.abort()
    searchController.current?.abort()
    setResults(null)
    setSearchError(null)
    setSearching(false)
    const controller = new AbortController()
    listController.current = controller
    setLoading(true)
    setListError(null)
    try {
      const current = await publishedKnowledgeService.list(subjectId, controller.signal)
      if (!controller.signal.aborted) setDocuments(current)
    } catch (caught: unknown) {
      if (!controller.signal.aborted) {
        setDocuments([])
        setListError(apiErrorMessage(caught, copy.publishedKnowledge.loadFailed))
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [subjectId])

  useEffect(() => {
    let disposed = false
    queueMicrotask(() => { if (!disposed) void load() })
    return () => {
      disposed = true
      listController.current?.abort()
      searchController.current?.abort()
      pageController.current?.abort()
    }
  }, [load])

  const search = async () => {
    const value = query.trim()
    if (!value || value.length > 200) return
    searchController.current?.abort()
    const controller = new AbortController()
    searchController.current = controller
    setSearching(true)
    setSearchError(null)
    setResults(null)
    try {
      const pages = await publishedKnowledgeService.search(subjectId, value, controller.signal)
      if (!controller.signal.aborted) setResults(pages)
    } catch (caught: unknown) {
      if (!controller.signal.aborted) setSearchError(apiErrorMessage(caught, copy.publishedKnowledge.searchFailed))
    } finally {
      if (!controller.signal.aborted) setSearching(false)
    }
  }

  const openPage = async (documentId: string, pageNumber: number) => {
    trigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    pageController.current?.abort()
    const controller = new AbortController()
    pageController.current = controller
    setDialogOpen(true)
    setPage(null)
    setPageError(null)
    setPageLoading(true)
    try {
      const current = await publishedKnowledgeService.page(subjectId, documentId, pageNumber, controller.signal)
      if (!controller.signal.aborted) setPage({ ...current, documentId })
    } catch (caught: unknown) {
      if (!controller.signal.aborted) setPageError(apiErrorMessage(caught, copy.publishedKnowledge.pageUnavailable))
    } finally {
      if (!controller.signal.aborted) setPageLoading(false)
    }
  }

  const close = useCallback(() => {
    pageController.current?.abort()
    setDialogOpen(false)
    setPage(null)
    setPageError(null)
  }, [])

  const handleAccessChanged = useCallback(() => {
    trigger.current = section.current
    close()
    void load()
  }, [close, load])

  return <section ref={section} id="published-knowledge" aria-labelledby="published-knowledge-title" className="scroll-mt-6" tabIndex={-1}>
    <Card>
      <CardHeader>
        <CardTitle id="published-knowledge-title" className="flex items-center gap-2 text-xl">
          <FileText className="h-5 w-5 text-blue-600" aria-hidden="true" />{copy.publishedKnowledge.title}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{copy.publishedKnowledge.description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? <p role="status" className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{copy.common.loading}</p> : null}
        {listError ? <div role="alert" className="flex flex-wrap items-center gap-3"><p>{listError}</p><Button type="button" variant="outline" onClick={() => void load()}>{copy.common.retry}</Button></div> : null}
        {!loading && !listError && documents.length === 0 ? <p>{copy.publishedKnowledge.empty}</p> : null}
        {!loading && documents.length > 0 ? <>
          <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); void search() }}>
            <div className="min-w-44 flex-1">
              <label htmlFor="published-knowledge-query" className="block text-sm font-medium">{copy.publishedKnowledge.searchLabel}</label>
              <input id="published-knowledge-query" value={query} onChange={(event) => setQuery(event.target.value)}
                maxLength={200} className="mt-1 min-h-11 w-full rounded border px-3" />
            </div>
            <Button type="submit" disabled={!query.trim() || searching}><Search className="mr-1 h-4 w-4" aria-hidden="true" />{copy.publishedKnowledge.search}</Button>
            {results !== null ? <Button type="button" variant="outline" onClick={() => { searchController.current?.abort(); setResults(null); setSearchError(null) }}>{copy.publishedKnowledge.clear}</Button> : null}
          </form>
          {searchError ? <p role="alert" className="text-sm text-red-700">{searchError}</p> : null}
          {searching ? <p role="status">{copy.publishedKnowledge.searching}</p> : null}
          {results !== null && !searching ? <div aria-live="polite" className="space-y-2">
            <h3 className="font-medium">{copy.publishedKnowledge.results}</h3>
            {results.length === 0 ? <p className="text-sm">{copy.publishedKnowledge.noResults}</p> : null}
            <ul className="space-y-1">{results.map((hit) => <li key={`${hit.document_id}-${hit.page_number}`}>
              <Button type="button" variant="link" className="h-auto min-h-11 whitespace-normal text-left" onClick={() => void openPage(hit.document_id, hit.page_number)}>
                {copy.publishedKnowledge.openPage(hit.document_title, hit.page_number)}
              </Button>
            </li>)}</ul>
          </div> : null}
          <div>
            <h3 className="font-medium">{copy.publishedKnowledge.lectures}</h3>
            <ul className="mt-2 space-y-1">{documents.map((item) => <li key={item.id}>
              <Button type="button" variant="link" className="h-auto min-h-11 whitespace-normal text-left" onClick={() => void openPage(item.id, 1)}>
                {copy.publishedKnowledge.openLecture(item.title, item.page_count)}
              </Button>
            </li>)}</ul>
          </div>
        </> : null}
      </CardContent>
    </Card>
    <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open) close() }}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] max-w-4xl overflow-y-auto [scrollbar-gutter:stable]" onCloseAutoFocus={(event) => {
        event.preventDefault()
        const target = trigger.current?.isConnected ? trigger.current : section.current
        target?.focus()
        trigger.current = null
      }}>
        <DialogHeader>
          <DialogTitle>{copy.publishedKnowledge.pageTitle}</DialogTitle>
          <DialogDescription>{copy.publishedKnowledge.pageDescription}</DialogDescription>
        </DialogHeader>
        {pageLoading ? <p role="status">{copy.askAi.pageLoading}</p> : null}
        {pageError ? <p role="alert">{pageError}</p> : null}
        {page ? <div className="min-w-0 space-y-3">
          <p className="font-medium">{copy.publishedKnowledge.openedPage(page.document_title, page.page_number)}</p>
          <Suspense fallback={<p role="status">{copy.askAi.pdfLoading}</p>}>
            <OriginalPdfPage key={`${page.documentId}-${page.page_number}`} subjectId={subjectId}
              documentId={page.documentId} initialPageNumber={page.page_number}
              onAccessChanged={handleAccessChanged} />
          </Suspense>
          <details className="rounded border p-3">
            <summary className="min-h-11 cursor-pointer font-medium">{copy.publishedKnowledge.openedPageText(page.page_number)}</summary>
            <p className="whitespace-pre-wrap break-words">{page.page_content}</p>
            {page.truncated ? <p className="text-sm text-amber-800">{copy.publishedKnowledge.extractedTextTruncated}</p> : null}
          </details>
        </div> : null}
      </DialogContent>
    </Dialog>
  </section>
}
