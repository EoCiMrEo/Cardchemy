import api from './api';

export const flashcardService = {
  async getCards(setId: string) {
    const response = await api.get(`/flashcards/sets/${setId}/cards`);
    return response.data;
  },

  async generateCards(formData: FormData) {
    // formData contains: subject_id, set_title, set_description, pdf_file
    const response = await api.post('/flashcards/generate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 60s timeout for AI generation
    });
    return response.data;
  },

  async updateCard(id: string, data: any) {
    const response = await api.put(`/flashcards/${id}`, data);
    return response.data;
  },

  async deleteCard(id: string) {
    const response = await api.delete(`/flashcards/${id}`);
    return response.data;
  },

  async approveAll(setId: string, minConfidence: number = 0.0) {
    const response = await api.post(`/flashcards/sets/${setId}/approve-all`, null, {
      params: { min_confidence: minConfidence }
    });
    return response.data;
  }
};
