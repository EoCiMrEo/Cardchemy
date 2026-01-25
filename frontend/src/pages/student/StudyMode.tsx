import { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { studyService } from "@/services/study"
import { Button } from "@/components/ui/button"
import { Loader2, X, Check, RotateCw, ArrowLeft } from "lucide-react"
import { Card } from "@/components/ui/card"

export default function StudyMode() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  
  const [session, setSession] = useState<any>(null)
  const [cards, setCards] = useState<any[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)
  const [loading, setLoading] = useState(true)
  const [sessionComplete, setSessionComplete] = useState(false)
  const [stats, setStats] = useState({ correct: 0, incorrect: 0 })

  useEffect(() => {
    if (id) loadSession()
  }, [id])

  const loadSession = async () => {
    try {
      setLoading(true)
      const data = await studyService.getStudySession(id!)
      setSession(data)
      setCards(data.cards)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleFlip = () => {
    setIsFlipped(!isFlipped)
  }

  const handleResponse = async (quality: number) => {
    const currentCard = cards[currentIndex]
    const isCorrect = quality >= 3
    
    // Optimistic update
    setStats(prev => ({
        correct: prev.correct + (isCorrect ? 1 : 0),
        incorrect: prev.incorrect + (isCorrect ? 0 : 1)
    }))

    try {
        await studyService.updateProgress({
            flashcard_id: currentCard.id,
            is_correct: isCorrect,
            quality: quality
        })
    } catch (e) {
        console.error("Failed to save progress", e)
        // Queue for offline sync if needed (PWA step)
    }

    if (currentIndex < cards.length - 1) {
        setIsFlipped(false)
        setTimeout(() => setCurrentIndex(currentIndex + 1), 200)
    } else {
        setSessionComplete(true)
    }
  }

  if (loading) return <div className="h-screen flex items-center justify-center"><Loader2 className="animate-spin h-8 w-8 text-primary" /></div>

  if (cards.length === 0 && !loading) {
      return (
          <div className="h-screen flex flex-col items-center justify-center p-4 text-center">
              <h1 className="text-2xl font-bold mb-2">All Caught Up! 🎉</h1>
              <p className="text-muted-foreground mb-6">You have no cards due for review in this set right now.</p>
              <Button onClick={() => navigate(-1)}>Go Back</Button>
          </div>
      )
  }

  if (sessionComplete) {
      return (
          <div className="h-screen flex flex-col items-center justify-center p-4 text-center bg-green-50">
              <h1 className="text-3xl font-bold mb-4 text-green-800">Session Complete! 🎓</h1>
              <div className="grid grid-cols-2 gap-8 mb-8">
                  <div className="text-center">
                      <div className="text-4xl font-bold text-green-600">{stats.correct}</div>
                      <div className="text-sm text-green-800 uppercase font-bold tracking-wide">Remembered</div>
                  </div>
                  <div className="text-center">
                      <div className="text-4xl font-bold text-orange-500">{stats.incorrect}</div>
                      <div className="text-sm text-orange-800 uppercase font-bold tracking-wide">Learning</div>
                  </div>
              </div>
              <Button size="lg" onClick={() => navigate(-1)}>Back to Dashboard</Button>
          </div>
      )
  }

  const currentCard = cards[currentIndex]

  return (
    <div className="h-screen flex flex-col bg-slate-100 overflow-hidden">
      {/* Header */}
      <div className="bg-white p-4 flex items-center justify-between shadow-sm z-10">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="text-sm font-medium text-slate-500">
            Card {currentIndex + 1} / {cards.length}
        </div>
        <div className="w-8"></div> {/* Spacer */}
      </div>

      {/* Card Area */}
      <div className="flex-1 flex items-center justify-center p-6 perspective-1000">
        <div 
            className="relative w-full max-w-xl aspect-[3/2] cursor-pointer group"
            onClick={handleFlip}
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
      <div className="bg-white p-6 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] z-10">
        {!isFlipped ? (
            <Button size="lg" className="w-full text-lg h-14" onClick={handleFlip}>
                Show Answer
            </Button>
        ) : (
            <div className="grid grid-cols-2 gap-4 max-w-xl mx-auto">
                <Button 
                    variant="destructive" 
                    size="lg" 
                    className="h-14 text-lg flex flex-col gap-1"
                    onClick={() => handleResponse(1)}
                >
                    <div className="flex items-center gap-2"><X className="h-5 w-5" /> Forgot</div>
                    <span className="text-xs font-normal opacity-80">Reset progress</span>
                </Button>
                
                <Button 
                    variant="default" 
                    size="lg" 
                    className="h-14 text-lg bg-green-600 hover:bg-green-700 flex flex-col gap-1"
                    onClick={() => handleResponse(4)}
                >
                    <div className="flex items-center gap-2"><Check className="h-5 w-5" /> Got it</div>
                    <span className="text-xs font-normal opacity-80">Next review later</span>
                </Button>
            </div>
        )}
      </div>
      
      {/* 3D Styles */}
      <style>{`
        .perspective-1000 { perspective: 1000px; }
        .backface-hidden { backface-visibility: hidden; }
      `}</style>
    </div>
  )
}
