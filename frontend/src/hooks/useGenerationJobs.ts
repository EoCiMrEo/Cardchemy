import { useCallback, useEffect, useRef, useState } from 'react'

import { apiErrorMessage } from '@/services/errors'
import { flashcardService } from '@/services/flashcards'
import type { GenerationJob, GenerationLimits } from '@/services/types'
import { copy } from '@/i18n/en'

const ACTIVE_STATUSES = new Set(['awaiting_upload', 'queued', 'running'])

function retryDelay(error: unknown, failures: number): number {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { headers?: Record<string, string> } }).response
    const retryAfter = Number(response?.headers?.['retry-after'])
    if (Number.isFinite(retryAfter) && retryAfter > 0) return Math.min(retryAfter * 1000, 30_000)
  }
  return Math.min(1_500 * 2 ** failures, 15_000)
}

export function useGenerationJobs(subjectId: string | null, onCompleted: () => void) {
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [limits, setLimits] = useState<GenerationLimits | null>(null)
  const [loading, setLoading] = useState(Boolean(subjectId))
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [wakeVersion, setWakeVersion] = useState(0)
  const onCompletedRef = useRef(onCompleted)
  const previousStatuses = useRef(new Map<string, string>())

  useEffect(() => {
    onCompletedRef.current = onCompleted
  }, [onCompleted])

  const applyJobs = useCallback((nextJobs: GenerationJob[], notify: boolean) => {
    if (notify) {
      for (const job of nextJobs) {
        const previous = previousStatuses.current.get(job.id)
        if (job.status === 'completed' && previous && previous !== 'completed') {
          onCompletedRef.current()
        }
      }
    }
    previousStatuses.current = new Map(nextJobs.map((job) => [job.id, job.status]))
    setJobs(nextJobs)
  }, [])

  useEffect(() => {
    if (!subjectId) {
      setJobs([])
      setLimits(null)
      setLoading(false)
      return
    }

    let disposed = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    let limitsLoaded = false
    const controller = new AbortController()

    const poll = async (initial: boolean) => {
      try {
        const shouldLoadLimits = initial || !limitsLoaded
        const [nextJobs, nextLimits] = await Promise.all([
          flashcardService.listGenerationJobs(subjectId, controller.signal),
          shouldLoadLimits
            ? flashcardService.getGenerationLimits(controller.signal)
            : Promise.resolve(null),
        ])
        if (disposed) return
        applyJobs(nextJobs, !initial)
        if (nextLimits) {
          setLimits(nextLimits)
          limitsLoaded = true
        }
        setStatusMessage(null)
        setLoading(false)
        failures = 0
        if (nextJobs.some((job) => ACTIVE_STATUSES.has(job.status))) {
          timer = setTimeout(() => void poll(false), 1_500)
        }
      } catch (error) {
        if (disposed || controller.signal.aborted) return
        setLoading(false)
        setStatusMessage(
          apiErrorMessage(error, copy.generation.statusUnavailable),
        )
        timer = setTimeout(() => void poll(false), retryDelay(error, failures++))
      }
    }

    void poll(true)
    return () => {
      disposed = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [applyJobs, subjectId, wakeVersion])

  const trackJob = useCallback((job: GenerationJob) => {
    setJobs((current) => {
      const withoutJob = current.filter((item) => item.id !== job.id)
      return [job, ...withoutJob]
    })
    previousStatuses.current.set(job.id, job.status)
    setWakeVersion((version) => version + 1)
  }, [])

  const cancelJob = useCallback(async (jobId: string) => {
    const job = await flashcardService.cancelGenerationJob(jobId)
    trackJob(job)
  }, [trackJob])

  const retryJob = useCallback(async (jobId: string, idempotencyKey: string) => {
    const job = await flashcardService.retryGenerationJob(jobId, idempotencyKey)
    trackJob(job)
  }, [trackJob])

  const refreshJobs = useCallback(() => {
    setWakeVersion((version) => version + 1)
  }, [])

  return {
    jobs,
    limits,
    loading,
    statusMessage,
    trackJob,
    cancelJob,
    retryJob,
    refreshJobs,
  }
}
