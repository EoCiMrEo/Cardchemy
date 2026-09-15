import { useState } from 'react'
import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { subjectService } from '@/services/subjects'
import type { Subject } from '@/services/types'

interface EditSubjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subject: Subject
  onSuccess: (updatedSubject: Subject) => void
}

interface EditSubjectFormProps {
  subject: Subject
  onCancel: () => void
  onSuccess: (updatedSubject: Subject) => void
}

function EditSubjectForm({ subject, onCancel, onSuccess }: EditSubjectFormProps) {
  const [name, setName] = useState(subject.name)
  const [description, setDescription] = useState(subject.description ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim()) {
      setError(copy.editSubject.nameRequired)
      return
    }

    setSaving(true)
    setError(null)
    try {
      const updated = await subjectService.updateSubject(subject.id, {
        name: name.trim(),
        description: description.trim() || null,
      })
      onSuccess(updated)
      onCancel()
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.editSubject.failed))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(event) => void handleSave(event)}>
      <DialogHeader>
        <DialogTitle>{copy.editSubject.title}</DialogTitle>
        <DialogDescription>{copy.editSubject.description}</DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4">
        <div className="grid gap-2">
          <Label htmlFor="subject-name">{copy.editSubject.name}</Label>
          <Input id="subject-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={255} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="subject-description">{copy.editSubject.descriptionLabel}</Label>
          <Textarea
            id="subject-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder={copy.editSubject.optionalDescription}
            maxLength={10_000}
          />
        </div>
        {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>{copy.common.cancel}</Button>
        <Button type="submit" disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
          {saving ? copy.common.saving : copy.common.saveChanges}
        </Button>
      </DialogFooter>
    </form>
  )
}

export function EditSubjectDialog({ open, onOpenChange, subject, onSuccess }: EditSubjectDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        {open ? (
          <EditSubjectForm
            key={`${subject.id}:${subject.name}:${subject.description ?? ''}`}
            subject={subject}
            onCancel={() => onOpenChange(false)}
            onSuccess={onSuccess}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
