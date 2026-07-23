import { http } from './http';

export interface User {
  id: number;
  email: string;
  role: 'admin' | 'user';
  is_active: boolean;
  preferred_locale?: 'zh-CN' | 'en-US';
  preferredLocale?: 'zh-CN' | 'en-US';
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
  register: async (data: RegisterRequest) => {
    const user = await http.post<User>('/auth/register', data);
    if (user) {
      user.preferredLocale = user.preferred_locale;
    }
    return user;
  },

  login: async (data: LoginRequest) => {
    const user = await http.post<User>('/auth/login', data);
    if (user) {
      user.preferredLocale = user.preferred_locale;
    }
    return user;
  },

  logout: () => 
    http.post<LogoutResponse>('/auth/logout'),

  getMe: async () => {
    const user = await http.get<User>('/auth/me');
    if (user) {
      user.preferredLocale = user.preferred_locale;
    }
    return user;
  },

  updatePreferences: async (data: { preferred_locale: 'zh-CN' | 'en-US' }) => {
    const res = await http.put<{ preferred_locale: 'zh-CN' | 'en-US' }>('/account/preferences', data);
    return {
      preferred_locale: res.preferred_locale,
      preferredLocale: res.preferred_locale,
    };
  },
};
