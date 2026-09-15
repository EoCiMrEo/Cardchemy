import { useState } from 'react'
import { Check, Copy, Link as LinkIcon, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { copy } from '@/i18n/en'
import { apiErrorMessage } from '@/services/errors'
import { subjectService } from '@/services/subjects'

interface InviteStudentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subjectId: string
  subjectName: string
}

export function InviteStudentDialog({ open, onOpenChange, subjectId, subjectName }: InviteStudentDialogProps) {
  const [expires, setExpires] = useState('24')
  const [loading, setLoading] = useState(false)
  const [inviteLink, setInviteLink] = useState('')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await subjectService.generateInvite(subjectId, Number(expires))
      setInviteLink(`${window.location.origin}/join?token=${encodeURIComponent(result.token)}`)
      setCopied(false)
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.invite.failed))
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    if (!inviteLink) return
    setError(null)
    try {
      await navigator.clipboard.writeText(inviteLink)
      setCopied(true)
    } catch (caught: unknown) {
      setError(apiErrorMessage(caught, copy.invite.copyFailed))
    }
  }

  const handleClose = (nextOpen: boolean) => {
    onOpenChange(nextOpen)
    if (!nextOpen) {
      setInviteLink('')
      setCopied(false)
      setError(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{copy.invite.title}</DialogTitle>
          <DialogDescription>{copy.invite.description(subjectName)}</DialogDescription>
        </DialogHeader>

        {!inviteLink ? (
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="invite-expiration">{copy.invite.expiration}</Label>
              <Select value={expires} onValueChange={setExpires}>
                <SelectTrigger id="invite-expiration">
                  <SelectValue placeholder={copy.invite.selectExpiration} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="24">{copy.invite.hours24}</SelectItem>
                  <SelectItem value="72">{copy.invite.days3}</SelectItem>
                  <SelectItem value="168">{copy.invite.days7}</SelectItem>
                  <SelectItem value="720">{copy.invite.days30}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{copy.invite.expirationHelp}</p>
            </div>
            <Button type="button" onClick={() => void handleGenerate()} disabled={loading} className="w-full">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : <LinkIcon className="mr-2 h-4 w-4" aria-hidden="true" />}
              {loading ? copy.invite.generating : copy.invite.generate}
            </Button>
          </div>
        ) : (
          <div className="space-y-4 py-4">
            <p className="rounded-lg bg-green-50 p-4 text-center text-sm text-green-800" role="status">
              {copy.invite.generated}
            </p>
            <div className="flex items-center space-x-2">
              <label htmlFor="invite-link" className="sr-only">{copy.invite.generated}</label>
              <Input id="invite-link" readOnly value={inviteLink} className="flex-1 bg-slate-50 font-mono text-xs" onClick={(event) => event.currentTarget.select()} />
              <Button type="button" size="icon" variant="outline" onClick={() => void handleCopy()} aria-label={copied ? copy.invite.copied : copy.invite.copy}>
                {copied ? <Check className="h-4 w-4 text-green-600" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
              </Button>
            </div>
            <Button type="button" variant="ghost" className="w-full" onClick={() => setInviteLink('')}>
              {copy.invite.generateAnother}
            </Button>
          </div>
        )}
        {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}
      </DialogContent>
    </Dialog>
  )
}
