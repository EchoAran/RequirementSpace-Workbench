import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Overview } from '../pages/Overview';

function LocaleSetter({ locale }: { locale: string }) {
  const { i18n } = useTranslation();
  return <button onClick={() => void i18n.changeLanguage(locale)}>set-locale</button>;
}

function setTestLocale(locale: string) {
  render(<LocaleSetter locale={locale} />);
  fireEvent.click(screen.getByText('set-locale'));
  cleanup();
}

// Mock sub-components rendered by Overview to avoid deep selector dependency issues
vi.mock('../components/shared/RightObjectPanel', () => ({
  RightObjectPanel: () => <div data-testid="right-object-panel" />
}));

vi.mock('../components/shared/ChoiceGroupPreviewModal', () => ({
  ChoiceGroupPreviewModal: () => <div data-testid="choice-group-preview-modal" />
}));

vi.mock('../components/shared/StaleChoiceDialog', () => ({
  StaleChoiceDialog: () => <div data-testid="stale-choice-dialog" />
}));

vi.mock('../components/collaboration/ConfirmationWorkspace', () => ({
  ConfirmationWorkspace: () => <div data-testid="confirmation-workspace" />
}));

// Mock workspace store or select hooks used by Overview.tsx
// Let's see what hooks Overview.tsx uses:
// useWorkspaceStore is a zustand store. Let's mock the whole store hook.
vi.mock('../store/useWorkspaceStore', () => {
  const mockState = {
    ir: {
      projectId: 'proj_123',
      projectName: 'Test Requirement Space',
      actors: [],
      features: [],
      flows: [],
      businessObjects: [],
      findings: [],
    },
    auditLogs: [
      {
        id: '1',
        timestamp: '2026-06-27T03:00:00.000Z',
        actionType: 'update_user_requirements',
        summary: '手动更新用户需求文档',
        targetIds: ['1'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '2',
        timestamp: '2026-06-27T03:05:00.000Z',
        actionType: 'refine_user_requirements',
        summary: '通过LLM精炼优化用户需求文档',
        targetIds: ['1'],
        actorUserId: 1,
        actorType: 'ai',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '3',
        timestamp: '2026-06-27T03:10:00.000Z',
        actionType: 'create_actor',
        summary: '添加主要参与者',
        targetIds: ['2'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '4',
        timestamp: '2026-06-27T03:15:00.000Z',
        actionType: 'create_feature',
        summary: '新增功能节点',
        targetIds: ['3'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '5',
        timestamp: '2026-06-27T03:20:00.000Z',
        actionType: 'update_scope',
        summary: '更新范围决策',
        targetIds: ['4'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '6',
        timestamp: '2026-06-27T03:25:00.000Z',
        actionType: 'create_flow',
        summary: '新增业务流',
        targetIds: ['5'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '7',
        timestamp: '2026-06-27T03:30:00.000Z',
        actionType: 'update_flow_step',
        summary: '调整流程步骤描述',
        targetIds: ['6'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '8',
        timestamp: '2026-06-27T03:35:00.000Z',
        actionType: 'create_actor',
        summary: '新增候选参与者',
        targetIds: ['7'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '9',
        timestamp: '2026-06-27T03:40:00.000Z',
        actionType: 'update_confirmation_status',
        summary: '确认参与者状态',
        targetIds: ['8'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '10',
        timestamp: '2026-06-27T03:45:00.000Z',
        actionType: 'task_created',
        summary: '创建确认任务: 请确认参与者',
        targetIds: ['9'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '11',
        timestamp: '2026-06-27T03:50:00.000Z',
        actionType: 'task_approved',
        summary: '确认任务已通过: 请确认参与者',
        targetIds: ['10'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '12',
        timestamp: '2026-06-27T03:55:00.000Z',
        actionType: 'generation_choice_group_created',
        summary: '创建 actor 候选组 (3/3)',
        targetIds: ['11'],
        actorUserId: 1,
        actorType: 'ai',
        actorEmail: 'user@perm.test',
        diff: {},
      },
      {
        id: '13',
        timestamp: '2026-06-27T04:00:00.000Z',
        actionType: 'generation_choice_accepted',
        summary: '接受 actor 候选: 主要用户',
        targetIds: ['12'],
        actorUserId: 1,
        actorType: 'user',
        actorEmail: 'user@perm.test',
        diff: {},
      },
    ],
    choiceGroups: [],
    isGeneratingChoices: false,
    choiceGroupGenerationProgress: 0,
    activeChoiceGroup: null,
    activeStaleChoice: null,
    isDiagnosing: false,
    findings: [],
    loadAuditLogs: vi.fn(),
    acceptChoice: vi.fn(),
    discardChoiceGroup: vi.fn(),
    clearStaleChoice: vi.fn(),
  };

  const useStore = (selector: any) => {
    if (typeof selector !== 'function') return mockState;
    return selector(mockState);
  };
  Object.assign(useStore, {
    getState: () => mockState,
    subscribe: vi.fn(),
  });
  return {
    useWorkspaceStore: useStore,
    selectChoices: () => [],
    default: useStore,
  };
});

describe('Audit Log Display rendering on Overview Page', () => {
  beforeEach(() => {
    setTestLocale('zh-CN');
  });

  it('renders recent audit logs with correct details including user email and AI badge', () => {
    render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    );

    // Check headings
    expect(screen.getByText('最近变更记录')).toBeDefined();

    // Check first audit operation (user)
    expect(screen.getAllByText('更新用户需求').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('手动更新用户需求文档')).toBeDefined();
    expect(screen.getAllByText('user@perm.test').length).toBe(13);

    // Check second audit operation (ai)
    expect(screen.getAllByText('AI 精炼用户需求').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('通过LLM精炼优化用户需求文档')).toBeDefined();
    expect(screen.getAllByText('更新确认状态').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('确认参与者状态')).toBeDefined();
    expect(screen.getAllByText('创建任务').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('创建确认任务: 请确认参与者')).toBeDefined();
    expect(screen.getAllByText('审批通过').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('确认任务已通过: 请确认参与者')).toBeDefined();
    expect(screen.getAllByText('生成候选方案组').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('创建 actor 候选组 (3/3)')).toBeDefined();
    expect(screen.getAllByText('采纳生成候选方案').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('接受 actor 候选: 主要用户')).toBeDefined();
    expect(screen.getAllByText('更新流程步骤').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('调整流程步骤描述')).toBeDefined();
    expect(screen.getByText('新增候选参与者')).toBeDefined();

    // The AI badge should render "AI" text
    const aiBadges = screen.getAllByText('AI');
    expect(aiBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('filters audit logs by one or more action types', () => {
    render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByLabelText('新增参与者'));

    expect(screen.getAllByText('新增参与者').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('添加主要参与者')).toBeDefined();
    expect(screen.getByText('新增候选参与者')).toBeDefined();
    expect(screen.queryByText('调整流程步骤描述')).toBeNull();
    expect(screen.queryByText('通过LLM精炼优化用户需求文档')).toBeNull();

    fireEvent.click(screen.getByLabelText('AI 精炼用户需求'));

    expect(screen.getAllByText('新增参与者').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('添加主要参与者')).toBeDefined();
    expect(screen.getByText('新增候选参与者')).toBeDefined();
    expect(screen.getByText('通过LLM精炼优化用户需求文档')).toBeDefined();
    expect(screen.queryByText('调整流程步骤描述')).toBeNull();

    fireEvent.click(screen.getByText('全部'));

    expect(screen.getByText('调整流程步骤描述')).toBeDefined();
  });

  it('uses English action labels and summaries in English mode', () => {
    setTestLocale('en-US');
    render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    );

    expect(screen.getByText('Recent Change History')).toBeDefined();
    expect(screen.getAllByText('Update User Requirements').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('AI Refine User Requirements').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('更新用户需求')).toBeNull();
    expect(screen.queryByText('手动更新用户需求文档')).toBeNull();
  });
});
