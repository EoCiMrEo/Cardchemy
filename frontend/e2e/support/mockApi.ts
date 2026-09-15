import type { Page, Request, Route } from '@playwright/test'

import type {
  Flashcard,
  FlashcardSet,
  SetProgress,
  Subject,
  User,
} from '../../src/services/types'
import { API_ORIGIN } from './constants'

export type MockRole = 'instructor' | 'student'

export interface ApiCall {
  method: string
  path: string
  query: URLSearchParams
  headers: Record<string, string>
  body: unknown
}

export interface MockResponse {
  status?: number
  json?: unknown
  headers?: Record<string, string>
  delayMs?: number
}

export type ApiResolver = (
  call: ApiCall,
  callNumber: number,
) => MockResponse | undefined | Promise<MockResponse | undefined>

interface MockApiOptions {
  auth?: MockRole | 'anonymous'
  resolver?: ApiResolver
}

function userFor(role: MockRole): User {
  return {
    id: `${role}-user-id`,
    email: `${role}@example.com`,
    full_name: role === 'student' ? 'Student Example' : 'Instructor Example',
    role,
    created_at: '2026-09-14T00:00:00Z',
  }
}

function parseBody(request: Request): unknown {
  const raw = request.postData()
  if (!raw) return undefined

  const contentType = request.headers()['content-type'] ?? ''
  if (contentType.includes('application/json')) {
    try {
      return JSON.parse(raw) as unknown
    } catch {
      return raw
    }
  }
  if (contentType.includes('application/x-www-form-urlencoded')) {
    return Object.fromEntries(new URLSearchParams(raw))
  }
  return raw
}

function defaultResponse(call: ApiCall, auth: MockApiOptions['auth']): MockResponse {
  if (call.method === 'POST' && call.path === '/auth/refresh') {
    return auth === 'anonymous'
      ? { status: 401, json: { detail: 'Refresh cookie is missing' } }
      : {
          json: {
            access_token: 'boot-access-token',
            token_type: 'bearer',
            expires_in: 900,
          },
        }
  }
  if (call.method === 'GET' && call.path === '/auth/me' && auth !== 'anonymous') {
    return { json: userFor(auth ?? 'instructor') }
  }
  if (call.method === 'GET' && call.path === '/subjects') return { json: [] }
  return {
    status: 501,
    json: { detail: `No browser-test mock is registered for ${call.method} ${call.path}` },
  }
}

async function fulfill(route: Route, response: MockResponse): Promise<void> {
  if (response.delayMs) {
    await new Promise((resolve) => setTimeout(resolve, response.delayMs))
  }

  try {
    await route.fulfill({
      status: response.status ?? 200,
      contentType: 'application/json',
      headers: response.headers,
      body: JSON.stringify(response.json ?? {}),
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    if (/aborted|canceled|cancelled|closed|already handled/i.test(message)) return
    throw error
  }
}

export interface MockApi {
  readonly calls: ApiCall[]
  count(method: string, path: string): number
  callsFor(method: string, path: string): ApiCall[]
}

export async function installMockApi(
  page: Page,
  { auth = 'instructor', resolver }: MockApiOptions = {},
): Promise<MockApi> {
  const calls: ApiCall[] = []

  await page.route(`${API_ORIGIN}/**`, async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const call: ApiCall = {
      method: request.method(),
      path: url.pathname.replace(/^\/api/, ''),
      query: url.searchParams,
      headers: request.headers(),
      body: parseBody(request),
    }
    calls.push(call)
    const callNumber = calls.filter(
      (candidate) => candidate.method === call.method && candidate.path === call.path,
    ).length
    const response = (await resolver?.(call, callNumber)) ?? defaultResponse(call, auth)
    await fulfill(route, response)
  })

  return {
    calls,
    count(method, path) {
      return calls.filter((call) => call.method === method && call.path === path).length
    },
    callsFor(method, path) {
      return calls.filter((call) => call.method === method && call.path === path)
    },
  }
}

export const fixtures = {
  user: userFor,
  subject: {
    id: 'subject-1',
    name: 'Biology',
    description: 'Cell biology',
    instructor_id: 'instructor-user-id',
    created_at: '2026-09-14T00:00:00Z',
    flashcard_set_count: 1,
    student_count: 1,
  } satisfies Subject,
  set: {
    id: 'set-1',
    subject_id: 'subject-1',
    title: 'Cell structures',
    description: 'Organelles and their roles',
    source_pdf_name: null,
    generation_job_id: null,
    is_published: true,
    time_limit: null,
    created_at: '2026-09-14T00:00:00Z',
    flashcard_count: 2,
    approved_count: 1,
  } satisfies FlashcardSet,
  cards: [
    {
      id: 'card-1',
      set_id: 'set-1',
      front_content: 'Which organelle produces ATP?',
      back_content: 'Mitochondrion',
      options: ['Nucleus', 'Mitochondrion', 'Ribosome', 'Golgi apparatus'],
      card_type: 'multiple_choice',
      quality_score: 0.9,
      is_approved: false,
      source_snippet: null,
      source_page: null,
      source_section: null,
      created_at: '2026-09-14T00:00:00Z',
    },
    {
      id: 'card-2',
      set_id: 'set-1',
      front_content: 'Where is DNA stored?',
      back_content: 'Nucleus',
      options: ['Cell wall', 'Cytoplasm', 'Nucleus', 'Vacuole'],
      card_type: 'multiple_choice',
      quality_score: 0.95,
      is_approved: true,
      source_snippet: null,
      source_page: null,
      source_section: null,
      created_at: '2026-09-14T00:00:00Z',
    },
  ] satisfies Flashcard[],
  progress: {
    total: 4,
    new: 2,
    learning: 1,
    review: 1,
    mastered: 0,
    studied: 2,
    correct_count: 1,
    // Deliberate sentinel values prove the client renders the server fields instead
    // of silently recomputing them from the counters above.
    completion_percentage: 37,
    mastery_percentage: 63,
  } satisfies SetProgress,
}
