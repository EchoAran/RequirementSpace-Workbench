import { http } from './http';

export interface User {
  id: number;
  email: string;
  role: 'admin' | 'user';
  is_active: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  invite_code?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LogoutResponse {
  status: string;
  message: string;
}

export const authApi = {
  register: (data: RegisterRequest) => 
    http.post<User>('/auth/register', data),

  login: (data: LoginRequest) => 
    http.post<User>('/auth/login', data),

  logout: () => 
    http.post<LogoutResponse>('/auth/logout'),

  getMe: () => 
    http.get<User>('/auth/me'),
};
