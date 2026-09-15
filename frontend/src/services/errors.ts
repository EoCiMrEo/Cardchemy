import axios from 'axios'

import { copy } from '@/i18n/en'

const MAX_MESSAGE_LENGTH = 500
const MAX_VALIDATION_ISSUES = 5
const MAX_LOCATION_PARTS = 4

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function boundedText(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim()
  if (!normalized) return null
  if (normalized.length <= MAX_MESSAGE_LENGTH) return normalized
  return `${normalized.slice(0, MAX_MESSAGE_LENGTH - 1)}…`
}

function validationLocation(value: unknown): string | null {
  if (!Array.isArray(value)) return null
  const parts = value
    .filter((part): part is string | number => typeof part === 'string' || typeof part === 'number')
    .slice(-MAX_LOCATION_PARTS)
    .map(String)
  return parts.length > 0 ? parts.join('.') : null
}

function validationArrayMessage(detail: unknown[]): string | null {
  const messages: string[] = []
  for (const issue of detail.slice(0, MAX_VALIDATION_ISSUES)) {
    if (!isRecord(issue)) continue
    const message = boundedText(issue.msg ?? issue.message)
    if (!message) continue
    const location = validationLocation(issue.loc)
    messages.push(location ? `${location}: ${message}` : message)
  }
  return boundedText(messages.join('; '))
}

function detailMessage(detail: unknown): string | null {
  const direct = boundedText(detail)
  if (direct) return direct
  if (Array.isArray(detail)) return validationArrayMessage(detail)
  if (!isRecord(detail)) return null
  return boundedText(detail.message ?? detail.detail)
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  const safeFallback = boundedText(fallback) ?? copy.common.unexpectedError
  if (!axios.isAxiosError(error)) return safeFallback
  if (error.code === 'ERR_CANCELED') return copy.common.requestCancelled

  const responseData: unknown = error.response?.data
  if (!isRecord(responseData)) return safeFallback
  return detailMessage(responseData.detail) ?? boundedText(responseData.message) ?? safeFallback
}
