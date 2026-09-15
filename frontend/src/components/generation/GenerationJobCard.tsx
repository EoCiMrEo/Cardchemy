import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, RefreshCw, Square, UploadCloud } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { apiErrorMessage } from '@/services/errors'
import type { GenerationJob } from '@/services/types'
import { copy } from '@/i18n/en'

interface GenerationJobCardProps {
  job: GenerationJob
  onCancel: (jobId: string) => Promise<void>
  onRetry: (jobId: string, idempotencyKey: string) => Promise<void>
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

export function GenerationJobCard({ job, onCancel, onRetry }: GenerationJobCardProps) {
  const [action, setAction] = useState<'cancel' | 'retry' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const retryKeyRef = useRef<string | null>(null)

  const handleCancel = async () => {
    setAction('cancel')
    setActionError(null)
    try {
      await onCancel(job.id)
    } catch (error) {
      setActionError(apiErrorMessage(error, copy.generation.cancellationFailed))
    } finally {
      setAction(null)
    }
  }

  const handleRetry = async () => {
    setAction('retry')
    setActionError(null)
    try {
      retryKeyRef.current ??= crypto.randomUUID()
      await onRetry(job.id, retryKeyRef.current)
      retryKeyRef.current = null
    } catch (error) {
      setActionError(apiErrorMessage(error, copy.generation.retryFailed))
    } finally {
      setAction(null)
    }
  }

  const isActive = ['awaiting_upload', 'queued', 'running'].includes(job.status)

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
        {job.error_message ? (
          <p className="rounded bg-red-50 p-2 text-sm text-red-700" role="alert">
            {job.error_message}
          </p>
        ) : null}
        {job.limit_reason_message && job.limit_reason_message !== job.error_message ? (
          <p className="rounded bg-amber-50 p-2 text-sm text-amber-800" role="status">
            {job.limit_reason_message}
          </p>
        ) : null}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-700">
          <div>
            <dt className="font-medium">{copy.generation.provider}</dt>
            <dd>{job.ai_provider} / {job.ai_model}</dd>
          </div>
          <div>
            <dt className="font-medium">{copy.generation.validatedCards}</dt>
            <dd>{copy.generation.validationCounts(job.accepted_card_count, job.rejected_card_count)}</dd>
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
              onClick={() => void handleRetry()}
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
    </Card>
  )
}
