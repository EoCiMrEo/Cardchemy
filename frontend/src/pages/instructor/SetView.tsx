import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { subjectService } from "@/services/subjects"
import { flashcardService } from "@/services/flashcards"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { ChevronLeft, Check, X, Loader2, Save, Trash2, Play } from "lucide-react"
import { PreviewDialog } from "@/components/sets/PreviewDialog"

export default function SetView() {
  const { id } = useParams<{ id: string }>()
  const [set, setSet] = useState<any>(null)
  const [cards, setCards] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState({ front: "", back: "" })
  const [saving, setSaving] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)

  useEffect(() => {
    if (id) loadData()
  }, [id])

  const loadData = async () => {
    try {
      setLoading(true)
      
      const [setData, cardsData] = await Promise.all([
        subjectService.getSet(id!),
        flashcardService.getCards(id!)
      ])
      
      setSet(setData)
      setCards(cardsData)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }
  
  const handleEdit = (card: any) => {
      setEditingId(card.id)
      setEditValues({ front: card.front_content, back: card.back_content })
  }
  
  const handleSave = async (cardId: string) => {
      try {
          setSaving(true)
          await flashcardService.updateCard(cardId, {
              front_content: editValues.front,
              back_content: editValues.back,
              is_approved: true // saving implies approval
          })
          setEditingId(null)
          
          // Update local state
          setCards(cards.map(c => 
              c.id === cardId ? { ...c, front_content: editValues.front, back_content: editValues.back, is_approved: true } : c
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
        setCards(cards.filter(c => c.id !== cardId))
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
                        <label className="text-xs font-bold text-muted-foreground uppercase">Back</label>
                        <Textarea 
                            value={editValues.back}
                            onChange={(e) => setEditValues({...editValues, back: e.target.value})}
                        />
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
               
               {card.source_chunk && (
                   <div className="text-xs text-muted-foreground border-t pt-2 mt-2 italic">
                       Source: "...{card.source_chunk.substring(0, 100)}..."
                   </div>
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
