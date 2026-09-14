import api from './api';
import type {
  SetProgress,
  StudyAnswerRequest,
  StudyAnswerResponse,
  StudySessionResponse,
  StudySyncResponse,
} from './types';

export const studyService = {
  async getStudySession(setId: string, limit: number = 20): Promise<StudySessionResponse> {
    const boundedLimit = Math.min(100, Math.max(1, limit));
    const response = await api.get<StudySessionResponse>(`/study/sets/${setId}/session`, {
      params: { limit: boundedLimit },
    });
    return response.data;
  },

  async updateProgress(data: StudyAnswerRequest): Promise<StudyAnswerResponse> {
    const response = await api.post<StudyAnswerResponse>('/study/progress', data);
    return response.data;
  },

  async getSetProgress(setId: string): Promise<SetProgress> {
    const response = await api.get<SetProgress>(`/study/sets/${setId}/progress`);
    return response.data;
  },

  async syncProgress(updates: StudyAnswerRequest[]): Promise<StudySyncResponse> {
    const response = await api.post<StudySyncResponse>('/study/sync', updates);
    return response.data;
  }
};
