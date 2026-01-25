import { useState, useEffect } from "react"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { motion, AnimatePresence } from "framer-motion"
import { X, ArrowRight, ArrowLeft } from "lucide-react"

interface PreviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  cards: any[]
  title: string
}

export function PreviewDialog({ open, onOpenChange, cards, title }: PreviewDialogProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)

  // Reset state when opened
  useEffect(() => {
    if (open) {
      setCurrentIndex(0)
      setIsFlipped(false)
    }
  }, [open])

  if (!cards || cards.length === 0) return null

  const currentCard = cards[currentIndex]

  const handleNext = () => {
    if (currentIndex < cards.length - 1) {
      setIsFlipped(false)
      setTimeout(() => setCurrentIndex(currentIndex + 1), 200)
    } else {
        // End of set, maybe close or loop?
        // Let's just loop for preview
        setIsFlipped(false)
        setTimeout(() => setCurrentIndex(0), 200)
    }
  }

  const handlePrev = () => {
      if (currentIndex > 0) {
          setIsFlipped(false)
          setTimeout(() => setCurrentIndex(currentIndex - 1), 200)
      }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] flex flex-col p-0 overflow-hidden bg-slate-100">
        {/* Header */}
        <div className="p-4 bg-white flex items-center justify-between shadow-sm z-10">
           <h2 className="font-bold text-lg">{title} - Preview</h2>
           <div className="text-sm text-slate-500">
               Card {currentIndex + 1} / {cards.length}
           </div>
           <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)}>
               <X className="h-5 w-5" />
           </Button>
        </div>

        {/* Card Area */}
        <div className="flex-1 flex items-center justify-center p-6 perspective-1000">
        <div 
            className="relative w-full max-w-xl aspect-[3/2] cursor-pointer group"
            onClick={() => setIsFlipped(!isFlipped)}
        >
            <motion.div 
                className="w-full h-full"
                initial={false}
                animate={{ rotateY: isFlipped ? 180 : 0 }}
                transition={{ duration: 0.6, type: "spring", stiffness: 260, damping: 20 }}
                style={{ transformStyle: "preserve-3d" }}
            >
                {/* Front */}
                <Card className="absolute inset-0 backface-hidden flex flex-col items-center justify-center p-8 text-center shadow-xl border-2 border-slate-200">
                    <div className="text-xs uppercase font-bold text-slate-400 mb-4 tracking-widest">Question</div>
                    <div className="text-2xl md:text-3xl font-medium text-slate-800">
                        {currentCard.front_content}
                    </div>
                    <div className="absolute bottom-4 text-xs text-slate-400">Tap to flip</div>
                </Card>

                {/* Back */}
                <Card 
                    className="absolute inset-0 backface-hidden flex flex-col items-center justify-center p-8 text-center shadow-xl border-2 border-blue-200 bg-blue-50/50"
                    style={{ transform: "rotateY(180deg)" }}
                >
                    <div className="text-xs uppercase font-bold text-blue-400 mb-4 tracking-widest">Answer</div>
                    <div className="text-xl md:text-2xl text-slate-800 max-h-[60%] overflow-y-auto">
                        {currentCard.back_content}
                    </div>
                </Card>
            </motion.div>
        </div>
      </div>

       {/* Controls */}
       <div className="bg-white p-6 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] z-10 flex justify-center gap-4">
           <Button 
               variant="outline" 
               onClick={handlePrev} 
               disabled={currentIndex === 0}
               size="lg"
           >
               <ArrowLeft className="mr-2 h-4 w-4" /> Previous
           </Button>
           
           <Button 
               size="lg" 
               className="min-w-[150px]"
               onClick={() => setIsFlipped(!isFlipped)}
           >
               {isFlipped ? "Hide Answer" : "Show Answer"}
           </Button>

           <Button 
               variant="default" 
               onClick={handleNext} 
               size="lg"
           >
               {currentIndex === cards.length - 1 ? "Restart" : "Next"} <ArrowRight className="ml-2 h-4 w-4" />
           </Button>
       </div>
       
       <style>{`
        .perspective-1000 { perspective: 1000px; }
        .backface-hidden { backface-visibility: hidden; }
      `}</style>

      </DialogContent>
    </Dialog>
  )
}
