import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { subjectService } from "@/services/subjects"
import { flashcardService } from "@/services/flashcards"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ChevronLeft, FileText, Upload, Loader2, BrainCircuit, Pencil, Trash2 } from "lucide-react"
import { EditSubjectDialog } from "@/components/subjects/EditSubjectDialog"
import { EditSetDialog } from "@/components/sets/EditSetDialog"
import { useNavigate } from "react-router-dom"

export default function SubjectDetails() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [subject, setSubject] = useState<any>(null)
  const [sets, setSets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  
  // Upload State
  const [isUploading, setIsUploading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [setTitle, setSetTitle] = useState("")
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState("")
  const [cardCount, setCardCount] = useState("20")

  // Edit/Delete State
  const [isEditSubjectOpen, setIsEditSubjectOpen] = useState(false)
  const [editingSet, setEditingSet] = useState<any>(null)
  const [isEditSetOpen, setIsEditSetOpen] = useState(false)

  useEffect(() => {
    if (id) loadData()
  }, [id])

  const loadData = async () => {
    try {
      setLoading(true)
      const [subData, setsData] = await Promise.all([
        subjectService.getSubject(id!),
        subjectService.getSets(id!)
      ])
      setSubject(subData)
      setSets(setsData)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (e: React.FormEvent) => {
      e.preventDefault()
      if (!file || !setTitle) return

      try {
          setUploading(true)
          setUploadMessage("Uploading & Processing PDF...")
          
          const formData = new FormData()
          formData.append('subject_id', id!)
          formData.append('set_title', setTitle)
          formData.append('pdf_file', file)
          formData.append('card_count', cardCount)
          
          // AI Generation can take time
          setUploadMessage("AI Agents extracting concepts...")
          
          const result = await flashcardService.generateCards(formData)
          
          setUploadMessage("Done!")
          setIsUploading(false)
          setFile(null)
          setSetTitle("")
          loadData() // Reload sets
          
      } catch (e: any) {
          console.error(e)
          setUploadMessage("Failed: " + (e.response?.data?.detail || e.message))
      } finally {
          setUploading(false)
      }
  }

  const handleDeleteSubject = async () => {
      if (confirm("Are you sure you want to delete this subject? This action cannot be undone and will delete all flashcard sets.")) {
          try {
              setLoading(true)
              await subjectService.deleteSubject(id!)
              navigate('/dashboard')
          } catch (e) {
              console.error(e)
              setLoading(false)
          }
      }
  }

  const handleDeleteSet = async (setId: string, e: React.MouseEvent) => {
      e.preventDefault() // prevent navigation
      e.stopPropagation()
      
      if (confirm("Are you sure you want to delete this flashcard set?")) {
          try {
              await subjectService.deleteSet(id!, setId)
              setSets(sets.filter(s => s.id !== setId))
          } catch (e) {
              console.error(e)
          }
      }
  }

  const openEditSet = (e: React.MouseEvent, set: any) => {
      e.preventDefault()
      e.stopPropagation()
      setEditingSet(set)
      setIsEditSetOpen(true)
  }

  if (loading) return <div className="p-8"><Loader2 className="animate-spin" /></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/dashboard">
          <Button variant="ghost" size="icon">
            <ChevronLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-bold">{subject?.name}</h1>
              <p className="text-muted-foreground">{subject?.description || "No description"}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setIsEditSubjectOpen(true)}>
                <Pencil className="h-4 w-4 mr-1" /> Edit
              </Button>
              <Button variant="destructive" size="sm" onClick={handleDeleteSubject}>
                <Trash2 className="h-4 w-4 mr-1" /> Delete
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center border-b pb-4">
        <h2 className="text-xl font-semibold">Flashcard Sets</h2>
        <Button onClick={() => setIsUploading(!isUploading)}>
          <Upload className="mr-2 h-4 w-4" /> Generate Flashcards Set
        </Button>
      </div>

      {isUploading && (
        <Card className="bg-slate-50 border-dashed">
            <CardHeader>
                <CardTitle>Generate Flashcards from PDF</CardTitle>
                <CardDescription>Upload a lecture slide or document. AI will extract Q/A pairs.</CardDescription>
            </CardHeader>
            <CardContent>
                <form onSubmit={handleUpload} className="space-y-4 max-w-md">
                    <div>
                        <label className="text-sm font-medium">Set Title</label>
                        <Input 
                            value={setTitle}
                            onChange={(e) => setSetTitle(e.target.value)}
                            placeholder="Chapter 1: Initial Generation"
                            required
                        />
                    </div>
                    <div>
                        <div className="mb-2 text-sm font-medium">Number of Cards</div>
                        <div className="flex gap-4">
                            {["5", "10", "15", "20"].map(num => (
                                <label key={num} className="flex items-center gap-2 cursor-pointer">
                                    <input 
                                        type="radio" 
                                        name="cardCount" 
                                        value={num}
                                        checked={cardCount === num}
                                        onChange={(e) => setCardCount(e.target.value)}
                                        className="accent-primary"
                                    />
                                    <span>{num}</span>
                                </label>
                            ))}
                        </div>
                    </div>
                    <div>
                        <label className="text-sm font-medium">PDF File</label>
                        <Input 
                            type="file" 
                            accept=".pdf"
                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                            required
                        />
                    </div>
                    
                    {uploading && (
                        <div className="text-sm text-blue-600 flex items-center bg-blue-50 p-2 rounded">
                            <Loader2 className="animate-spin mr-2 h-4 w-4" />
                            {uploadMessage}
                        </div>
                    )}

                    <Button type="submit" disabled={uploading} className="w-full">
                        {uploading ? "Processing..." : "Generate with AI"}
                    </Button>
                </form>
            </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sets.map((set) => (
          <Card key={set.id}>
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                <div className="flex items-center gap-2">
                   <FileText className="h-4 w-4 text-blue-500" />
                   {set.title}
                </div>
                <div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={(e) => openEditSet(e, set)}>
                        <Pencil className="h-3 w-3" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50" onClick={(e) => handleDeleteSet(set.id, e)}>
                        <Trash2 className="h-3 w-3" />
                    </Button>
                </div>
              </CardTitle>
              <CardDescription>
                 Generated from {set.source_pdf_name || "Manual"}
              </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="flex justify-between items-center text-sm">
                    <span className={`px-2 py-1 rounded-full ${set.is_published ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                        {set.is_published ? "Published" : "Draft"}
                    </span>
                    <span className="text-muted-foreground">
                        {set.flashcard_count || 0} cards
                    </span>
                </div>
                <Link to={`/sets/${set.id}`}>
                    <Button variant="secondary" className="w-full mt-4">
                        View & Edit Cards
                    </Button>
                </Link>
            </CardContent>
          </Card>
        ))}
        
        {subject && (
            <EditSubjectDialog 
                open={isEditSubjectOpen} 
                onOpenChange={setIsEditSubjectOpen} 
                subject={subject}
                onSuccess={setSubject} 
            />
        )}
        
        {editingSet && (
            <EditSetDialog 
                open={isEditSetOpen} 
                onOpenChange={setIsEditSetOpen} 
                subjectId={id!}
                set={editingSet}
                onSuccess={() => {
                    loadData() // Reload to get updated sets
                    setEditingSet(null)
                }} 
            />
        )}
        
        {sets.length === 0 && !loading && (
            <div className="col-span-full py-12 text-center text-muted-foreground">
                <BrainCircuit className="mx-auto h-12 w-12 opacity-20 mb-4" />
                <p>No flashcard sets yet. Upload a PDF to generate one!</p>
            </div>
        )}
      </div>
    </div>
  )
}
