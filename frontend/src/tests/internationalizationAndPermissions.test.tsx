import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AccountSettings } from '@/pages/AccountSettings';
import { ProjectConfiguration } from '@/pages/ProjectConfiguration';
import { useAuthStore } from '@/store/useAuthStore';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { authApi } from '@/lib/authApi';
import { workspaceApi } from '@/lib/api';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: vi.fn(),
  },
  useTranslation: () => ({
    t: (key: string, options?: any) => {
      if (key === 'projectConfig.contentLanguage.saveBtn') {
        return '保存语言设置';
      }
      if (options?.projectName) {
        return `${key}_${options.projectName}`;
      }
      return key;
    },
    i18n: {
      changeLanguage: vi.fn().mockResolvedValue(true),
      language: 'zh-CN',
    },
  }),
}));

// Mock API modules
vi.mock('@/lib/authApi', () => ({
  authApi: {
    updatePreferences: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('@/lib/accountApi', () => ({
  accountApi: {
    getLLMConfig: vi.fn().mockResolvedValue({ configured: false, source: 'system' }),
  },
}));

vi.mock('@/lib/api', () => ({
  workspaceApi: {
    listProjectMembers: vi.fn(),
    updateProjectConfiguration: vi.fn(),
    getProjectConfiguration: vi.fn().mockResolvedValue({
      content_locale: null,
      contentLocale: null,
      generation_strategy: {
        enabled: true,
        candidate_count: 2,
        strategies: [],
      },
      knowledge: {
        enabled: true,
      },
    }),
    getProjectLLMConfig: vi.fn().mockResolvedValue({}),
    listNotifications: vi.fn().mockResolvedValue([]),
  },
}));

// Mock React Router DOM
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useParams: () => ({ projectId: 'project-123' }),
  useSearchParams: () => [new URLSearchParams('tab=ai-strategies'), vi.fn()],
}));

describe('Phase 3 - Internationalization and Permissions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Default auth store state
    useAuthStore.setState({
      user: {
        id: 1,
        email: 'user@test.com',
        role: 'admin',
        preferredLocale: 'zh-CN',
        preferred_locale: 'zh-CN',
      } as any,
      isAuthenticated: true,
      isInitializing: false,
    });

    // Default workspace store state
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123', projectName: 'Test Project' } as any,
      projectConfiguration: {
        contentLocale: null,
        content_locale: null,
        generation_strategy: {
          enabled: true,
          candidate_count: 2,
          strategies: [],
        },
        knowledge: {
          enabled: true,
        },
      },
      updateProjectConfiguration: vi.fn().mockResolvedValue({}),
    });
  });

  describe('AccountSettings - Interface Language Selection', () => {
    it('renders the interface language select and calls authApi.updatePreferences on change', async () => {
      render(<AccountSettings />);

      // Find the select element
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect(select).toBeDefined();
      expect(select.value).toBe('zh-CN');

      // Change value to en-US
      fireEvent.change(select, { target: { value: 'en-US' } });

      await waitFor(() => {
        expect(authApi.updatePreferences).toHaveBeenCalledWith({ preferred_locale: 'en-US' });
      });
    });
  });

  describe('ProjectConfiguration - Project Content Language Permissions', () => {
    it('enables language select and button for owners/admins', async () => {
      // Mock user role in listProjectMembers to owner
      vi.mocked(workspaceApi.listProjectMembers).mockResolvedValue([
        { userId: 1, role: 'owner', joinedAt: '', status: 'active', email: '' } as any,
      ]);

      render(<ProjectConfiguration />);

      // Wait for role check
      await waitFor(() => {
        expect(workspaceApi.listProjectMembers).toHaveBeenCalledWith('project-123');
      });

      // Find select and save button
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      const saveButton = screen.getByRole('button', { name: /保存语言设置/ }) as HTMLButtonElement;

      expect(select.disabled).toBe(false);
      expect(saveButton.disabled).toBe(false);

      // Change selection and click save
      fireEvent.change(select, { target: { value: 'zh-CN' } });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(useWorkspaceStore.getState().updateProjectConfiguration).toHaveBeenCalledWith(
          'project-123',
          { content_locale: 'zh-CN' }
        );
      });
    });

    it('disables language select for non-admin members and displays warning', async () => {
      // Mock user role to editor (non-admin/non-owner)
      vi.mocked(workspaceApi.listProjectMembers).mockResolvedValue([
        { userId: 1, role: 'editor', joinedAt: '', status: 'active', email: '' } as any,
      ]);

      render(<ProjectConfiguration />);

      await waitFor(() => {
        expect(workspaceApi.listProjectMembers).toHaveBeenCalledWith('project-123');
      });

      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect(select.disabled).toBe(true);

      // Warning text should be visible
      expect(screen.getByText('projectConfig.contentLanguage.permissionWarning')).toBeDefined();
    });
  });
});
