import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { studyService } from "@/services/study";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowRight, ArrowLeft, Clock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useSelector, useDispatch } from "react-redux";
import type { RootState } from "@/store";
import { startSession, answerCard, nextCard } from "@/store/slices/studySlice";
import type { StudyAnswerResponse } from "@/services/types";

export default function StudyMode() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const dispatch = useDispatch();

  // Redux State
  const { cards, currentIndex, sessionComplete, timeLimit, results } = useSelector((state: RootState) => state.study);

  // Local UI State
  const [loading, setLoading] = useState(true);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isFlipped, setIsFlipped] = useState(false);
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [answerResult, setAnswerResult] = useState<StudyAnswerResponse | null>(null);
  
  // Stats for current session (could be moved to Redux fully, but this is fine for display)
  const currentStats = {
      correct: Object.values(results).filter(r => r).length,
      incorrect: Object.values(results).filter(r => !r).length
  }

  // Timer Ref
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (id) loadData();
    return () => stopTimer();
  }, [id]);

  useEffect(() => {
     // Reset state when card changes
     setSelectedOption(null);
     setIsFlipped(false);
     setTimedOut(false);
     setAnswerResult(null);
     if (timeLimit) {
         setTimeLeft(timeLimit);
         startTimer();
     }
  }, [currentIndex, timeLimit]);

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await studyService.getStudySession(id!);
      // Initialize Redux
      dispatch(startSession({ 
          sessionId: id!, 
          cards: data.cards,
          timeLimit: data.time_limit ?? null
      }));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const startTimer = () => {
      stopTimer();
      timerRef.current = setInterval(() => {
          setTimeLeft((prev) => {
              if (prev !== null && prev > 0) return prev - 1;
              stopTimer();
              handleTimeout(); // Auto-fail
              return 0;
          });
      }, 1000);
  };

  const stopTimer = () => {
      if (timerRef.current) clearInterval(timerRef.current);
  };

  const handleTimeout = () => {
      if (selectedOption || isFlipped) return; // Already answered
      setTimedOut(true);
      handleOptionSelect(null); // Treat as generic failure
  };

  const handleOptionSelect = async (option: string | null) => {
    stopTimer();
    setSelectedOption(option);
    
    const currentCard = cards[currentIndex];
    try {
        const result = await studyService.updateProgress({
            flashcard_id: currentCard.id,
            selected_option: option,
        });
        setAnswerResult(result);
        dispatch(answerCard({ cardId: currentCard.id, isCorrect: result.is_correct }));
        setIsFlipped(true);
    } catch (e) {
        console.error("Failed to sync progress", e);
    }
  };

  const handleNext = () => {
      dispatch(nextCard());
  };

  if (loading) return <div className="h-screen flex items-center justify-center"><Loader2 className="animate-spin h-8 w-8 text-primary" /></div>;

  if (cards.length === 0 && !loading) {
      return (
          <div className="h-screen flex flex-col items-center justify-center p-4 text-center">
              <h1 className="text-2xl font-bold mb-2">All Caught Up! 🎉</h1>
              <Button onClick={() => navigate(-1)}>Go Back</Button>
          </div>
      )
  }

  if (sessionComplete) {
      return (
          <div className="h-screen flex flex-col items-center justify-center p-4 text-center bg-green-50">
               <h1 className="text-3xl font-bold mb-4 text-green-800">Session Complete! 🎓</h1>
               <div className="flex gap-8 mb-8">
                   <div className="text-center">
                       <div className="text-4xl font-bold text-green-600">{currentStats.correct}</div>
                       <div className="text-sm text-green-800 font-bold">CORRECT</div>
                   </div>
                   <div className="text-center">
                       <div className="text-4xl font-bold text-orange-500">{currentStats.incorrect}</div>
                       <div className="text-sm text-orange-800 font-bold">WRONG</div>
                   </div>
               </div>
               <Button size="lg" onClick={() => navigate(-1)}>Back to Dashboard</Button>
          </div>
      )
  }

  const currentCard = cards[currentIndex];
  // Calculate progress for timer
  const progressValue = timeLimit && timeLeft !== null ? (timeLeft / timeLimit) * 100 : 100;

  return (
    <div className="h-screen flex flex-col bg-slate-100 overflow-hidden">
      {/* Header */}
      <div className="bg-white p-4 flex items-center justify-between shadow-sm z-10">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-5 w-5" />
        </Button>
        
        {timeLimit && (
            <div className="flex-1 max-w-md mx-4 flex items-center gap-3">
                <Clock className={`h-4 w-4 ${timeLeft && timeLeft < 5 ? 'text-red-500 animate-pulse' : 'text-slate-400'}`} />
                <Progress value={progressValue} className="h-2" />
                <span className="text-xs font-mono w-8">{timeLeft}s</span>
            </div>
        )}

        <div className="text-sm font-medium text-slate-500">
            {currentIndex + 1} / {cards.length}
        </div>
      </div>

      {/* Main Area */}
      <div className="flex-1 flex flex-col items-center justify-center p-4 overflow-y-auto">
          {/* Question Card */}
          <div className="w-full max-w-xl mb-6 perspective-1000 relative aspect-[3/2]">
               <motion.div 
                    className="w-full h-full relative"
                    initial={false}
                    animate={{ rotateY: isFlipped ? 180 : 0 }}
                    transition={{ duration: 0.6 }}
                    style={{ transformStyle: "preserve-3d" }}
               >
                   {/* Front */}
                   <Card className="absolute inset-0 backface-hidden flex flex-col items-center justify-center p-8 text-center shadow-lg border-2 border-slate-200">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Question</span>
                        <h2 className="text-2xl font-medium text-slate-800">{currentCard.front_content}</h2>
                   </Card>

                   {/* Back - Answer */}
                   <Card 
                        className="absolute inset-0 backface-hidden flex flex-col items-center justify-center p-8 text-center shadow-lg border-2 border-blue-200 bg-blue-50"
                        style={{ transform: "rotateY(180deg)" }}
                   >
                        <span className="text-xs font-bold text-blue-400 uppercase tracking-widest mb-4">Answer</span>
                         <h2 className="text-xl font-medium text-slate-800">{answerResult?.correct_option}</h2>
                   </Card>
               </motion.div>
          </div>

          {/* Interaction Area */}
          <div className="w-full max-w-2xl">
              {/* If answered, show Next button and feedback */}
              {isFlipped ? (
                  <div className="space-y-4">
                      {/* Show all options with correct/incorrect highlighting */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {currentCard.options?.map((option: string, idx: number) => {
                              const isCorrect = option === answerResult?.correct_option;
                              const wasSelected = option === selectedOption;
                              
                              let bgColor = "bg-slate-100 border-slate-200";
                              if (isCorrect) {
                                  bgColor = "bg-green-100 border-green-400 ring-2 ring-green-400";
                              } else if (wasSelected && !isCorrect) {
                                  bgColor = "bg-red-100 border-red-400";
                              }
                              
                              return (
                                  <div
                                      key={idx}
                                      className={`p-4 rounded-xl border-2 ${bgColor} transition-all flex items-start gap-3`}
                                  >
                                      <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                                          isCorrect ? 'bg-green-500 text-white' : wasSelected ? 'bg-red-500 text-white' : 'bg-slate-200 text-slate-600'
                                      }`}>
                                          {String.fromCharCode(65 + idx)}
                                      </span>
                                      <span className={`text-sm ${isCorrect ? 'font-semibold text-green-800' : 'text-slate-700'}`}>
                                          {option}
                                      </span>
                                  </div>
                              );
                          })}
                      </div>
                      
                      {/* Feedback Banner */}
                      <div className={`text-center p-3 rounded-xl font-semibold text-lg ${
                          timedOut 
                              ? 'bg-orange-500 text-white'
                              : answerResult?.is_correct
                                  ? 'bg-green-500 text-white' 
                                  : 'bg-red-500 text-white'
                      }`}>
                          {timedOut ? "⏱️ Time Out!" : answerResult?.is_correct ? "🎉 Correct!" : "❌ Incorrect"}
                      </div>
                      
                      {/* Next Button */}
                      <Button 
                          size="lg" 
                          className="w-full h-14 text-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-lg" 
                          onClick={handleNext}
                      >
                          Next Question <ArrowRight className="ml-2 h-5 w-5" />
                      </Button>
                  </div>
              ) : (
                  // Show Options - 2x2 Grid with Colors
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {currentCard.options?.map((option: string, idx: number) => {
                          // Color palette for each option
                          const colors = [
                              "border-rose-300 hover:border-rose-500 hover:bg-rose-50 focus:ring-rose-400",
                              "border-amber-300 hover:border-amber-500 hover:bg-amber-50 focus:ring-amber-400",
                              "border-emerald-300 hover:border-emerald-500 hover:bg-emerald-50 focus:ring-emerald-400",
                              "border-sky-300 hover:border-sky-500 hover:bg-sky-50 focus:ring-sky-400",
                          ];
                          const badgeColors = [
                              "bg-rose-500",
                              "bg-amber-500", 
                              "bg-emerald-500",
                              "bg-sky-500",
                          ];
                          
                          return (
                              <button
                                  key={idx}
                                  className={`
                                      w-full text-left p-4 rounded-xl border-2 bg-white
                                      ${colors[idx % 4]}
                                      transition-all duration-200 ease-out
                                      hover:shadow-md hover:scale-[1.02]
                                      focus:outline-none focus:ring-2
                                      flex items-start gap-3
                                  `}
                                  onClick={() => handleOptionSelect(option)}
                              >
                                  <span className={`w-8 h-8 rounded-full ${badgeColors[idx % 4]} text-white flex items-center justify-center text-sm font-bold shrink-0`}>
                                      {String.fromCharCode(65 + idx)}
                                  </span>
                                  <span className="text-slate-700 text-sm leading-relaxed">{option}</span>
                              </button>
                          );
                      })}
                  </div>
              )}
          </div>
      </div>
      
      <style>{`
        .perspective-1000 { perspective: 1000px; }
        .backface-hidden { backface-visibility: hidden; }
      `}</style>
    </div>
  );
}
