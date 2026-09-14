export type UserRole = 'instructor' | 'student'

export interface User {
  id: string
  email: string
  role: UserRole
  full_name?: string | null
  created_at: string
}

export interface AccessTokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface StudentRegistration {
  email: string
  password: string
  full_name?: string
  invite_token: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface ApiMessage {
  message: string
}

export interface InvitationResponse {
  token: string
  subject_id: string
  expires_at: string
}
