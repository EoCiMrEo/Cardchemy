import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const rawApiUrl = import.meta.env.VITE_API_URL
if (!rawApiUrl) {
  throw new Error('VITE_API_URL is required')
}

let apiBaseUrl: string
try {
  const parsed = new URL(rawApiUrl)
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('unsupported protocol')
  }
  apiBaseUrl = parsed.toString().replace(/\/$/, '')
} catch {
  throw new Error('VITE_API_URL must be an absolute HTTP(S) URL')
}

let accessToken: string | null = null
let refreshPromise: Promise<string> | null = null
let authFailureNotified = false

export const getAccessToken = () => accessToken
export const setAccessToken = (token: string) => {
  accessToken = token
  authFailureNotified = false
}
export const clearAccessToken = () => {
  accessToken = null
}

const publicApi = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = publicApi
      .post<{ access_token: string }>('/auth/refresh')
      .then(({ data }) => {
        setAccessToken(data.access_token)
        return data.access_token
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
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
      try {
        const token = await refreshAccessToken()
        request.headers.Authorization = `Bearer ${token}`
        return api(request)
      } catch {
        clearAccessToken()
        if (!authFailureNotified) {
          authFailureNotified = true
          window.dispatchEvent(new Event('auth:session-ended'))
        }
      }
    }
    return Promise.reject(error)
  },
)

export { publicApi }
export default api
