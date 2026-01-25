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
import { subjectService } from "@/services/subjects"
import { Loader2 } from "lucide-react"

interface EditSubjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subject: {
    id: string
    name: string
    description?: string
  }
  onSuccess: (updatedSubject: any) => void
}

export function EditSubjectDialog({ open, onOpenChange, subject, onSuccess }: EditSubjectDialogProps) {
  const [name, setName] = useState(subject.name)
  const [description, setDescription] = useState(subject.description || "")
  const [saving, setSaving] = useState(false)

  // Reset form when subject changes or dialog opens
  useEffect(() => {
    if (open) {
      setName(subject.name)
      setDescription(subject.description || "")
    }
  }, [open, subject])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setSaving(true)
      const updated = await subjectService.updateSubject(subject.id, {
        name,
        description
      })
      onSuccess(updated)
      onOpenChange(false)
    } catch (error) {
      console.error("Failed to update subject", error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSave}>
          <DialogHeader>
            <DialogTitle>Edit Subject</DialogTitle>
            <DialogDescription>
              Update the subject details.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
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
