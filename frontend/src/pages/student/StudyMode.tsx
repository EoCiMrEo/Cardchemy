import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Clock, Loader2 } from 'lucide-react'
import { motion } from 'framer-motion'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate, useParams } from 'react-router-dom'

import { PageError } from '@/components/feedback/PageError'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { studyService } from '@/services/study'
import type { StudyAnswerResponse, StudyCard } from '@/services/types'
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

function StudyCardView({ card, current, total, timeLimit, onAnswered, onNext, onLeave }: StudyCardViewProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [attempted, setAttempted] = useState(false)
  const [timedOut, setTimedOut] = useState(false)
  const [answerResult, setAnswerResult] = useState<StudyAnswerResponse | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [timeLeft, setTimeLeft] = useState<number | null>(timeLimit)

  const submitAnswer = useCallback(async (option: string | null, timeout = false) => {
    if (submitting || answerResult) return
    setAttempted(true)
    setSelectedOption(option)
    setTimedOut(timeout)
    setSubmitting(true)
    setSaveError(null)
    try {
      const result = await studyService.updateProgress({ flashcard_id: card.id, selected_option: option })
      setAnswerResult(result)
      onAnswered(card.id, result.is_correct)
    } catch (caught: unknown) {
      setSaveError(apiErrorMessage(caught, copy.study.saveFailed))
    } finally {
      setSubmitting(false)
    }
  }, [answerResult, card.id, onAnswered, submitting])

  useEffect(() => {
    if (!timeLimit || attempted || answerResult || saveError) return
    const deadline = Date.now() + timeLimit * 1_000
    const interval = window.setInterval(() => {
      setTimeLeft(Math.max(0, Math.ceil((deadline - Date.now()) / 1_000)))
    }, 250)
    const timeout = window.setTimeout(() => void submitAnswer(null, true), timeLimit * 1_000)
    return () => {
      window.clearInterval(interval)
      window.clearTimeout(timeout)
    }
  }, [answerResult, attempted, saveError, submitAnswer, timeLimit])

  const progressValue = timeLimit && timeLeft !== null ? (timeLeft / timeLimit) * 100 : 100

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-100">
      <div className="z-10 flex items-center justify-between bg-white p-4 shadow-sm">
        <Button type="button" variant="ghost" size="icon" onClick={onLeave} aria-label={copy.study.leaveStudy}>
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        </Button>
        {timeLimit ? (
          <div className="mx-4 flex max-w-md flex-1 items-center gap-3">
            <Clock className={`h-4 w-4 ${timeLeft !== null && timeLeft < 5 ? 'animate-pulse text-red-500' : 'text-slate-400'}`} aria-hidden="true" />
            <Progress value={progressValue} className="h-2" />
            <span className="w-8 font-mono text-xs">{copy.study.secondsRemaining(timeLeft ?? 0)}</span>
          </div>
        ) : null}
        <div className="text-sm font-medium text-slate-500">{copy.study.position(current, total)}</div>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto p-4">
        <div className="perspective-1000 relative mb-6 aspect-[3/2] w-full max-w-xl">
          <motion.div className="relative h-full w-full" initial={false} animate={{ rotateY: answerResult ? 180 : 0 }} transition={{ duration: 0.6 }} style={{ transformStyle: 'preserve-3d' }}>
            <Card className="backface-hidden absolute inset-0 flex flex-col items-center justify-center border-2 border-slate-200 p-8 text-center shadow-lg">
              <span className="mb-4 text-xs font-bold uppercase tracking-widest text-slate-400">{copy.study.question}</span>
              <h2 className="text-2xl font-medium text-slate-800">{card.front_content}</h2>
            </Card>
            <Card className="backface-hidden absolute inset-0 flex flex-col items-center justify-center border-2 border-blue-200 bg-blue-50 p-8 text-center shadow-lg" style={{ transform: 'rotateY(180deg)' }}>
              <span className="mb-4 text-xs font-bold uppercase tracking-widest text-blue-400">{copy.study.answer}</span>
              <h2 className="text-xl font-medium text-slate-800">{answerResult?.correct_option}</h2>
            </Card>
          </motion.div>
        </div>

        <div className="w-full max-w-2xl">
          {answerResult ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {card.options.map((option, index) => {
                  const isCorrect = option === answerResult.correct_option
                  const wasSelected = option === selectedOption
                  const color = isCorrect
                    ? 'bg-green-100 border-green-400 ring-2 ring-green-400'
                    : wasSelected
                      ? 'bg-red-100 border-red-400'
                      : 'bg-slate-100 border-slate-200'
                  return (
                    <div key={option} className={`flex items-start gap-3 rounded-xl border-2 p-4 ${color}`}>
                      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${isCorrect ? 'bg-green-500 text-white' : wasSelected ? 'bg-red-500 text-white' : 'bg-slate-200 text-slate-600'}`}>{String.fromCharCode(65 + index)}</span>
                      <span className={`text-sm ${isCorrect ? 'font-semibold text-green-800' : 'text-slate-700'}`}>{option}</span>
                    </div>
                  )
                })}
              </div>
              <div className={`rounded-xl p-3 text-center text-lg font-semibold text-white ${timedOut ? 'bg-orange-500' : answerResult.is_correct ? 'bg-green-500' : 'bg-red-500'}`} role="status">
                {timedOut ? copy.study.timeout : answerResult.is_correct ? copy.study.correct : copy.study.incorrect}
              </div>
              <Button type="button" size="lg" className="h-14 w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-lg shadow-lg hover:from-blue-700 hover:to-indigo-700" onClick={onNext}>
                {copy.study.nextQuestion} <ArrowRight className="ml-2 h-5 w-5" aria-hidden="true" />
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {card.options.map((option, index) => {
                  const colors = [
                    'border-rose-300 hover:border-rose-500 hover:bg-rose-50 focus:ring-rose-400',
                    'border-amber-300 hover:border-amber-500 hover:bg-amber-50 focus:ring-amber-400',
                    'border-emerald-300 hover:border-emerald-500 hover:bg-emerald-50 focus:ring-emerald-400',
                    'border-sky-300 hover:border-sky-500 hover:bg-sky-50 focus:ring-sky-400',
                  ]
                  const badges = ['bg-rose-500', 'bg-amber-500', 'bg-emerald-500', 'bg-sky-500']
                  return (
                    <button key={option} type="button" className={`flex w-full items-start gap-3 rounded-xl border-2 bg-white p-4 text-left transition-all duration-200 ease-out hover:scale-[1.02] hover:shadow-md focus:outline-none focus:ring-2 ${colors[index]}`} onClick={() => void submitAnswer(option)} disabled={attempted || submitting}>
                      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${badges[index]}`}>{String.fromCharCode(65 + index)}</span>
                      <span className="text-sm leading-relaxed text-slate-700">{option}</span>
                    </button>
                  )
                })}
              </div>
              {submitting ? <p className="text-center text-sm text-muted-foreground" role="status">{copy.common.saving}</p> : null}
              {saveError ? (
                <div className="rounded border border-red-200 bg-red-50 p-3 text-center" role="alert">
                  <p className="text-sm text-red-800">{saveError}</p>
                  <Button type="button" variant="outline" className="mt-3" onClick={() => void submitAnswer(selectedOption, timedOut)} disabled={submitting}>{copy.study.retrySave}</Button>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
      <style>{`.perspective-1000 { perspective: 1000px; } .backface-hidden { backface-visibility: hidden; }`}</style>
    </div>
  )
}

export default function StudyMode() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const dispatch = useDispatch<AppDispatch>()
  const { cards, currentIndex, sessionComplete, timeLimit, results } = useSelector((state: RootState) => state.study)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setLoadError(null)
    try {
      const data = await studyService.getStudySession(id)
      dispatch(startSession({ sessionId: id, cards: data.cards, timeLimit: data.time_limit }))
    } catch (caught: unknown) {
      setLoadError(apiErrorMessage(caught, copy.study.loadFailed))
    } finally {
      setLoading(false)
    }
  }, [dispatch, id])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const recordAnswer = useCallback((cardId: string, isCorrect: boolean) => {
    dispatch(answerCard({ cardId, isCorrect }))
  }, [dispatch])

  if (loading) return <div className="flex h-screen items-center justify-center" role="status" aria-label={copy.study.loading}><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
  if (loadError) return <div className="flex h-screen items-center justify-center p-4"><PageError message={loadError} onRetry={() => void loadData()} /></div>

  if (cards.length === 0) {
    return (
      <div className="flex h-screen flex-col items-center justify-center p-4 text-center">
        <h1 className="mb-2 text-2xl font-bold">{copy.study.allCaughtUp}</h1>
        <Button type="button" onClick={() => navigate(-1)}>{copy.study.goBack}</Button>
      </div>
    )
  }

  if (sessionComplete) {
    const values = Object.values(results)
    const correct = values.filter(Boolean).length
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-green-50 p-4 text-center">
        <h1 className="mb-4 text-3xl font-bold text-green-800">{copy.study.sessionComplete}</h1>
        <div className="mb-8 flex gap-8">
          <div><div className="text-4xl font-bold text-green-600">{correct}</div><div className="text-sm font-bold text-green-800">{copy.study.correctLabel}</div></div>
          <div><div className="text-4xl font-bold text-orange-500">{values.length - correct}</div><div className="text-sm font-bold text-orange-800">{copy.study.wrongLabel}</div></div>
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
