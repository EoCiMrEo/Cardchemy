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
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { subjectService } from '@/services/subjects'
import type { FlashcardSet } from '@/services/types'

interface EditSetDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subjectId: string
  set: FlashcardSet
  onSuccess: () => void
}

interface EditSetFormProps extends Pick<EditSetDialogProps, 'subjectId' | 'set' | 'onSuccess'> {
  onCancel: () => void
}

function EditSetForm({ subjectId, set, onSuccess, onCancel }: EditSetFormProps) {
  const [title, setTitle] = useState(set.title)
  const [description, setDescription] = useState(set.description ?? '')
  const [isPublished, setIsPublished] = useState(set.is_published)
  const [timeLimit, setTimeLimit] = useState<number | string>(set.time_limit ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault()
    const parsedTimeLimit = timeLimit === '' ? null : Number(timeLimit)
    if (!title.trim()) {
      setError(copy.editSet.titleRequired)
      return
    }
    if (parsedTimeLimit !== null && (!Number.isInteger(parsedTimeLimit) || parsedTimeLimit < 5 || parsedTimeLimit > 3600)) {
      setError(copy.editSet.timeLimitInvalid)
      return
    }

    setSaving(true)
    setError(null)
    try {
      await subjectService.updateSet(subjectId, set.id, {
        title: title.trim(),
        description: description.trim() || null,
        is_published: isPublished,
        time_limit: parsedTimeLimit,
      })
      onSuccess()
      onCancel()
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.editSet.failed))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(event) => void handleSave(event)}>
      <DialogHeader>
        <DialogTitle>{copy.editSet.title}</DialogTitle>
        <DialogDescription>{copy.editSet.description}</DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4">
        <div className="grid gap-2">
          <Label htmlFor="set-title">{copy.editSet.titleLabel}</Label>
          <Input id="set-title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={255} required />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="set-description">{copy.editSet.descriptionLabel}</Label>
          <Textarea
            id="set-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder={copy.editSet.optionalDescription}
            maxLength={10_000}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="set-time-limit">{copy.editSet.timeLimit}</Label>
          <Input
            id="set-time-limit"
            type="number"
            min={5}
            max={3600}
            value={timeLimit}
            onChange={(event) => setTimeLimit(event.target.value)}
            placeholder={copy.editSet.optionalTimeLimit}
          />
          <p className="text-xs text-muted-foreground">{copy.editSet.noTimeLimit}</p>
        </div>
        <div className="flex items-center justify-between space-x-2 rounded-md border p-3">
          <Label htmlFor="set-published" className="flex flex-col space-y-1">
            <span>{copy.editSet.published}</span>
            <span className="text-xs font-normal text-muted-foreground">{copy.editSet.visibleToStudents}</span>
          </Label>
          <Switch id="set-published" checked={isPublished} onCheckedChange={setIsPublished} />
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

export function EditSetDialog({ open, onOpenChange, subjectId, set, onSuccess }: EditSetDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        {open ? (
          <EditSetForm
            key={`${set.id}:${set.created_at}`}
            subjectId={subjectId}
            set={set}
            onSuccess={onSuccess}
            onCancel={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
