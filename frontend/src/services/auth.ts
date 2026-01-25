import api from './api';

export const authService = {
  async register(data: any) {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  async login(data: any) {
    // data = { email, password }
    // API expects form data for OAuth2 spec
    const formData = new URLSearchParams();
    formData.append('username', data.email);
    formData.append('password', data.password);
    
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return response.data;
  },

  async getProfile() {
    const response = await api.get('/auth/me');
    return response.data;
  },
  
  async acceptInvite(code: string, data: any) {
    const response = await api.post(`/auth/invite/accept/${code}`, data);
    return response.data;
  }
};
