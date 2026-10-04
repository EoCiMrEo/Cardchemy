import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, RefreshCw, Square, UploadCloud } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { apiErrorMessage } from '@/services/errors'
import type { GenerationJob, KnowledgeDuplicateChoice } from '@/services/types'
import { copy } from '@/i18n/en'

interface GenerationJobCardProps {
  job: GenerationJob
  onCancel: (jobId: string) => Promise<void>
  onRetry: (jobId: string, idempotencyKey: string, acknowledgeAdditionalCost: boolean) => Promise<void>
  onChooseKnowledge: (jobId: string, choice: KnowledgeDuplicateChoice, idempotencyKey: string) => Promise<void>
  onChooseCardCount: (jobId: string, cardCount: number, idempotencyKey: string) => Promise<void>
}

function stageLabel(stage: string): string {
  return stage.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
}

function formatTokens(value: number | null): string {
  return value === null ? copy.generation.unavailable : new Intl.NumberFormat('en').format(value)
}

function formatCost(microusd: number | null): string {
  return microusd === null ? copy.generation.pricingNotConfigured : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(microusd / 1_000_000)
}

function formatRateLimitWait(milliseconds: number): string {
  return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(milliseconds / 1000)} s`
}

export function GenerationJobCard({ job, onCancel, onRetry, onChooseKnowledge, onChooseCardCount }: GenerationJobCardProps) {
  const [action, setAction] = useState<'cancel' | 'retry' | 'choice' | 'card_choice' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const retryKeyRef = useRef<string | null>(null)
  const choiceKeyRef = useRef<string | null>(null)
  const cardChoiceRef = useRef<{ count: number; key: string } | null>(null)
  const [submittedChoice, setSubmittedChoice] = useState<KnowledgeDuplicateChoice | null>(null)
  const [submittedCardCount, setSubmittedCardCount] = useState<number | null>(null)
  const [cardChoiceCount, setCardChoiceCount] = useState<number | null>(null)
  const [choiceOpen, setChoiceOpen] = useState(false)
  const [cardChoiceOpen, setCardChoiceOpen] = useState(false)
  const [retryOpen, setRetryOpen] = useState(false)

  const handleCancel = async () => {
    setAction('cancel')
    setActionError(null)
    try {
      await onCancel(job.id)
      setChoiceOpen(false)
      setCardChoiceOpen(false)
      setRetryOpen(false)
    } catch (error) {
      setActionError(apiErrorMessage(error, copy.generation.cancellationFailed))
    } finally {
      setAction(null)
    }
  }

  const handleChoice = async (choice: KnowledgeDuplicateChoice) => {
    if (submittedChoice && submittedChoice !== choice) return
    setAction('choice')
    setActionError(null)
    setSubmittedChoice(choice)
    try {
      choiceKeyRef.current ??= crypto.randomUUID()
      await onChooseKnowledge(job.id, choice, choiceKeyRef.current)
      choiceKeyRef.current = null
      setChoiceOpen(false)
    } catch (error) {
      setActionError(apiErrorMessage(error, copy.generation.choiceFailed))
    } finally {
      setAction(null)
    }
  }

  const handleRetry = async () => {
    setAction('retry')
    setActionError(null)
    try {
      retryKeyRef.current ??= crypto.randomUUID()
      await onRetry(job.id, retryKeyRef.current, job.status === 'awaiting_card_choice')
      retryKeyRef.current = null
      setRetryOpen(false)
    } catch (error) {
      setActionError(apiErrorMessage(error, copy.generation.retryFailed))
    } finally {
      setAction(null)
    }
  }

  const handleCardChoice = async () => {
    const count = cardChoiceCount ?? job.valid_candidate_count
    if (!job.can_accept_smaller_target || !Number.isInteger(count) || count < 1 || count > job.valid_candidate_count) return
    if (cardChoiceRef.current && cardChoiceRef.current.count !== count) return
    setAction('card_choice')
    setActionError(null)
    setSubmittedCardCount(count)
    try {
      cardChoiceRef.current ??= { count, key: crypto.randomUUID() }
      await onChooseCardCount(job.id, count, cardChoiceRef.current.key)
      cardChoiceRef.current = null
      setCardChoiceOpen(false)
    } catch (error) {
      setActionError(apiErrorMessage(error, copy.generation.cardChoiceFailed))
    } finally {
      setAction(null)
    }
  }

  const isActive = ['awaiting_upload', 'queued', 'running'].includes(job.status)
  // The candidate can be removed after the upload.  Keep the durable choice
  // recoverable so the owner can still create a separate copy or cancel.
  const awaitingChoice = job.status === 'awaiting_choice'
  const awaitingCardChoice = job.status === 'awaiting_card_choice'
  const selectedCardCount = cardChoiceCount ?? job.valid_candidate_count
  const cardCountValid = Number.isInteger(selectedCardCount) && selectedCardCount >= 1 && selectedCardCount <= job.valid_candidate_count

  return (
    <Card className="border-blue-200 bg-blue-50/40">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-3 text-base">
          <span className="min-w-0 truncate">{job.source_pdf_name}</span>
          <span className="shrink-0 rounded-full bg-white px-2 py-1 text-xs capitalize text-slate-700">
            {copy.generation.status(job.status)}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div role={job.status === 'failed' ? 'alert' : 'status'} aria-live="polite">
          <div className="mb-2 flex items-center gap-2 text-sm text-slate-700">
            {isActive ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            <span>{stageLabel(job.stage)}</span>
            {job.attempt_count > 0 ? (
              <span className="text-xs text-slate-700">
                {copy.generation.attempt(job.attempt_count, job.max_attempts)}
              </span>
            ) : null}
          </div>
          <Progress
            value={job.progress}
            aria-label={copy.generation.progress(job.source_pdf_name)}
            aria-valuetext={copy.generation.progressValue(job.progress, stageLabel(job.stage))}
          />
        </div>

        {job.cancellation_requested_at ? (
          <p className="text-sm text-amber-700">{copy.generation.cancellationPending}</p>
        ) : null}
        {job.error_message && !awaitingCardChoice ? (
          <p className="rounded bg-red-50 p-2 text-sm text-red-700" role="alert">
            {job.error_message}
          </p>
        ) : null}
        {job.limit_reason_message && job.limit_reason_message !== job.error_message ? (
          <p className="rounded bg-amber-50 p-2 text-sm text-amber-800" role="status">
            {job.limit_reason_message}
          </p>
        ) : null}
        {job.knowledge_upload_outcome ? (
          <p className="rounded bg-blue-50 p-2 text-sm text-blue-800" role="status">
            {copy.generation.knowledgeOutcome(job.knowledge_upload_outcome)}
          </p>
        ) : null}
        {awaitingChoice ? (
          <p className="rounded bg-amber-50 p-2 text-sm text-amber-900" role="status">
            {copy.generation.duplicatePending}
          </p>
        ) : null}
        {awaitingCardChoice ? (
          <p className="rounded bg-amber-50 p-2 text-sm text-amber-900" role="status">
            {copy.generation.cardChoicePending(job.valid_candidate_count, job.requested_card_count)}
          </p>
        ) : null}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-700">
          <div>
            <dt className="font-medium">{copy.generation.provider}</dt>
            <dd>{job.ai_provider} / {job.ai_model}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.persistedCards}</dt>
            <dd>{job.accepted_card_count}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.latestAttemptValidation}</dt>
            <dd>{job.latest_attempt_quality_diagnostics
              ? copy.generation.latestAttemptCounts(job.latest_attempt_quality_diagnostics.accepted_count, job.latest_attempt_rejected_card_count)
              : copy.generation.latestAttemptUnavailable}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.rejectedCardsTotal}</dt>
            <dd>{job.rejected_card_count}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.estimatedTokens}</dt>
            <dd>{formatTokens(job.estimated_input_tokens + job.estimated_output_tokens)}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.usedTokens}</dt>
            <dd>
              {formatTokens(
                job.actual_input_tokens === null || job.actual_output_tokens === null
                  ? null
                  : job.actual_input_tokens + job.actual_output_tokens,
              )}
              {job.usage_estimated ? copy.generation.estimatedUsage : ''}
            </dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.providerRequests}</dt>
            <dd>{copy.generation.providerRequestCounts(
              job.provider_request_count,
              job.estimated_request_count,
              job.provider_retry_count,
            )}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.rateLimitWait}</dt>
            <dd>{formatRateLimitWait(job.provider_rate_limit_wait_milliseconds)}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.cachedInputTokens}</dt>
            <dd>{formatTokens(job.cached_input_tokens)}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.estimatedCost}</dt>
            <dd>{formatCost(job.estimated_cost_microusd)}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.recordedCost}</dt>
            <dd>{formatCost(job.actual_cost_microusd)}</dd>
          </div>
        </dl>
        {actionError ? <p className="text-sm text-red-700" role="alert">{actionError}</p> : null}

        <div className="flex flex-wrap gap-2">
          {awaitingChoice ? (
            <Button type="button" variant="outline" size="sm" disabled={action !== null} onClick={() => setChoiceOpen(true)}>
              {copy.generation.reviewDuplicate}
            </Button>
          ) : null}
          {awaitingCardChoice && job.can_accept_smaller_target ? (
            <Button type="button" variant="outline" size="sm" disabled={action !== null} onClick={() => setCardChoiceOpen(true)}>
              {copy.generation.reviewCardChoice}
            </Button>
          ) : null}
          {job.can_cancel ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={action !== null}
              onClick={() => void handleCancel()}
            >
              {action === 'cancel' ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Square className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              {copy.generation.cancel}
            </Button>
          ) : null}
          {job.can_retry ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={action !== null}
              onClick={() => setRetryOpen(true)}
            >
              {action === 'retry' ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              {copy.generation.retry}
            </Button>
          ) : null}
          {job.status === 'completed' && job.flashcard_set_id ? (
            <Button asChild size="sm">
              <Link to={`/sets/${job.flashcard_set_id}`}>
                <UploadCloud className="mr-2 h-4 w-4" aria-hidden="true" />
                {copy.generation.reviewCards(job.generated_card_count ?? 0)}
              </Link>
            </Button>
          ) : null}
        </div>
      </CardContent>
      <Dialog open={choiceOpen && awaitingChoice} onOpenChange={setChoiceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.generation.duplicateTitle}</DialogTitle>
            <DialogDescription>{copy.generation.duplicateDescription}</DialogDescription>
          </DialogHeader>
          {job.duplicate_candidate ? (
            <p className="break-words text-sm">{copy.generation.existingKnowledge(job.duplicate_candidate.title)}</p>
          ) : null}
          {job.duplicate_candidate?.can_reuse ? (
            <p className="text-sm text-muted-foreground">{copy.generation.reuseExplanation}</p>
          ) : (
            <p className="text-sm text-amber-800">{copy.generation.reuseUnavailable}</p>
          )}
          {job.choice_expires_at ? (
            <p className="text-xs text-muted-foreground">{copy.generation.choiceExpiry(new Date(job.choice_expires_at).toLocaleString())}</p>
          ) : null}
          {actionError ? <p className="text-sm text-red-700" role="alert">{actionError}</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={action !== null} onClick={() => void handleCancel()}>
              {copy.generation.cancelWholeJob}
            </Button>
            <Button type="button" variant="outline" disabled={action !== null || submittedChoice === 'reuse'} onClick={() => void handleChoice('separate_copy')}>
              {copy.generation.separateCopy}
            </Button>
            {job.duplicate_candidate?.can_reuse ? (
              <Button type="button" disabled={action !== null || submittedChoice === 'separate_copy'} onClick={() => void handleChoice('reuse')}>
                {copy.generation.reuseKnowledge}
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={cardChoiceOpen && awaitingCardChoice} onOpenChange={setCardChoiceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.generation.cardChoiceTitle}</DialogTitle>
            <DialogDescription>{copy.generation.cardChoiceDescription}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm" aria-live="polite">
            <p>{copy.generation.cardChoicePending(job.valid_candidate_count, job.requested_card_count)}</p>
            <label htmlFor={`card-choice-${job.id}`} className="block font-medium">{copy.generation.cardChoiceLabel}</label>
            <input
              id={`card-choice-${job.id}`}
              type="number"
              inputMode="numeric"
              min={1}
              max={job.valid_candidate_count}
              step={1}
              value={selectedCardCount}
              disabled={action !== null || submittedCardCount !== null}
              aria-invalid={!cardCountValid}
              className="min-h-11 w-28 rounded-md border bg-white px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
              onChange={(event) => setCardChoiceCount(Number(event.target.value))}
            />
            {job.card_choice_expires_at ? (
              <p className="text-xs text-muted-foreground">{copy.generation.cardChoiceExpiry(new Date(job.card_choice_expires_at).toLocaleString())}</p>
            ) : null}
            {actionError ? <p className="text-sm text-red-700" role="alert">{actionError}</p> : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={action !== null} onClick={() => setCardChoiceOpen(false)}>{copy.common.cancel}</Button>
            <Button type="button" disabled={action !== null || !job.can_accept_smaller_target || !cardCountValid || (submittedCardCount !== null && submittedCardCount !== selectedCardCount)} onClick={() => void handleCardChoice()}>
              {action === 'card_choice' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
              {copy.generation.confirmCardChoice(selectedCardCount)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={retryOpen && job.can_retry} onOpenChange={(open) => { if (action !== 'retry') setRetryOpen(open) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.generation.retryDialogTitle}</DialogTitle>
            <DialogDescription>{copy.generation.retryDialogDescription}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 text-sm" aria-live="polite">
            <p>{job.retry_estimated_additional_cost_microusd === null
              ? copy.generation.estimatedAdditionalCostUnavailable
              : copy.generation.estimatedAdditionalCost(formatCost(job.retry_estimated_additional_cost_microusd))}</p>
            <p>{job.previous_attempt_cost_unknown
              ? copy.generation.previousAttemptCostUnknown
              : copy.generation.previousAttemptCostRecorded}</p>
            {actionError ? <p className="text-sm text-red-700" role="alert">{actionError}</p> : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={action !== null} onClick={() => setRetryOpen(false)}>{copy.common.cancel}</Button>
            <Button type="button" disabled={action !== null} onClick={() => void handleRetry()}>
              {action === 'retry' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
              {copy.generation.confirmRetry}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
