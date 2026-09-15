import api, { publicApi, settleActiveRefresh, supersedeActiveRefresh } from './api'
import type {
  AccessTokenResponse,
  ApiMessage,
  LoginRequest,
  PasswordForgotRequest,
  PasswordResetRequest,
  StudentRegistration,
  User,
} from './types'

export const authService = {
  async register(data: StudentRegistration): Promise<User> {
    await supersedeActiveRefresh()
    const response = await publicApi.post<User>('/auth/register', data)
    return response.data
  },

  async login(data: LoginRequest): Promise<AccessTokenResponse> {
    await supersedeActiveRefresh()
    const formData = new URLSearchParams()
    formData.append('username', data.email.trim().toLowerCase())
    formData.append('password', data.password)
    const response = await publicApi.post<AccessTokenResponse>('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return response.data
  },

  async logout(): Promise<void> {
    await settleActiveRefresh()
    await api.post<ApiMessage>('/auth/logout')
  },

  async getProfile(): Promise<User> {
    const response = await api.get<User>('/auth/me')
    return response.data
  },

  async forgotPassword(email: string): Promise<ApiMessage> {
    const request: PasswordForgotRequest = { email }
    const response = await publicApi.post<ApiMessage>('/auth/password/forgot', request)
    return response.data
  },

  async resetPassword(token: string, newPassword: string): Promise<ApiMessage> {
    const request: PasswordResetRequest = {
      token,
      new_password: newPassword,
    }
    const response = await publicApi.post<ApiMessage>('/auth/password/reset', request)
    return response.data
  },
}
