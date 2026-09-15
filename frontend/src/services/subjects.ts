import api from './api'
import { CanceledError } from 'axios'
import type {
  FlashcardSet,
  FlashcardSetCreate,
  FlashcardSetUpdate,
  InvitationResponse,
  InvitationAccept,
  InvitationCreate,
  JoinCourseResponse,
  Subject,
  SubjectCreate,
  SubjectUpdate,
} from './types'

interface ActiveJoinRequest {
  controller: AbortController
  promise: Promise<JoinCourseResponse>
  subscribers: Set<symbol>
  pendingAbort: ReturnType<typeof setTimeout> | null
}

const activeJoinRequests = new Map<string, ActiveJoinRequest>()

function abortError(): CanceledError<unknown> {
  return new CanceledError('The join request was cancelled.')
}

function scheduleUnusedRequestAbort(token: string, request: ActiveJoinRequest): void {
  if (request.pendingAbort || request.subscribers.size > 0) return
  request.pendingAbort = setTimeout(() => {
    request.pendingAbort = null
    if (request.subscribers.size === 0 && activeJoinRequests.get(token) === request) {
      request.controller.abort()
    }
  }, 0)
}

function subscribeToJoinRequest(
  token: string,
  request: ActiveJoinRequest,
  signal: AbortSignal,
): Promise<JoinCourseResponse> {
  if (signal.aborted) {
    scheduleUnusedRequestAbort(token, request)
    return Promise.reject(abortError())
  }

  if (request.pendingAbort) {
    clearTimeout(request.pendingAbort)
    request.pendingAbort = null
  }

  const subscriber = Symbol(token)
  request.subscribers.add(subscriber)

  return new Promise<JoinCourseResponse>((resolve, reject) => {
    let settled = false

    const release = () => {
      signal.removeEventListener('abort', handleAbort)
      request.subscribers.delete(subscriber)
      scheduleUnusedRequestAbort(token, request)
    }

    const handleAbort = () => {
      if (settled) return
      settled = true
      release()
      reject(abortError())
    }

    signal.addEventListener('abort', handleAbort, { once: true })
    void request.promise.then(
      (result) => {
        if (settled) return
        settled = true
        release()
        resolve(result)
      },
      (error: unknown) => {
        if (settled) return
        settled = true
        release()
        reject(error)
      },
    )
  })
}

function subscribeWithoutAbort(token: string, request: ActiveJoinRequest): Promise<JoinCourseResponse> {
  if (request.pendingAbort) {
    clearTimeout(request.pendingAbort)
    request.pendingAbort = null
  }
  const subscriber = Symbol(token)
  request.subscribers.add(subscriber)
  return request.promise.finally(() => {
    request.subscribers.delete(subscriber)
  })
}

function getOrCreateJoinRequest(token: string): ActiveJoinRequest {
  const existing = activeJoinRequests.get(token)
  if (existing) return existing

  const controller = new AbortController()
  const body: InvitationAccept = { token }
  const request: ActiveJoinRequest = {
    controller,
    subscribers: new Set(),
    pendingAbort: null,
    promise: api
      .post<JoinCourseResponse>('/subjects/invitations/accept', body, { signal: controller.signal })
      .then((response) => response.data)
      .finally(() => {
        if (request.pendingAbort) clearTimeout(request.pendingAbort)
        if (activeJoinRequests.get(token) === request) activeJoinRequests.delete(token)
      }),
  }
  activeJoinRequests.set(token, request)
  return request
}

export const subjectService = {
  async getSubjects(signal?: AbortSignal): Promise<Subject[]> {
    const response = await api.get<Subject[]>('/subjects', { signal })
    return response.data
  },

  async createSubject(data: SubjectCreate): Promise<Subject> {
    const response = await api.post<Subject>('/subjects', data)
    return response.data
  },

  async getSubject(id: string, signal?: AbortSignal): Promise<Subject> {
    const response = await api.get<Subject>(`/subjects/${id}`, { signal })
    return response.data
  },

  async getSet(id: string, signal?: AbortSignal): Promise<FlashcardSet> {
    const response = await api.get<FlashcardSet>(`/subjects/sets/${id}`, { signal })
    return response.data
  },

  async getSets(subjectId: string, signal?: AbortSignal): Promise<FlashcardSet[]> {
    const response = await api.get<FlashcardSet[]>(`/subjects/${subjectId}/sets`, { signal })
    return response.data
  },

  async createSet(
    subjectId: string,
    data: FlashcardSetCreate,
  ): Promise<FlashcardSet> {
    const response = await api.post<FlashcardSet>(`/subjects/${subjectId}/sets`, data)
    return response.data
  },

  async updateSubject(id: string, data: SubjectUpdate): Promise<Subject> {
    const response = await api.put<Subject>(`/subjects/${id}`, data)
    return response.data
  },

  async deleteSubject(id: string): Promise<void> {
    await api.delete<void>(`/subjects/${id}`)
  },

  async updateSet(
    subjectId: string,
    setId: string,
    data: FlashcardSetUpdate,
  ): Promise<FlashcardSet> {
    const response = await api.put<FlashcardSet>(`/subjects/${subjectId}/sets/${setId}`, data)
    return response.data
  },

  async deleteSet(subjectId: string, setId: string): Promise<void> {
    await api.delete<void>(`/subjects/${subjectId}/sets/${setId}`)
  },

  async generateInvite(subjectId: string, expiresInHours: number): Promise<InvitationResponse> {
    const request: InvitationCreate = {
      expires_in_hours: expiresInHours,
    }
    const response = await api.post<InvitationResponse>(`/subjects/${subjectId}/invite`, request)
    return response.data
  },

  joinCourse(token: string, signal?: AbortSignal): Promise<JoinCourseResponse> {
    const normalizedToken = token.trim()
    if (signal?.aborted) return Promise.reject(abortError())
    const request = getOrCreateJoinRequest(normalizedToken)
    return signal
      ? subscribeToJoinRequest(normalizedToken, request, signal)
      : subscribeWithoutAbort(normalizedToken, request)
  },
}
