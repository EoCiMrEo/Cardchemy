import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { normalizeApiBaseUrl } from './apiUrl'
import type { AccessTokenResponse } from './types'

const rawApiUrl = import.meta.env.VITE_API_URL
if (!rawApiUrl) {
  throw new Error('VITE_API_URL is required')
}

let apiBaseUrl: string
try {
  apiBaseUrl = normalizeApiBaseUrl(rawApiUrl)
} catch {
  throw new Error('VITE_API_URL must be an absolute HTTP(S) URL or a root-relative path such as /api')
}

let accessToken: string | null = null
let sessionRevision = 0

interface RefreshAttempt {
  controller: AbortController
  promise: Promise<string>
  sessionRevision: number
}

let activeRefresh: RefreshAttempt | null = null

export const getAccessToken = (): string | null => accessToken

export const setAccessToken = (token: string): void => {
  accessToken = token
  sessionRevision += 1
}

export const clearAccessToken = (): void => {
  accessToken = null
  sessionRevision += 1
}

const publicApi = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

function getOrCreateRefreshAttempt(): RefreshAttempt {
  if (activeRefresh) return activeRefresh

  const refreshRevision = sessionRevision
  const controller = new AbortController()
  const attempt: RefreshAttempt = {
    controller,
    sessionRevision: refreshRevision,
    promise: publicApi
      .post<AccessTokenResponse>('/auth/refresh', undefined, { signal: controller.signal })
      .then(({ data }) => {
        if (sessionRevision !== refreshRevision) {
          if (accessToken) return accessToken
          throw new axios.CanceledError('A newer authentication operation replaced this refresh.')
        }
        setAccessToken(data.access_token)
        return data.access_token
      })
      .finally(() => {
        if (activeRefresh === attempt) activeRefresh = null
      }),
  }
  activeRefresh = attempt
  return attempt
}

export function refreshAccessToken(): Promise<string> {
  return getOrCreateRefreshAttempt().promise
}

export async function supersedeActiveRefresh(): Promise<void> {
  const attempt = activeRefresh
  if (!attempt) return
  attempt.controller.abort()
  try {
    await attempt.promise
  } catch {
    // Cancellation is expected; waiting prevents a stale cookie response from
    // landing after the explicit authentication request that follows.
  }
}

export async function settleActiveRefresh(): Promise<void> {
  const attempt = activeRefresh
  if (!attempt) return
  try {
    await attempt.promise
  } catch {
    // The caller will perform its own explicit authentication operation next.
  }
}

const api = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

type RetryableRequest = InternalAxiosRequestConfig & { _retry?: boolean }

function endSessionOnce(refreshRevision: number): void {
  if (sessionRevision !== refreshRevision) return
  accessToken = null
  sessionRevision += 1
  window.dispatchEvent(new Event('auth:session-ended'))
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetryableRequest | undefined
    const path = request?.url ?? ''
    const isPublicAuthRequest = [
      '/auth/login',
      '/auth/register',
      '/auth/refresh',
      '/auth/password/',
    ].some((endpoint) => path.includes(endpoint))

    if (error.response?.status === 401 && request && !request._retry && !isPublicAuthRequest) {
      request._retry = true
      const currentToken = getAccessToken()
      const sentAuthorization = request.headers.Authorization
      if (currentToken && sentAuthorization !== `Bearer ${currentToken}`) {
        request.headers.Authorization = `Bearer ${currentToken}`
        return api(request)
      }
      const refreshAttempt = getOrCreateRefreshAttempt()
      try {
        const token = await refreshAttempt.promise
        request.headers.Authorization = `Bearer ${token}`
        return api(request)
      } catch (refreshError: unknown) {
        if (!axios.isCancel(refreshError)) endSessionOnce(refreshAttempt.sessionRevision)
      }
    }
    return Promise.reject(error)
  },
)

export { publicApi }
export default api
