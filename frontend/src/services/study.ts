import api from './api';

export const studyService = {
  async getStudySession(setId: string) {
    const response = await api.get(`/study/sets/${setId}/session`);
    return response.data;
  },

  async updateProgress(data: { flashcard_id: string; is_correct: boolean; quality: number }) {
    const response = await api.post('/study/progress', data);
    return response.data;
  },

  async getSetProgress(setId: string) {
    const response = await api.get(`/study/sets/${setId}/progress`);
    return response.data;
  },

  async syncProgress(updates: any[]) {
    const response = await api.post('/study/sync', updates);
    return response.data;
  }
};
