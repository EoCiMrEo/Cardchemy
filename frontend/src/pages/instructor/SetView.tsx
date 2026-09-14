import { useCallback, useEffect, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { subjectService } from "@/services/subjects"
import { flashcardService } from "@/services/flashcards"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { ChevronLeft, Check, Loader2, Save, Trash2, Play } from "lucide-react"
import { PreviewDialog } from "@/components/sets/PreviewDialog"
import type { Flashcard } from "@/services/types"

interface EditValues {
  front: string
  options: [string, string, string, string]
  correctOptionIndex: number
}

interface SetDetails {
  id: string
  title: string
}

export default function SetView() {
  const { id } = useParams<{ id: string }>()
  const [set, setSet] = useState<SetDetails | null>(null)
  const [cards, setCards] = useState<Flashcard[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<EditValues>({
    front: "",
    options: ["", "", "", ""],
    correctOptionIndex: 0,
  })
  const [saving, setSaving] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)

  const loadData = useCallback(async () => {
    if (!id) return
    try {
      setLoading(true)
      
      const [setData, cardsData] = await Promise.all([
        subjectService.getSet(id),
        flashcardService.getCards(id)
      ])
      
      setSet(setData)
      setCards(cardsData)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void loadData()
  }, [loadData])
  
  const handleEdit = (card: Flashcard) => {
      setEditingId(card.id)
      const correctOptionIndex = card.options.findIndex(
        option => option.trim().toLocaleLowerCase() === card.back_content.trim().toLocaleLowerCase()
      )
      setEditValues({
        front: card.front_content,
        options: [...card.options],
        correctOptionIndex: correctOptionIndex >= 0 ? correctOptionIndex : 0,
      })
  }
  
  const handleSave = async (cardId: string) => {
      try {
          setSaving(true)
          await flashcardService.updateCard(cardId, {
              front_content: editValues.front,
              back_content: editValues.options[editValues.correctOptionIndex],
              options: editValues.options,
              is_approved: true // saving implies approval
          })
          setEditingId(null)
          
          // Update local state
          setCards((currentCards) => currentCards.map(c =>
              c.id === cardId ? {
                ...c,
                front_content: editValues.front.trim(),
                back_content: editValues.options[editValues.correctOptionIndex].trim(),
                options: editValues.options.map(option => option.trim()) as [string, string, string, string],
                is_approved: true,
              } : c
          ))
      } catch (e) {
          console.error(e)
      } finally {
          setSaving(false)
      }
  }

  const handleApproveAll = async () => {
      if (!confirm("Approve all cards in this set?")) return
      try {
          setLoading(true)
          await flashcardService.approveAll(id!)
          const cardsData = await flashcardService.getCards(id!)
          setCards(cardsData)
      } catch (e) {
          console.error(e)
      } finally {
          setLoading(false)
      }
  }

  const handleDelete = async (cardId: string) => {
    if (!confirm("Are you sure you want to delete this flashcard?")) return
    try {
        await flashcardService.deleteCard(cardId)
        setCards((currentCards) => currentCards.filter(c => c.id !== cardId))
    } catch (e) {
        console.error(e)
    }
  }

  if (loading) return <div className="p-8"><Loader2 className="animate-spin" /></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
            <Link to="#" onClick={() => window.history.back()}>
            <Button variant="ghost" size="icon">
                <ChevronLeft className="h-5 w-5" />
            </Button>
            </Link>
            <h1 className="text-2xl font-bold">{set?.title || "Review Flashcards"}</h1>
        </div>
        <div className="flex gap-2">
            <Button onClick={() => setPreviewOpen(true)} variant="outline">
                <Play className="mr-2 h-4 w-4" /> Preview
            </Button>
            <Button onClick={handleApproveAll} variant="default">
                Approve All
            </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.id} className={card.is_approved ? "border-green-200 bg-green-50/30" : "border-yellow-200 bg-yellow-50/30"}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.is_approved ? <span className="text-green-600 flex items-center gap-1"><Check className="h-3 w-3"/> Approved</span> : "Needs Review"}
              </CardTitle>
              {!editingId && (
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => handleEdit(card)}>Edit</Button>
                    <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700 hover:bg-red-50" onClick={() => handleDelete(card.id)}>
                        <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
              )}
            </CardHeader>
            <CardContent className="space-y-4 mt-2">
               {editingId === card.id ? (
                   <>
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-muted-foreground uppercase">Front</label>
                        <Textarea 
                            value={editValues.front} 
                            onChange={(e) => setEditValues({...editValues, front: e.target.value})}
                        />
                    </div>
                    <div className="space-y-2">
                        <div className="text-xs font-bold text-muted-foreground uppercase">Options and correct answer</div>
                        {editValues.options.map((option, optionIndex) => (
                          <label key={optionIndex} className="flex items-start gap-2">
                            <input
                              type="radio"
                              name={`correct-${card.id}`}
                              checked={editValues.correctOptionIndex === optionIndex}
                              onChange={() => setEditValues({ ...editValues, correctOptionIndex: optionIndex })}
                              className="mt-3"
                            />
                            <Textarea
                              value={option}
                              onChange={(event) => {
                                const options = [...editValues.options] as [string, string, string, string]
                                options[optionIndex] = event.target.value
                                setEditValues({ ...editValues, options })
                              }}
                            />
                          </label>
                        ))}
                    </div>
                   </>
               ) : (
                   <>
                    <div>
                        <div className="text-xs font-bold text-muted-foreground uppercase mb-1">Front</div>
                        <p className="text-sm font-medium">{card.front_content}</p>
                    </div>
                    <div>
                        <div className="text-xs font-bold text-muted-foreground uppercase mb-1">Back</div>
                         <p className="text-sm text-gray-700">{card.back_content}</p>
                    </div>
                   </>
               )}
               
               {card.source_snippet ? (
                   <figure className="border-t pt-2 mt-2 text-xs text-muted-foreground">
                       <figcaption className="font-medium not-italic">
                         Verified source{card.source_page ? ` · Page ${card.source_page}` : ''}
                         {card.source_section ? ` · ${card.source_section}` : ''}
                       </figcaption>
                       <blockquote className="mt-1 border-l-2 pl-2 italic">
                         “{card.source_snippet}”
                       </blockquote>
                   </figure>
               ) : (
                 <p className="border-t pt-2 mt-2 text-xs text-muted-foreground">
                   Manual card; no generated source reference.
                 </p>
               )}
            </CardContent>
            {editingId === card.id && (
                <CardFooter className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setEditingId(null)}>Cancel</Button>
                    <Button size="sm" onClick={() => handleSave(card.id)} disabled={saving}>
                        {saving ? <Loader2 className="h-3 w-3 animate-spin"/> : <><Save className="h-3 w-3 mr-1"/> Save</>}
                    </Button>
                </CardFooter>
            )}
          </Card>
        ))}
      </div>

      <PreviewDialog 
        open={previewOpen} 
        onOpenChange={setPreviewOpen} 
        cards={cards} 
        title={set?.title || "Flashcards"} 
      />
    </div>
  )
}
