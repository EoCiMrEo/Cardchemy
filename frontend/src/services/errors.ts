import axios from 'axios'

type ErrorDetail = { code?: unknown; message?: unknown }

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback
  const detail: unknown = error.response?.data?.detail
  if (typeof detail === 'string' && detail.length <= 500) return detail
  if (detail && typeof detail === 'object') {
    const message = (detail as ErrorDetail).message
    if (typeof message === 'string' && message.length <= 500) return message
  }
  if (error.code === 'ERR_CANCELED') return 'The request was cancelled.'
  return fallback
}
