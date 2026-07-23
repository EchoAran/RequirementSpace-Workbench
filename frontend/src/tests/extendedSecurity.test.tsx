import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { useWorkspaceStore, getFriendlyErrorMessage } from '../store/useWorkspaceStore';
import { accountApi } from '../lib/accountApi';
import { http } from '../lib/http';
import { workspaceApi } from '../lib/api';
import { AuthGuard } from '../components/auth/AuthGuard';
import { GuestGuard } from '../components/auth/GuestGuard';
import { GlobalToast } from '../App';
import i18n from '@/i18n';

// Mock http client
vi.mock('../lib/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/http')>();
  return {
    ...actual,
    http: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
    request: vi.fn(),
  };
});

// Mock workspaceApi
vi.mock('../lib/api', () => {
  return {
    workspaceApi: {
      healthCheck: vi.fn(),
      list: vi.fn(),
      getById: vi.fn(),
      delete: vi.fn(),
      updateProject: vi.fn(),
      listChoiceGroups: vi.fn(),
    }
  };
});

// Helper component to track and assert current URL route in React Router
function LocationTracker() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

describe('Extended Security & Routing Isolation Matrix', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().clearAuth();
    useWorkspaceStore.setState({
      error: null,
      lastActionMessageToken: null,
      isLoading: false,
      ir: null,
    });
  });

  describe('1. LLM 配置 CRUD 与测试 API Wrapper', () => {
    it('should invoke GET /account/llm-config', async () => {
      vi.mocked(http.get).mockResolvedValueOnce({ configured: true, source: 'personal', api_url: 'http://test', model_name: 'test-model', api_key_last4: '4321' });
      const res = await accountApi.getLLMConfig();
      expect(http.get).toHaveBeenCalledWith('/account/llm-config');
      expect(res.configured).toBe(true);
      expect(res.api_key_last4).toBe('4321');
    });

    it('should invoke PUT /account/llm-config', async () => {
      vi.mocked(http.put).mockResolvedValueOnce({ configured: true, source: 'personal' });
      const payload = { api_url: 'http://test-new', api_key: 'plain-secret-key', model_name: 'new-model' };
      const res = await accountApi.updateLLMConfig(payload);
      expect(http.put).toHaveBeenCalledWith('/account/llm-config', payload);
      expect(res.configured).toBe(true);
    });

    it('should invoke DELETE /account/llm-config', async () => {
      vi.mocked(http.delete).mockResolvedValueOnce({ message: 'Success' });
      const res = await accountApi.deleteLLMConfig();
      expect(http.delete).toHaveBeenCalledWith('/account/llm-config');
      expect(res.message).toBe('Success');
    });

    it('should invoke POST /account/llm-config/test', async () => {
      vi.mocked(http.post).mockResolvedValueOnce({ success: true, error_type: null, error_detail: null });
      const payload = { api_url: 'http://test', api_key: 'test-key', model_name: 'gpt-4' };
      const res = await accountApi.testLLMConfig(payload);
      expect(http.post).toHaveBeenCalledWith('/account/llm-config/test', payload);
      expect(res.success).toBe(true);
    });
  });

  describe('2. llm_config_required 引导提示与重定向', () => {
    it('should render the LLM config warning toast and navigate to settings page on click', async () => {
      useWorkspaceStore.setState({
        error: 'llm_config_required',
      });

      render(
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<GlobalToast />} />
            <Route path="/settings" element={<div>Settings Page</div>} />
          </Routes>
          <LocationTracker />
        </MemoryRouter>
      );

      const friendlyMsg = getFriendlyErrorMessage('llm_config_required');
      const translatedMsg = i18n.t(friendlyMsg);
      expect(screen.queryByText(translatedMsg)).not.toBeNull();
      
      // Ensure '前往设置' indicator/button is rendered
      const button = screen.queryByText('前往设置');
      expect(button).not.toBeNull();

      // Click to trigger navigate('/settings')
      fireEvent.click(screen.getByText(translatedMsg));

      // Assert redirection took place
      expect(screen.getByTestId('location').textContent).toBe('/settings');
      expect(useWorkspaceStore.getState().error).toBeNull();
    });
  });

  describe('3. 路由守卫 (AuthGuard & GuestGuard)', () => {
    describe('AuthGuard', () => {
      it('should display authorization loading session loader when initializing', () => {
        useAuthStore.setState({
          isInitializing: true,
          isAuthenticated: false,
        });

        render(
          <MemoryRouter>
            <AuthGuard>
              <div data-testid="protected-content">Secret Dashboard</div>
            </AuthGuard>
          </MemoryRouter>
        );

        expect(screen.queryByTestId('protected-content')).toBeNull();
        expect(screen.queryByText('正在加载安全会话')).not.toBeNull();
      });

      it('should redirect anonymous users to login page', () => {
        useAuthStore.setState({
          isInitializing: false,
          isAuthenticated: false,
        });

        render(
          <MemoryRouter initialEntries={['/workspace']}>
            <Routes>
              <Route path="/workspace" element={
                <AuthGuard>
                  <div data-testid="protected-content">Secret Dashboard</div>
                </AuthGuard>
              } />
              <Route path="/login" element={<div>Login Page</div>} />
            </Routes>
            <LocationTracker />
          </MemoryRouter>
        );

        expect(screen.queryByTestId('protected-content')).toBeNull();
        expect(screen.getByTestId('location').textContent).toBe('/login');
      });

      it('should render child content when authenticated', () => {
        useAuthStore.setState({
          isInitializing: false,
          isAuthenticated: true,
        });

        render(
          <MemoryRouter>
            <AuthGuard>
              <div data-testid="protected-content">Secret Dashboard</div>
            </AuthGuard>
          </MemoryRouter>
        );

        expect(screen.queryByTestId('protected-content')).not.toBeNull();
        expect(screen.queryByText('正在加载安全会话')).toBeNull();
      });
    });

    describe('GuestGuard', () => {
      it('should display loader when initializing', () => {
        useAuthStore.setState({
          isInitializing: true,
          isAuthenticated: false,
        });

        render(
          <MemoryRouter>
            <GuestGuard>
              <div data-testid="guest-content">Login Interface</div>
            </GuestGuard>
          </MemoryRouter>
        );

        expect(screen.queryByTestId('guest-content')).toBeNull();
        expect(screen.queryByText('正在加载安全会话')).not.toBeNull();
      });

      it('should render children for non-authenticated guests', () => {
        useAuthStore.setState({
          isInitializing: false,
          isAuthenticated: false,
        });

        render(
          <MemoryRouter>
            <GuestGuard>
              <div data-testid="guest-content">Login Interface</div>
            </GuestGuard>
          </MemoryRouter>
        );

        expect(screen.queryByTestId('guest-content')).not.toBeNull();
      });

      it('should redirect authenticated users to /home', () => {
        useAuthStore.setState({
          isInitializing: false,
          isAuthenticated: true,
        });

        render(
          <MemoryRouter initialEntries={['/login']}>
            <Routes>
              <Route path="/login" element={
                <GuestGuard>
                  <div data-testid="guest-content">Login Interface</div>
                </GuestGuard>
              } />
              <Route path="/home" element={<div>Home Portal</div>} />
            </Routes>
            <LocationTracker />
          </MemoryRouter>
        );

        expect(screen.queryByTestId('guest-content')).toBeNull();
        expect(screen.getByTestId('location').textContent).toBe('/home');
      });
    });
  });

  describe('4. CRUD 悬空请求的 sessionVersion 隔离', () => {
    it('should ignore responses from CRUD operations if sessionVersion changes while the request is in-flight', async () => {
      // Setup initial store state
      useWorkspaceStore.setState({
        sessionVersion: 10,
        ir: { projectId: '99', name: 'Original Name' } as any,
        isLoading: false,
      });

      let resolveApi: any;
      const apiPromise = new Promise((resolve) => {
        resolveApi = resolve;
      });

      vi.mocked(workspaceApi.updateProject).mockReturnValueOnce(apiPromise);

      // Trigger the CRUD operation updateProject
      const requestPromise = useWorkspaceStore.getState().updateProject('99', 'Changed Name', 'Description');

      // Assert state becomes loading
      expect(useWorkspaceStore.getState().isLoading).toBe(true);

      // Simulate a logout or workspace switch: increment sessionVersion and wipe IR data
      useWorkspaceStore.setState({
        sessionVersion: 11,
        ir: null,
        isLoading: false,
      });

      // Now resolve the API call
      resolveApi({ name: 'Changed Name', description: 'Description' });

      // Wait for the store's action handler to process the resolution
      await requestPromise;

      // Assert that because sessionVersion mismatched, the store ignored the response.
      // - isLoading should NOT be set to false again by updateProject
      // - ir should remain null (not get populated with stale data or refresh)
      expect(useWorkspaceStore.getState().ir).toBeNull();
      expect(useWorkspaceStore.getState().sessionVersion).toBe(11);
    });
  });
});
