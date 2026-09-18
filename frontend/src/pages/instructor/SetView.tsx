import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, ChevronLeft, Loader2, Play, Save, Trash2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { PageError } from '@/components/feedback/PageError'
import { PreviewDialog } from '@/components/sets/PreviewDialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { flashcardService } from '@/services/flashcards'
import { subjectService } from '@/services/subjects'
import type { Flashcard, FlashcardSet } from '@/services/types'

interface EditValues {
  front: string
  options: [string, string, string, string]
  correctOptionIndex: number
}

const EMPTY_EDIT: EditValues = {
  front: '',
  options: ['', '', '', ''],
  correctOptionIndex: 0,
}

function validateEdit(values: EditValues): string | null {
  if (!values.front.trim()) return copy.setReview.validationFront
  const options = values.options.map((option) => option.trim())
  if (options.some((option) => !option)) return copy.setReview.validationOptions
  if (new Set(options.map((option) => option.toLowerCase())).size !== options.length) {
    return copy.setReview.validationUnique
  }
  return null
}

export default function SetView() {
  const { id } = useParams<{ id: string }>()
  return <SetViewContent key={id} />
}

function SetViewContent() {
  const { id } = useParams<{ id: string }>()
  const [set, setSet] = useState<FlashcardSet | null>(null)
  const [cards, setCards] = useState<Flashcard[]>([])
  const [loadedId, setLoadedId] = useState<string | null>(null)
  const loading = loadedId !== id
  const loadControllerRef = useRef<AbortController | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<EditValues>(EMPTY_EDIT)
  const [cardErrors, setCardErrors] = useState<Record<string, string>>({})
  const [busyCardIds, setBusyCardIds] = useState<ReadonlySet<string>>(new Set())
  const busyCardIdsRef = useRef(new Set<string>())
  const [approvingAll, setApprovingAll] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)

  const loadData = useCallback(() => {
    if (!id) return Promise.resolve()
    loadControllerRef.current?.abort()
    const controller = new AbortController()
    loadControllerRef.current = controller
    return Promise.all([
      subjectService.getSet(id, controller.signal),
      flashcardService.getCards(id, controller.signal),
    ]).then(([setData, cardsData]) => {
      if (controller.signal.aborted) return
      setLoadError(null)
      setSet(setData)
      setCards(cardsData)
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) setLoadError(apiErrorMessage(caught, copy.setReview.loadFailed))
    }).finally(() => {
      if (!controller.signal.aborted) setLoadedId(id)
    })
  }, [id])

  const reloadData = () => {
    setLoadedId(null)
    void loadData()
  }

  useEffect(() => {
    void loadData()
    return () => loadControllerRef.current?.abort()
  }, [loadData])

  const startCardAction = (cardId: string): boolean => {
    if (busyCardIdsRef.current.has(cardId)) return false
    busyCardIdsRef.current.add(cardId)
    setBusyCardIds(new Set(busyCardIdsRef.current))
    return true
  }

  const finishCardAction = (cardId: string) => {
    busyCardIdsRef.current.delete(cardId)
    setBusyCardIds(new Set(busyCardIdsRef.current))
  }

  const clearCardError = (cardId: string) => {
    setCardErrors((current) => {
      if (!(cardId in current)) return current
      const next = { ...current }
      delete next[cardId]
      return next
    })
  }

  const setCardError = (cardId: string, message: string) => {
    setCardErrors((current) => ({ ...current, [cardId]: message }))
  }

  const handleEdit = (card: Flashcard) => {
    const correctOptionIndex = card.options.findIndex((option) => option === card.back_content)
    setEditingId(card.id)
    clearCardError(card.id)
    setEditValues({
      front: card.front_content,
      options: [...card.options],
      correctOptionIndex: correctOptionIndex >= 0 ? correctOptionIndex : 0,
    })
  }

  const handleSave = async (cardId: string) => {
    const validationError = validateEdit(editValues)
    if (validationError) {
      setCardError(cardId, validationError)
      return
    }
    if (!startCardAction(cardId)) return

    const options = editValues.options.map((option) => option.trim()) as EditValues['options']
    clearCardError(cardId)
    try {
      const updated = await flashcardService.updateCard(cardId, {
        front_content: editValues.front.trim(),
        back_content: options[editValues.correctOptionIndex],
        options,
      })
      setCards((current) => current.map((card) => card.id === cardId ? updated : card))
      setEditingId((current) => current === cardId ? null : current)
    } catch (caught: unknown) {
      setCardError(cardId, apiErrorMessage(caught, copy.setReview.saveFailed))
    } finally {
      finishCardAction(cardId)
    }
  }

  const handleApprove = async (card: Flashcard) => {
    if (!startCardAction(card.id)) return
    setActionError(null)
    try {
      const updated = await flashcardService.updateCard(card.id, { is_approved: true })
      setCards((current) => current.map((item) => item.id === card.id ? updated : item))
    } catch (caught: unknown) {
      setActionError(apiErrorMessage(caught, copy.setReview.approveFailed))
    } finally {
      finishCardAction(card.id)
    }
  }

  const handleApproveAll = async () => {
    if (!id || busyCardIdsRef.current.size > 0 || !confirm(copy.setReview.confirmApproveAll)) return
    setApprovingAll(true)
    setActionError(null)
    try {
      await flashcardService.approveAll(id)
      setCards(await flashcardService.getCards(id))
    } catch (caught: unknown) {
      setActionError(apiErrorMessage(caught, copy.setReview.approveAllFailed))
    } finally {
      setApprovingAll(false)
    }
  }

  const handleDelete = async (card: Flashcard) => {
    if (!confirm(copy.setReview.confirmDelete)) return
    if (!startCardAction(card.id)) return
    setActionError(null)
    try {
      await flashcardService.deleteCard(card.id)
      setCards((current) => current.filter((item) => item.id !== card.id))
      if (editingId === card.id) setEditingId(null)
    } catch (caught: unknown) {
      setActionError(apiErrorMessage(caught, copy.setReview.deleteFailed))
    } finally {
      finishCardAction(card.id)
    }
  }

  if (loading) {
    return <div className="p-8" role="status" aria-label={copy.common.loading}><Loader2 className="animate-spin" aria-hidden="true" /></div>
  }

  if (loadError) return <PageError message={loadError} onRetry={reloadData} />

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <Button asChild variant="ghost" size="icon">
            <Link to={set ? `/subjects/${set.subject_id}` : '/dashboard'} aria-label={copy.common.backToDashboard}>
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </Link>
          </Button>
          <h1 className="min-w-0 break-words text-2xl font-bold">{set?.title || copy.setReview.defaultTitle}</h1>
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          <Button type="button" onClick={() => setPreviewOpen(true)} variant="outline" disabled={cards.length === 0}>
            <Play className="mr-2 h-4 w-4" aria-hidden="true" /> {copy.setReview.preview}
          </Button>
          <Button type="button" onClick={() => void handleApproveAll()} disabled={approvingAll || busyCardIds.size > 0 || cards.length === 0}>
            {approvingAll ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            {copy.setReview.approveAll}
          </Button>
        </div>
      </div>

      {actionError ? <p className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{actionError}</p> : null}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => {
          const isEditing = editingId === card.id
          const isBusy = busyCardIds.has(card.id)
          return (
            <Card key={card.id} className={`min-w-0 ${card.is_approved ? 'border-green-200 bg-green-50/30' : 'border-yellow-200 bg-yellow-50/30'}`}>
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <CardTitle className="min-w-0 text-sm font-medium text-muted-foreground">
                  {card.is_approved ? (
                    <span className="flex items-center gap-1 text-green-700"><Check className="h-3 w-3" aria-hidden="true" /> {copy.setReview.approved}</span>
                  ) : copy.setReview.needsReview}
                </CardTitle>
                <div className="flex flex-wrap justify-end gap-1">
                  {!card.is_approved ? (
                    <Button type="button" variant="ghost" size="sm" onClick={() => void handleApprove(card)} disabled={isBusy || approvingAll} aria-label={copy.setReview.approveCard(card.front_content)}>
                      {copy.setReview.approve}
                    </Button>
                  ) : null}
                  <Button type="button" variant="ghost" size="sm" onClick={() => handleEdit(card)} disabled={isBusy || approvingAll} aria-label={copy.setReview.editCard(card.front_content)}>
                    {copy.common.edit}
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="text-red-500 hover:bg-red-50 hover:text-red-700" onClick={() => void handleDelete(card)} disabled={isBusy || approvingAll} aria-label={copy.setReview.deleteCard(card.front_content)}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="mt-2 space-y-4">
                {isEditing ? (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor={`front-${card.id}`} className="text-xs font-bold uppercase text-muted-foreground">{copy.setReview.front}</Label>
                      <Textarea id={`front-${card.id}`} value={editValues.front} onChange={(event) => setEditValues((values) => ({ ...values, front: event.target.value }))} maxLength={10_000} />
                    </div>
                    <fieldset className="space-y-2">
                      <legend className="text-xs font-bold uppercase text-muted-foreground">{copy.setReview.optionsAndAnswer}</legend>
                      {editValues.options.map((option, optionIndex) => (
                        <div key={optionIndex} className="flex min-w-0 items-start gap-2">
                          <label className="flex min-h-11 min-w-11 shrink-0 cursor-pointer items-start justify-center pt-3">
                            <input
                              type="radio"
                              name={`correct-${card.id}`}
                              checked={editValues.correctOptionIndex === optionIndex}
                              onChange={() => setEditValues((values) => ({ ...values, correctOptionIndex: optionIndex }))}
                              className="h-5 w-5"
                              aria-label={copy.setReview.correctAnswer(optionIndex)}
                            />
                          </label>
                          <Label htmlFor={`option-${card.id}-${optionIndex}`} className="sr-only">{copy.setReview.optionLabel(optionIndex)}</Label>
                          <Textarea
                            id={`option-${card.id}-${optionIndex}`}
                            value={option}
                            onChange={(event) => setEditValues((values) => {
                              const options = [...values.options] as EditValues['options']
                              options[optionIndex] = event.target.value
                              return { ...values, options }
                            })}
                            maxLength={10_000}
                          />
                        </div>
                      ))}
                    </fieldset>
                    {cardErrors[card.id] ? <p className="text-sm text-destructive" role="alert">{cardErrors[card.id]}</p> : null}
                  </>
                ) : (
                  <>
                    <div>
                      <div className="mb-1 text-xs font-bold uppercase text-muted-foreground">{copy.setReview.front}</div>
                      <p className="break-words text-sm font-medium">{card.front_content}</p>
                    </div>
                    <div>
                      <div className="mb-1 text-xs font-bold uppercase text-muted-foreground">{copy.setReview.answer}</div>
                      <p className="break-words text-sm text-gray-700">{card.back_content}</p>
                    </div>
                  </>
                )}

                {card.source_snippet ? (
                  <figure className="mt-2 border-t pt-2 text-xs text-muted-foreground">
                    <figcaption className="break-words font-medium not-italic">
                      {copy.setReview.verifiedSource}
                      {card.source_page ? ` · ${copy.setReview.sourcePage(card.source_page)}` : ''}
                      {card.source_section ? ` · ${card.source_section}` : ''}
                    </figcaption>
                    <blockquote className="mt-1 break-words border-l-2 pl-2 italic">“{card.source_snippet}”</blockquote>
                  </figure>
                ) : <p className="mt-2 border-t pt-2 text-xs text-muted-foreground">{copy.setReview.manualCard}</p>}
              </CardContent>
              {isEditing ? (
                <CardFooter className="flex flex-wrap justify-end gap-2">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setEditingId(null)} disabled={isBusy}>{copy.common.cancel}</Button>
                  <Button type="button" size="sm" onClick={() => void handleSave(card.id)} disabled={isBusy || approvingAll}>
                    {isBusy ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Save className="mr-1 h-3 w-3" aria-hidden="true" />} {copy.setReview.save}
                  </Button>
                </CardFooter>
              ) : null}
            </Card>
          )
        })}
      </div>

      {cards.length === 0 ? <p className="py-12 text-center text-muted-foreground">{copy.setReview.noCards}</p> : null}
      {previewOpen ? <PreviewDialog open cards={cards} title={set?.title || copy.setReview.defaultTitle} onOpenChange={setPreviewOpen} /> : null}
    </div>
  )
}
