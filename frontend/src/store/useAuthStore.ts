import { create } from 'zustand';
import { User, RegisterRequest, LoginRequest, authApi } from '../lib/authApi';
import { onUnauthorized } from '../lib/http';
import { useWorkspaceStore } from './useWorkspaceStore';

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  error: string | null;
  
  register: (data: RegisterRequest) => Promise<void>;
  login: (data: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => {
  // Register the 401 interceptor callback
  onUnauthorized(() => {
    get().clearAuth();
  });

  return {
    user: null,
    isAuthenticated: false,
    isInitializing: true,
    error: null,

    register: async (data: RegisterRequest) => {
      set({ error: null });
      try {
        const user = await authApi.register(data);
        set({ user, isAuthenticated: true });
        
        // Load workspaces for the newly registered user
        await useWorkspaceStore.getState().loadWorkspaces();
      } catch (err: any) {
        set({ error: err.message || '注册失败，请检查邀请码或重试。' });
        throw err;
      }
    },

    login: async (data: LoginRequest) => {
      set({ error: null });
      try {
        const user = await authApi.login(data);
        set({ user, isAuthenticated: true });
        
        // Load workspaces for the logged in user
        await useWorkspaceStore.getState().loadWorkspaces();
      } catch (err: any) {
        set({ error: err.message || '登录失败，请检查邮箱或密码。' });
        throw err;
      }
    },

    logout: async () => {
      try {
        await authApi.logout();
      } catch (err) {
        console.error('Logout API call failed:', err);
      } finally {
        get().clearAuth();
      }
    },

    checkAuth: async () => {
      set({ isInitializing: true, error: null });
      try {
        const user = await authApi.getMe();
        set({ user, isAuthenticated: true });
        
        // Load workspaces for the authenticated user
        await useWorkspaceStore.getState().loadWorkspaces();
      } catch (err) {
        // Safe to ignore on initial load if user is not logged in
        set({ user: null, isAuthenticated: false });
      } finally {
        set({ isInitializing: false });
      }
    },

    clearAuth: () => {
      set({
        user: null,
        isAuthenticated: false,
        isInitializing: false,
        error: null,
      });
      
      // Clean workspace states
      const workspaceStore = useWorkspaceStore.getState();
      workspaceStore.exitWorkspace();
      useWorkspaceStore.setState({ workspaces: [] });
    },
  };
});
