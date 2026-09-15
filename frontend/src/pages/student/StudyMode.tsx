import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Clock, Loader2 } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { PageError } from '@/components/feedback/PageError'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { studyService } from '@/services/study'
import type { StudyAnswerResponse, StudyCard, StudySessionMode } from '@/services/types'
import type { AppDispatch, RootState } from '@/store'
import { answerCard, nextCard, startSession } from '@/store/slices/studySlice'

interface StudyCardViewProps {
  card: StudyCard
  current: number
  total: number
  timeLimit: number | null
  onAnswered: (cardId: string, isCorrect: boolean) => void
  onNext: () => void
  onLeave: () => void
}

interface LogicalSubmission {
  idempotencyKey: string
  option: string | null
  timedOut: boolean
}

function StudyCardView({ card, current, total, timeLimit, onAnswered, onNext, onLeave }: StudyCardViewProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [attempted, setAttempted] = useState(false)
  const [timedOut, setTimedOut] = useState(false)
  const [answerResult, setAnswerResult] = useState<StudyAnswerResponse | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [timeLeft, setTimeLeft] = useState<number | null>(timeLimit)
  const submissionRef = useRef<LogicalSubmission | null>(null)
  const submissionInFlightRef = useRef(false)
  const answerResolvedRef = useRef(false)
  const activeControllerRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)
  const questionHeadingRef = useRef<HTMLHeadingElement>(null)
  const nextButtonRef = useRef<HTMLButtonElement>(null)
  const retryButtonRef = useRef<HTMLButtonElement>(null)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    mountedRef.current = true
    questionHeadingRef.current?.focus()
    return () => {
      mountedRef.current = false
      activeControllerRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    if (answerResult) nextButtonRef.current?.focus()
    else if (saveError) retryButtonRef.current?.focus()
  }, [answerResult, saveError])

  const submitAnswer = useCallback(async (option: string | null, timeout = false) => {
    if (submissionInFlightRef.current || answerResolvedRef.current) return

    const submission = submissionRef.current ?? {
      idempotencyKey: crypto.randomUUID(),
      option,
      timedOut: timeout,
    }
    submissionRef.current = submission
    submissionInFlightRef.current = true
    const controller = new AbortController()
    activeControllerRef.current = controller

    setAttempted(true)
    setSelectedOption(submission.option)
    setTimedOut(submission.timedOut)
    setSubmitting(true)
    setSaveError(null)

    try {
      const result = await studyService.updateProgress(
        { flashcard_id: card.id, selected_option: submission.option },
        submission.idempotencyKey,
        controller.signal,
      )
      if (!mountedRef.current || controller.signal.aborted) return
      answerResolvedRef.current = true
      setAnswerResult(result)
      onAnswered(card.id, result.is_correct)
    } catch (caught: unknown) {
      if (mountedRef.current && !controller.signal.aborted) {
        setSaveError(apiErrorMessage(caught, copy.study.saveFailed))
      }
    } finally {
      if (activeControllerRef.current === controller) activeControllerRef.current = null
      submissionInFlightRef.current = false
      if (mountedRef.current) setSubmitting(false)
    }
  }, [card.id, onAnswered])

  useEffect(() => {
    if (timeLimit === null || attempted || answerResult || saveError) return

    setTimeLeft(timeLimit)
    const deadline = Date.now() + timeLimit * 1_000
    const updateCountdown = () => {
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1_000))
      setTimeLeft(remaining)
    }
    const intervalId: number = window.setInterval(updateCountdown, 250)
    const timeoutId: number = window.setTimeout(() => {
      setTimeLeft(0)
      void submitAnswer(null, true)
    }, timeLimit * 1_000)

    return () => {
      window.clearInterval(intervalId)
      window.clearTimeout(timeoutId)
    }
  }, [answerResult, attempted, saveError, submitAnswer, timeLimit])

  const progressValue = timeLimit && timeLeft !== null ? (timeLeft / timeLimit) * 100 : 100
  const options = Array.isArray(card.options) ? card.options : []
  const hasAnswerOptions = card.card_type === 'multiple_choice' && options.length > 0
  const flipTransition = reduceMotion ? { duration: 0 } : { duration: 0.35 }

  return (
    <div className="flex min-h-dvh flex-col bg-slate-100">
      <header className="sticky top-0 z-10 flex min-h-16 flex-wrap items-center gap-3 bg-white px-3 py-3 shadow-sm sm:px-4">
        <Button type="button" variant="ghost" size="icon" onClick={onLeave} aria-label={copy.study.leaveStudy}>
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        </Button>
        {timeLimit ? (
          <div className="order-3 flex min-w-full flex-1 items-center gap-3 sm:order-none sm:min-w-0">
            <Clock className={`h-4 w-4 shrink-0 ${timeLeft !== null && timeLeft < 5 ? 'text-red-700 motion-safe:animate-pulse' : 'text-slate-600'}`} aria-hidden="true" />
            <Progress
              value={progressValue}
              className="h-2"
              aria-label={copy.study.timerLabel}
              aria-valuetext={copy.study.timerValue(timeLeft ?? 0)}
            />
            <span className="w-10 shrink-0 font-mono text-sm" aria-live="polite">
              {copy.study.secondsRemaining(timeLeft ?? 0)}
            </span>
          </div>
        ) : <div className="flex-1" />}
        <div className="ml-auto text-sm font-medium text-slate-600" aria-label={copy.study.position(current, total)}>
          {copy.study.position(current, total)}
        </div>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-3 py-4 sm:p-6">
        <div className="perspective-1000 relative mb-5 h-60 w-full max-w-xl sm:h-auto sm:aspect-[3/2]">
          <motion.div
            className="relative h-full w-full"
            initial={false}
            animate={{ rotateY: answerResult ? 180 : 0 }}
            transition={flipTransition}
            style={{ transformStyle: 'preserve-3d' }}
          >
            <Card
              className="backface-hidden absolute inset-0 flex flex-col items-center justify-center overflow-y-auto border-2 border-slate-200 p-5 text-center shadow-lg sm:p-8"
              aria-hidden={Boolean(answerResult)}
            >
              <span className="mb-4 text-xs font-bold uppercase tracking-widest text-slate-600">{copy.study.question}</span>
              <h1 ref={questionHeadingRef} tabIndex={-1} className="text-xl font-medium text-slate-900 focus:outline-none sm:text-2xl">
                {card.front_content}
              </h1>
            </Card>
            <Card
              className="backface-hidden absolute inset-0 flex flex-col items-center justify-center overflow-y-auto border-2 border-blue-300 bg-blue-50 p-5 text-center shadow-lg sm:p-8"
              style={{ transform: 'rotateY(180deg)' }}
              aria-hidden={!answerResult}
            >
              <span className="mb-4 text-xs font-bold uppercase tracking-widest text-blue-800">{copy.study.answer}</span>
              <h2 className="text-lg font-medium text-slate-900 sm:text-xl">{answerResult?.correct_option}</h2>
            </Card>
          </motion.div>
        </div>

        <div className="w-full max-w-2xl">
          {answerResult ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {options.map((option, index) => {
                  const isCorrect = option === answerResult.correct_option
                  const wasSelected = option === selectedOption
                  const color = isCorrect
                    ? 'border-green-700 bg-green-50'
                    : wasSelected
                      ? 'border-red-700 bg-red-50'
                      : 'border-slate-300 bg-slate-50'
                  return (
                    <div key={`${card.id}-${index}`} className={`flex min-h-12 items-start gap-3 rounded-xl border-2 p-4 ${color}`}>
                      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${isCorrect ? 'bg-green-800' : wasSelected ? 'bg-red-800' : 'bg-slate-700'}`}>
                        {String.fromCharCode(65 + index)}
                      </span>
                      <span className="min-w-0 text-sm leading-relaxed text-slate-800">
                        <span className="block break-words">{option}</span>
                        {isCorrect ? <span className="mt-1 block font-semibold text-green-800">{copy.study.correctAnswer}</span> : null}
                        {wasSelected && !isCorrect ? <span className="mt-1 block font-semibold text-red-800">{copy.study.yourAnswer}</span> : null}
                      </span>
                    </div>
                  )
                })}
              </div>
              <div className={`rounded-xl p-3 text-center text-lg font-semibold text-white ${timedOut ? 'bg-orange-800' : answerResult.is_correct ? 'bg-green-800' : 'bg-red-800'}`} role="status" aria-live="polite">
                {timedOut ? copy.study.timeout : answerResult.is_correct ? copy.study.correct : copy.study.incorrect}
              </div>
              <Button ref={nextButtonRef} type="button" size="lg" className="min-h-12 w-full bg-gradient-to-r from-blue-700 to-indigo-800 text-lg shadow-lg hover:from-blue-800 hover:to-indigo-900" onClick={onNext}>
                {copy.study.nextQuestion} <ArrowRight className="ml-2 h-5 w-5" aria-hidden="true" />
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {hasAnswerOptions ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {options.map((option, index) => {
                    const colors = [
                      'border-rose-400 hover:border-rose-700 hover:bg-rose-50 focus-visible:ring-rose-700',
                      'border-amber-500 hover:border-amber-800 hover:bg-amber-50 focus-visible:ring-amber-800',
                      'border-emerald-500 hover:border-emerald-800 hover:bg-emerald-50 focus-visible:ring-emerald-800',
                      'border-sky-500 hover:border-sky-800 hover:bg-sky-50 focus-visible:ring-sky-800',
                    ]
                    const badges = ['bg-rose-700', 'bg-amber-800', 'bg-emerald-800', 'bg-sky-800']
                    return (
                      <button
                        key={`${card.id}-${index}`}
                        type="button"
                        className={`flex min-h-12 w-full items-start gap-3 rounded-xl border-2 bg-white p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 motion-reduce:transition-none ${colors[index % colors.length]}`}
                        onClick={() => void submitAnswer(option)}
                        disabled={attempted || submitting}
                      >
                        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${badges[index % badges.length]}`}>
                          {String.fromCharCode(65 + index)}
                        </span>
                        <span className="min-w-0 break-words text-sm leading-relaxed text-slate-800">{option}</span>
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-center">
                  <p className="mb-3 text-sm text-amber-950" role="alert">{copy.study.noOptions}</p>
                  <Button type="button" variant="outline" onClick={() => void submitAnswer(null)} disabled={attempted || submitting}>
                    {copy.study.submitUnanswered}
                  </Button>
                </div>
              )}
              {submitting ? <p className="text-center text-sm text-muted-foreground" role="status">{copy.common.saving}</p> : null}
              {saveError ? (
                <div className="rounded border border-red-300 bg-red-50 p-3 text-center" role="alert">
                  <p className="text-sm text-red-900">{saveError}</p>
                  <Button ref={retryButtonRef} type="button" variant="outline" className="mt-3" onClick={() => void submitAnswer(selectedOption, timedOut)} disabled={submitting}>
                    {copy.study.retrySave}
                  </Button>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default function StudyMode() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const dispatch = useDispatch<AppDispatch>()
  const { cards, currentIndex, sessionComplete, timeLimit, results } = useSelector((state: RootState) => state.study)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const completionHeadingRef = useRef<HTMLHeadingElement>(null)
  const emptyHeadingRef = useRef<HTMLHeadingElement>(null)
  const mode: StudySessionMode = searchParams.get('mode') === 'review_all' ? 'review_all' : 'due'

  const loadData = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setLoadError(null)
    try {
      const data = await studyService.getStudySession(id, 20, mode)
      dispatch(startSession({ sessionId: id, cards: data.cards, timeLimit: data.time_limit }))
    } catch (caught: unknown) {
      setLoadError(apiErrorMessage(caught, copy.study.loadFailed))
    } finally {
      setLoading(false)
    }
  }, [dispatch, id, mode])

  useEffect(() => {
    void loadData()
  }, [loadData])

  useEffect(() => {
    if (sessionComplete) completionHeadingRef.current?.focus()
    else if (!loading && cards.length === 0) emptyHeadingRef.current?.focus()
  }, [cards.length, loading, sessionComplete])

  const recordAnswer = useCallback((cardId: string, isCorrect: boolean) => {
    dispatch(answerCard({ cardId, isCorrect }))
  }, [dispatch])

  if (loading) return <div className="flex min-h-dvh items-center justify-center" role="status" aria-label={copy.study.loading}><Loader2 className="h-8 w-8 text-primary motion-safe:animate-spin" /></div>
  if (loadError) return <div className="flex min-h-dvh items-center justify-center p-4"><PageError message={loadError} onRetry={() => void loadData()} /></div>

  if (cards.length === 0) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center p-4 text-center">
        <h1 ref={emptyHeadingRef} tabIndex={-1} className="mb-2 text-2xl font-bold focus:outline-none">{copy.study.allCaughtUp}</h1>
        <Button type="button" onClick={() => navigate(-1)}>{copy.study.goBack}</Button>
      </div>
    )
  }

  if (sessionComplete) {
    const values = Object.values(results)
    const correct = values.filter(Boolean).length
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center bg-green-50 p-4 text-center">
        <h1 ref={completionHeadingRef} tabIndex={-1} className="mb-4 text-3xl font-bold text-green-900 focus:outline-none">{copy.study.sessionComplete}</h1>
        <div className="mb-8 flex flex-wrap justify-center gap-8">
          <div><div className="text-4xl font-bold text-green-800">{correct}</div><div className="text-sm font-bold text-green-900">{copy.study.correctLabel}</div></div>
          <div><div className="text-4xl font-bold text-orange-800">{values.length - correct}</div><div className="text-sm font-bold text-orange-900">{copy.study.wrongLabel}</div></div>
        </div>
        <Button type="button" size="lg" onClick={() => navigate(-1)}>{copy.study.backToDashboard}</Button>
      </div>
    )
  }

  const currentCard = cards[currentIndex]
  return (
    <StudyCardView
      key={currentCard.id}
      card={currentCard}
      current={currentIndex + 1}
      total={cards.length}
      timeLimit={timeLimit}
      onAnswered={recordAnswer}
      onNext={() => dispatch(nextCard())}
      onLeave={() => navigate(-1)}
    />
  )
}
