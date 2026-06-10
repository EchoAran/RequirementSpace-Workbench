import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuthStore } from '../store/useAuthStore';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { authApi, User } from '../lib/authApi';

// Mock authApi
vi.mock('../lib/authApi', () => ({
  authApi: {
    register: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    getMe: vi.fn(),
  }
}));

// Mock loadWorkspaces on useWorkspaceStore
const mockLoadWorkspaces = vi.fn().mockResolvedValue(undefined);
useWorkspaceStore.getState().loadWorkspaces = mockLoadWorkspaces;

describe('useAuthStore - Authentication & Workspace Isolation Matrix', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().clearAuth();
  });

  it('1. 登录 (Login) - Verifies successful login and workspace reload', async () => {
    const mockUser: User = { id: 1, email: 'test@example.com', role: 'user', is_active: true };
    vi.mocked(authApi.login).mockResolvedValueOnce(mockUser);

    await useAuthStore.getState().login({ email: 'test@example.com', password: 'password123' });

    expect(authApi.login).toHaveBeenCalledWith({ email: 'test@example.com', password: 'password123' });
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(mockLoadWorkspaces).toHaveBeenCalled();
  });

  it('2. 注册 (Register) - Verifies registration triggers login state and workspace load', async () => {
    const mockUser: User = { id: 2, email: 'admin@example.com', role: 'admin', is_active: true };
    vi.mocked(authApi.register).mockResolvedValueOnce(mockUser);

    await useAuthStore.getState().register({
      email: 'admin@example.com',
      password: 'password123',
      invite_code: 'admin_code'
    });

    expect(authApi.register).toHaveBeenCalledWith({
      email: 'admin@example.com',
      password: 'password123',
      invite_code: 'admin_code'
    });
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(mockLoadWorkspaces).toHaveBeenCalled();
  });

  it('3. 刷新恢复 (Refresh Recovery / checkAuth) - Restores profile on success, handles failure', async () => {
    const mockUser: User = { id: 3, email: 'recover@example.com', role: 'user', is_active: true };
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockUser);

    await useAuthStore.getState().checkAuth();

    expect(authApi.getMe).toHaveBeenCalled();
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(mockLoadWorkspaces).toHaveBeenCalled();

    // Reset and test failure case
    useAuthStore.getState().clearAuth();
    vi.mocked(authApi.getMe).mockRejectedValueOnce(new Error('Unauthorized'));

    await useAuthStore.getState().checkAuth();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('4. Session 过期 (Session Expiration) - Verifies 401 callback purges auth and cleans workspace', async () => {
    // Set initial logged in state
    const mockUser: User = { id: 4, email: 'session@example.com', role: 'user', is_active: true };
    useAuthStore.setState({
      user: mockUser,
      isAuthenticated: true
    });
    useWorkspaceStore.setState({
      workspaces: [{ id: '1', name: 'Workspace 1', idea: 'Test Idea', updatedAt: '2026-06-09', status: 'active', issueCount: 0, nodeCount: 0 }]
    });

    // Simulate 401 response trigger by importing and triggering callback
    const { request } = await import('../lib/http');
    
    // We mock fetch to return 401
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'unauthorized_token' })
    } as any);

    await expect(request('/some-protected-endpoint')).rejects.toThrow();

    // Verify auth state is cleared upon 401 interception
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
    expect(useWorkspaceStore.getState().workspaces).toEqual([]);
  });

  it('5. 账户切换隔离 (Account Switching Isolation) - Verifies complete workspace cleanup on logout', async () => {
    // 1. Populate workspace state with user A data
    useWorkspaceStore.setState({
      isGenerating: true,
      isGeneratingChoices: true,
      pendingGenerationConflict: { type: 'actor', local: {}, remote: {} } as any,
      activeChoiceGroup: { id: 'group_1', candidates: [] } as any,
      ir: { project: { id: 1, name: 'Project A' } } as any,
      workspaces: [{ id: '10', name: 'Workspace A', idea: 'Idea A', updatedAt: '2026-06-09', status: 'active', issueCount: 0, nodeCount: 0 }]
    });

    // 2. Perform logout (simulating switching account or session cleanup)
    vi.mocked(authApi.logout).mockResolvedValueOnce(undefined);
    await useAuthStore.getState().logout();

    // 3. Verify that all workspace states and lists are wiped out cleanly to protect data isolation
    const workspaceState = useWorkspaceStore.getState();
    expect(workspaceState.isGenerating).toBe(false);
    expect(workspaceState.isGeneratingChoices).toBe(false);
    expect(workspaceState.pendingGenerationConflict).toBeNull();
    expect(workspaceState.activeChoiceGroup).toBeNull();
    expect(workspaceState.ir).toBeNull();
    expect(workspaceState.workspaces).toEqual([]);
  });
});
