import api, { publicApi } from './api'
import type {
  AccessTokenResponse,
  ApiMessage,
  LoginRequest,
  StudentRegistration,
  User,
} from './types'

export const authService = {
  async register(data: StudentRegistration): Promise<User> {
    const response = await publicApi.post<User>('/auth/register', data)
    return response.data
  },

  async login(data: LoginRequest): Promise<AccessTokenResponse> {
    const formData = new URLSearchParams()
    formData.append('username', data.email.trim().toLowerCase())
    formData.append('password', data.password)
    const response = await publicApi.post<AccessTokenResponse>('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return response.data
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout')
  },

  async getProfile(): Promise<User> {
    const response = await api.get<User>('/auth/me')
    return response.data
  },

  async forgotPassword(email: string): Promise<ApiMessage> {
    const response = await publicApi.post<ApiMessage>('/auth/password/forgot', { email })
    return response.data
  },

  async resetPassword(token: string, newPassword: string): Promise<ApiMessage> {
    const response = await publicApi.post<ApiMessage>('/auth/password/reset', {
      token,
      new_password: newPassword,
    })
    return response.data
  },
}
