import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthGuard } from '../components/auth/AuthGuard';
import { GuestGuard } from '../components/auth/GuestGuard';
import { Login } from '../pages/Login';
import { Register } from '../pages/Register';
import { LeftNav } from '../components/layout/LeftNav';
import { TopBar } from '../components/layout/TopBar';
import { useAuthStore } from '../store/useAuthStore';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

// Mock react-i18next specifically for English mode
vi.mock('react-i18next', () => {
  const fs = require('fs');
  const path = require('path');
  const enUS = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../locales/en-US.json'), 'utf8'));

  return {
    initReactI18next: {
      type: '3rdParty',
      init: vi.fn(),
    },
    useTranslation: () => ({
      t: (key: string, options?: any) => {
        const parts = key.split('.');
        let current: any = enUS;
        for (const part of parts) {
          if (current && typeof current === 'object') {
            current = current[part];
          } else {
            current = undefined;
            break;
          }
        }

        if (typeof current === 'string') {
          let val = current;
          if (options) {
            for (const [k, v] of Object.entries(options)) {
              val = val.replace(new RegExp(`{{\\s*${k}\\s*}}`, 'g'), String(v));
            }
          }
          return val;
        }
        return key;
      },
      i18n: {
        changeLanguage: vi.fn().mockResolvedValue(true),
        language: 'en-US',
      },
    }),
  };
});

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: '/home', state: null }),
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
  useParams: () => ({ projectId: 'project-123' }),
}));

// Mock workspace store selectors/helpers
vi.mock('../core/selectors', () => ({
  buildProjectRoute: (id: string, path: string) => `/projects/${id}${path}`,
  buildReadiness: () => ({ overallScore: 75 }),
  extractWorkspacePage: () => '/overview',
}));

// Mock workspaceApi
vi.mock('../lib/api', () => ({
  workspaceApi: {
    listNotifications: vi.fn().mockResolvedValue([]),
    listProjectMembers: vi.fn().mockResolvedValue([]),
  },
}));

describe('Batch 1 Components in English Mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('AuthGuard in English mode', () => {
    it('renders secure session loading spinner in English', () => {
      useAuthStore.setState({
        isInitializing: true,
        isAuthenticated: false,
        user: null,
      });

      render(<AuthGuard><div>Authenticated content</div></AuthGuard>);
      expect(screen.getByText('Loading secure session')).toBeDefined();
      expect(screen.getByText('Validating credentials, keeping your workspace secure...')).toBeDefined();
    });
  });

  describe('GuestGuard in English mode', () => {
    it('renders guest session loading spinner in English', () => {
      useAuthStore.setState({
        isInitializing: true,
        isAuthenticated: false,
        user: null,
      });

      render(<GuestGuard><div>Guest content</div></GuestGuard>);
      expect(screen.getByText('Loading secure session')).toBeDefined();
      expect(screen.getByText('Checking your authentication credentials, please wait...')).toBeDefined();
    });
  });

  describe('Login page in English mode', () => {
    it('renders login title and inputs in English', () => {
      useAuthStore.setState({
        isInitializing: false,
        isAuthenticated: false,
        user: null,
      });

      render(<Login />);
      expect(screen.getByText('Sign in to Requirement Workspace')).toBeDefined();
      expect(screen.getByText('Email Address')).toBeDefined();
      expect(screen.getByText('Password')).toBeDefined();
      expect(screen.getByPlaceholderText('Enter password')).toBeDefined();
      expect(screen.getByText('Enter Workspace')).toBeDefined();
      expect(screen.getByText("Don't have an account?")).toBeDefined();
      expect(screen.getByText('Register Free')).toBeDefined();
    });
  });

  describe('Register page in English mode', () => {
    it('renders register title and inputs in English', () => {
      useAuthStore.setState({
        isInitializing: false,
        isAuthenticated: false,
        user: null,
      });

      render(<Register />);
      expect(screen.getByText('Create your account')).toBeDefined();
      expect(screen.getByText(/at least 8 characters/)).toBeDefined();
      expect(screen.getByText('Confirm Password')).toBeDefined();
      expect(screen.getByPlaceholderText('Enter password again')).toBeDefined();
      expect(screen.getByText('Complete Registration & Sign In')).toBeDefined();
      expect(screen.getByText('Already have an account?')).toBeDefined();
      expect(screen.getByText('Log in now')).toBeDefined();
    });
  });

  describe('LeftNav in English mode', () => {
    it('renders maturity label and project title in English', () => {
      useWorkspaceStore.setState({
        ir: { projectId: 'project-123', projectName: 'Test Project' } as any,
        stageProgress: {
          stages: [
            { stage: 'what', unlocked: true, statusCode: 'ready', statusLabel: '已就绪' },
            { stage: 'how', unlocked: false, statusCode: 'locked', statusLabel: '已锁定' },
          ],
        } as any,
      });

      render(<LeftNav />);
      expect(screen.getByText('Requirement Workspace')).toBeDefined();
      expect(screen.getByText('Overall Maturity')).toBeDefined();
      expect(screen.getAllByText('Ready').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Locked').length).toBeGreaterThan(0);
      expect(screen.getByText('Preview available')).toBeDefined();
      expect(screen.getByText('Please complete all core modeling rules in the What stage first')).toBeDefined();
    });
  });

  describe('TopBar in English mode', () => {
    it('renders titles and priorities in English', () => {
      useAuthStore.setState({
        user: { id: 1, email: 'owner@test.com', preferredLocale: 'en-US' } as any,
      });
      useWorkspaceStore.setState({
        ir: { projectId: 'project-123', projectName: 'Test Project' } as any,
        userTasks: [
          {
            task: { id: 'task-1', title: 'Confirm actor details', priority: 'high', createdAt: '2026-07-13T12:00:00Z' },
            projectSummary: { projectId: 'project-123', projectName: 'Test Project' },
            targetSummary: { nodeKind: 'actor', nodeName: 'User Actor' },
            creatorSummary: { email: 'creator@test.com' },
          },
        ] as any,
      });

      const { container } = render(<TopBar />);
      
      // Open task list popover
      const trigger = screen.getByTitle('Tasks pending my confirmation');
      const { fireEvent: fe } = require('@testing-library/react');
      fe.click(trigger);

      expect(screen.getByTitle('Notifications')).toBeDefined();
      expect(screen.getByText('High')).toBeDefined();
      expect(screen.getByText('Actor')).toBeDefined();
      expect(screen.getByText('By: creator@test.com')).toBeDefined();
    });
  });
});
