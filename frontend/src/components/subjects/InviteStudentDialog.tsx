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
  const [recipientEmail, setRecipientEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [inviteLink, setInviteLink] = useState('')
  const [deliveryRequested, setDeliveryRequested] = useState(false)
  const [deliveryQueued, setDeliveryQueued] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    const normalizedRecipient = recipientEmail.trim()
    setLoading(true)
    setError(null)
    try {
      const result = await subjectService.generateInvite(
        subjectId,
        Number(expires),
        normalizedRecipient || undefined,
      )
      setInviteLink(result.invite_url)
      setDeliveryRequested(Boolean(normalizedRecipient))
      setDeliveryQueued(result.delivery_queued)
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
      setRecipientEmail('')
      setInviteLink('')
      setDeliveryRequested(false)
      setDeliveryQueued(false)
      setCopied(false)
      setError(null)
    }
  }

  const generateAnother = () => {
    setInviteLink('')
    setDeliveryRequested(false)
    setDeliveryQueued(false)
    setCopied(false)
    setError(null)
  }

  const successMessage = deliveryQueued
    ? copy.invite.emailQueued
    : deliveryRequested
      ? copy.invite.emailNotQueued
      : copy.invite.generated

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{copy.invite.title}</DialogTitle>
          <DialogDescription className="break-words">{copy.invite.description(subjectName)}</DialogDescription>
        </DialogHeader>

        {!inviteLink ? (
          <form
            className="space-y-4 py-4"
            onSubmit={(event) => {
              event.preventDefault()
              void handleGenerate()
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="invite-recipient-email">{copy.invite.recipientEmail}</Label>
              <Input
                id="invite-recipient-email"
                type="email"
                value={recipientEmail}
                onChange={(event) => setRecipientEmail(event.target.value)}
                placeholder={copy.invite.recipientEmailPlaceholder}
                aria-describedby="invite-recipient-help"
                autoComplete="email"
                maxLength={255}
                disabled={loading}
              />
              <p id="invite-recipient-help" className="text-xs text-muted-foreground">
                {copy.invite.recipientEmailHelp}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-expiration">{copy.invite.expiration}</Label>
              <Select value={expires} onValueChange={setExpires} disabled={loading}>
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
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : <LinkIcon className="mr-2 h-4 w-4" aria-hidden="true" />}
              {loading
                ? copy.invite.generating
                : recipientEmail.trim()
                  ? copy.invite.generateAndSend
                  : copy.invite.generate}
            </Button>
          </form>
        ) : (
          <div className="space-y-4 py-4">
            <p
              className={`break-words rounded-lg p-4 text-center text-sm ${
                deliveryRequested && !deliveryQueued
                  ? 'bg-amber-50 text-amber-900'
                  : 'bg-green-50 text-green-800'
              }`}
              role="status"
            >
              {successMessage}
            </p>
            <div className="flex min-w-0 items-center gap-2">
              <label htmlFor="invite-link" className="sr-only">{copy.invite.copyableLink}</label>
              <Input id="invite-link" readOnly value={inviteLink} className="min-w-0 flex-1 bg-slate-50 font-mono text-xs" onClick={(event) => event.currentTarget.select()} />
              <Button type="button" size="icon" variant="outline" onClick={() => void handleCopy()} aria-label={copied ? copy.invite.copied : copy.invite.copy}>
                {copied ? <Check className="h-4 w-4 text-green-600" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
              </Button>
            </div>
            <Button type="button" variant="ghost" className="w-full" onClick={generateAnother}>
              {copy.invite.generateAnother}
            </Button>
          </div>
        )}
        {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}
      </DialogContent>
    </Dialog>
  )
}
