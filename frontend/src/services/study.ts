import api from './api';
import type {
  SetProgress,
  StudyAnswerRequest,
  StudyAnswerResponse,
  StudySessionMode,
  StudySessionResponse,
} from './types';

export const studyService = {
  async getStudySession(
    setId: string,
    limit: number = 20,
    mode: StudySessionMode = 'due',
  ): Promise<StudySessionResponse> {
    const boundedLimit = Math.min(100, Math.max(1, limit));
    const response = await api.get<StudySessionResponse>(`/study/sets/${setId}/session`, {
      params: { limit: boundedLimit, mode },
    });
    return response.data;
  },

  async updateProgress(
    data: StudyAnswerRequest,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): Promise<StudyAnswerResponse> {
    const response = await api.post<StudyAnswerResponse>('/study/progress', data, {
      headers: { 'Idempotency-Key': idempotencyKey },
      signal,
    });
    return response.data;
  },

  async getSetProgress(setId: string): Promise<SetProgress> {
    const response = await api.get<SetProgress>(`/study/sets/${setId}/progress`);
    return response.data;
  }
};
