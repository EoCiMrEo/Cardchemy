import axios from 'axios';

// Create basic Axios instance
const api = axios.create({
  baseURL: 'http://localhost:8000', // Update this for production
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper to get token (simplistic for now)
export const getToken = () => localStorage.getItem('access_token');
export const setToken = (token: string) => localStorage.setItem('access_token', token);
export const removeToken = () => localStorage.removeItem('access_token');
export const getRefreshToken = () => localStorage.getItem('refresh_token');
export const setRefreshToken = (token: string) => localStorage.setItem('refresh_token', token);
export const removeRefreshToken = () => localStorage.removeItem('refresh_token');

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle token refresh (simplified)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // If 401 and we haven't retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = getRefreshToken();
      
      if (refreshToken) {
        try {
          // Try to refresh
          const response = await axios.post('http://localhost:8000/auth/refresh', null, {
            params: { refresh_token: refreshToken }
          });
          
          const { access_token, refresh_token: new_refresh } = response.data;
          
          setToken(access_token);
          setRefreshToken(new_refresh);
          
          // Retry original request
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed - logout
          removeToken();
          removeRefreshToken();
          window.location.href = '/login';
        }
      } else {
        // No refresh token - logout
        removeToken();
        removeRefreshToken();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
