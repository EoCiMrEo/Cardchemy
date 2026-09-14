import api from './api';
import type { InvitationResponse } from './types';

interface JoinCourseResponse {
  message: string;
  subject_name: string;
}

const activeJoinRequests = new Map<string, Promise<JoinCourseResponse>>();

export const subjectService = {
  async getSubjects() {
    const response = await api.get('/subjects');
    return response.data;
  },

  async createSubject(data: { name: string; description?: string }) {
    const response = await api.post('/subjects', data);
    return response.data;
  },

  async getSubject(id: string) {
    const response = await api.get(`/subjects/${id}`);
    return response.data;
  },

  async getSet(id: string) {
    const response = await api.get(`/subjects/sets/${id}`);
    return response.data;
  },

  async getSets(subjectId: string) {
    const response = await api.get(`/subjects/${subjectId}/sets`);
    return response.data;
  },

  async createSet(subjectId: string, data: { title: string; description?: string }) {
    const response = await api.post(`/subjects/${subjectId}/sets`, data);
    return response.data;
  },

  async updateSubject(id: string, data: { name?: string; description?: string }) {
    const response = await api.put(`/subjects/${id}`, data);
    return response.data;
  },

  async deleteSubject(id: string) {
    const response = await api.delete(`/subjects/${id}`);
    return response.data;
  },

  async updateSet(subjectId: string, setId: string, data: { title?: string; description?: string; is_published?: boolean; time_limit?: number | null }) {
    const response = await api.put(`/subjects/${subjectId}/sets/${setId}`, data);
    return response.data;
  },

  async deleteSet(subjectId: string, setId: string) {
    const response = await api.delete(`/subjects/${subjectId}/sets/${setId}`);
    return response.data;
  },

  async generateInvite(subjectId: string, expiresInHours: number): Promise<InvitationResponse> {
    const response = await api.post<InvitationResponse>(`/subjects/${subjectId}/invite`, { expires_in_hours: expiresInHours });
    return response.data;
  },

  joinCourse(token: string): Promise<JoinCourseResponse> {
    const existing = activeJoinRequests.get(token);
    if (existing) return existing;

    const request = api
      .post<JoinCourseResponse>('/subjects/invitations/accept', { token })
      .then((response) => response.data)
      .finally(() => activeJoinRequests.delete(token));
    activeJoinRequests.set(token, request);
    return request;
  }
};
