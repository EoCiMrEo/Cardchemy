import { useState } from 'react'
import { ArrowLeft, ArrowRight, X } from 'lucide-react'
import { motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent } from '@/components/ui/dialog'
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
      <DialogContent className="flex h-[80vh] max-w-4xl flex-col overflow-hidden bg-slate-100 p-0">
        <div className="z-10 flex items-center justify-between bg-white p-4 shadow-sm">
          <h2 className="text-lg font-bold">{copy.preview.title(title)}</h2>
          <div className="text-sm text-slate-500">{copy.preview.position(currentIndex + 1, cards.length)}</div>
          <Button type="button" variant="ghost" size="icon" onClick={() => onOpenChange(false)} aria-label={copy.preview.close}>
            <X className="h-5 w-5" aria-hidden="true" />
          </Button>
        </div>

        <div className="perspective-1000 flex flex-1 items-center justify-center p-6">
          <button
            type="button"
            className="group relative aspect-[3/2] w-full max-w-xl cursor-pointer text-left"
            onClick={flip}
            aria-label={copy.preview.flipHint}
          >
            <motion.div
              className="h-full w-full"
              initial={false}
              animate={{ rotateY: isFlipped ? 180 : 0 }}
              transition={{ duration: 0.6, type: 'spring', stiffness: 260, damping: 20 }}
              style={{ transformStyle: 'preserve-3d' }}
            >
              <Card className="backface-hidden absolute inset-0 flex flex-col items-center justify-center border-2 border-slate-200 p-8 text-center shadow-xl">
                <div className="mb-4 text-xs font-bold uppercase tracking-widest text-slate-400">{copy.preview.question}</div>
                <div className="text-2xl font-medium text-slate-800 md:text-3xl">{currentCard.front_content}</div>
                <div className="absolute bottom-4 text-xs text-slate-400">{copy.preview.flipHint}</div>
              </Card>
              <Card className="backface-hidden absolute inset-0 flex flex-col items-center justify-center border-2 border-blue-200 bg-blue-50/50 p-8 text-center shadow-xl" style={{ transform: 'rotateY(180deg)' }}>
                <div className="mb-4 text-xs font-bold uppercase tracking-widest text-blue-400">{copy.preview.answer}</div>
                <div className="max-h-[60%] overflow-y-auto text-xl text-slate-800 md:text-2xl">{currentCard.back_content}</div>
              </Card>
            </motion.div>
          </button>
        </div>

        <div className="z-10 flex justify-center gap-4 bg-white p-6 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
          <Button type="button" variant="outline" onClick={handlePrevious} disabled={currentIndex === 0} size="lg">
            <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" /> {copy.preview.previous}
          </Button>
          <Button type="button" size="lg" className="min-w-[150px]" onClick={flip}>
            {isFlipped ? copy.preview.hideAnswer : copy.preview.showAnswer}
          </Button>
          <Button type="button" onClick={handleNext} size="lg">
            {currentIndex === cards.length - 1 ? copy.preview.restart : copy.preview.next} <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        <style>{`.perspective-1000 { perspective: 1000px; } .backface-hidden { backface-visibility: hidden; }`}</style>
      </DialogContent>
    </Dialog>
  )
}
