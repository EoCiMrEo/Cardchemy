import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { subjectService } from "@/services/subjects"
import { Loader2 } from "lucide-react"

interface EditSetDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subjectId: string
  set: {
    id: string
    title: string
    description?: string
    is_published: boolean
    time_limit?: number | null
  }
  onSuccess: () => void
}

export function EditSetDialog({ open, onOpenChange, subjectId, set, onSuccess }: EditSetDialogProps) {
  const [title, setTitle] = useState(set.title)
  const [description, setDescription] = useState(set.description || "")
  const [isPublished, setIsPublished] = useState(set.is_published)
  const [timeLimit, setTimeLimit] = useState<number | string>(set.time_limit || "")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setTitle(set.title)
      setDescription(set.description || "")
      setIsPublished(set.is_published)
      setTimeLimit(set.time_limit || "")
    }
  }, [open, set])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setSaving(true)
      await subjectService.updateSet(subjectId, set.id, {
        title,
        description,
        is_published: isPublished,
        time_limit: timeLimit ? Number(timeLimit) : null
      })
      onSuccess()
      onOpenChange(false)
    } catch (error) {
      console.error("Failed to update set", error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSave}>
          <DialogHeader>
            <DialogTitle>Edit Flashcard Set</DialogTitle>
            <DialogDescription>
              Update the set details and visibility.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="timeLimit">Time Limit (seconds)</Label>
              <Input
                id="timeLimit"
                type="number"
                min="0"
                value={timeLimit}
                onChange={(e) => setTimeLimit(e.target.value)}
                placeholder="Optional (e.g. 10)"
              />
              <p className="text-xs text-muted-foreground">Leave empty for no limit.</p>
            </div>
            <div className="flex items-center justify-between space-x-2 border p-3 rounded-md">
                <Label htmlFor="published" className="flex flex-col space-y-1">
                    <span>Published</span>
                    <span className="font-normal text-xs text-muted-foreground">
                        Visible to students
                    </span>
                </Label>
                <Switch 
                    id="published" 
                    checked={isPublished}
                    onCheckedChange={setIsPublished}
                />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
