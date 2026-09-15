import { useState } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { copy } from '@/i18n/en'
import type { Flashcard } from '@/services/types'

interface PreviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  cards: Flashcard[]
  title: string
}

export function PreviewDialog({ open, onOpenChange, cards, title }: PreviewDialogProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)
  const reduceMotion = useReducedMotion()

  if (cards.length === 0) return null

  const currentCard = cards[currentIndex]
  const flip = () => setIsFlipped((flipped) => !flipped)
  const handleNext = () => {
    setIsFlipped(false)
    setCurrentIndex((index) => index < cards.length - 1 ? index + 1 : 0)
  }
  const handlePrevious = () => {
    setIsFlipped(false)
    setCurrentIndex((index) => Math.max(0, index - 1))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[calc(100dvh-2rem)] max-h-[48rem] max-w-4xl flex-col overflow-hidden bg-slate-100 p-0">
        <div className="z-10 flex min-w-0 flex-wrap items-start justify-between gap-2 bg-white p-4 pr-14 shadow-sm">
          <DialogTitle className="min-w-0 break-words text-lg font-bold">{copy.preview.title(title)}</DialogTitle>
          <DialogDescription className="sr-only">{copy.preview.flipHint}</DialogDescription>
          <div className="shrink-0 text-sm text-slate-600">{copy.preview.position(currentIndex + 1, cards.length)}</div>
        </div>

        <div className="perspective-1000 flex min-h-0 flex-1 items-center justify-center p-3 sm:p-6">
          <button
            type="button"
            className="group relative aspect-[3/2] max-h-full w-full max-w-xl cursor-pointer rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            onClick={flip}
            aria-label={isFlipped ? copy.preview.hideAnswer : copy.preview.showAnswer}
            aria-describedby="preview-card-content"
            aria-pressed={isFlipped}
          >
            <motion.div
              className="h-full w-full"
              initial={false}
              animate={{ rotateY: isFlipped ? 180 : 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.6, type: 'spring', stiffness: 260, damping: 20 }}
              style={{ transformStyle: 'preserve-3d' }}
            >
              <Card aria-hidden={isFlipped} className="backface-hidden absolute inset-0 flex min-w-0 flex-col items-center justify-center overflow-y-auto border-2 border-slate-200 p-4 text-center shadow-xl sm:p-8">
                <div className="mb-4 text-xs font-bold uppercase tracking-widest text-slate-600">{copy.preview.question}</div>
                <div className="max-w-full break-words text-2xl font-medium text-slate-800 md:text-3xl">{currentCard.front_content}</div>
                <div className="mt-4 text-xs text-slate-600">{copy.preview.flipHint}</div>
              </Card>
              <Card aria-hidden={!isFlipped} className="backface-hidden absolute inset-0 flex min-w-0 flex-col items-center justify-center overflow-y-auto border-2 border-blue-200 bg-blue-50/50 p-4 text-center shadow-xl sm:p-8" style={{ transform: 'rotateY(180deg)' }}>
                <div className="mb-4 text-xs font-bold uppercase tracking-widest text-blue-700">{copy.preview.answer}</div>
                <div className="max-w-full break-words text-xl text-slate-800 md:text-2xl">{currentCard.back_content}</div>
              </Card>
            </motion.div>
          </button>
          <p id="preview-card-content" className="sr-only" aria-live="polite">
            {isFlipped ? `${copy.preview.answer}: ${currentCard.back_content}` : `${copy.preview.question}: ${currentCard.front_content}`}
          </p>
        </div>

        <div className="z-10 grid grid-cols-1 gap-2 bg-white p-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] sm:grid-cols-3 sm:p-6">
          <Button type="button" variant="outline" onClick={handlePrevious} disabled={currentIndex === 0} size="lg">
            <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" /> {copy.preview.previous}
          </Button>
          <Button type="button" size="lg" onClick={flip}>
            {isFlipped ? copy.preview.hideAnswer : copy.preview.showAnswer}
          </Button>
          <Button type="button" onClick={handleNext} size="lg">
            {currentIndex === cards.length - 1 ? copy.preview.restart : copy.preview.next} <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

      </DialogContent>
    </Dialog>
  )
}
