import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { BranchSelector } from '../components/version-control/BranchSelector';
import { VersionControlBar } from '../components/version-control/VersionControlBar';
import { CreateBranchDialog } from '../components/version-control/CreateBranchDialog';
import { SemanticDiffView } from '../components/version-control/SemanticDiffView';
import { BranchSwitchConfirmDialog } from '../components/version-control/BranchSwitchConfirmDialog';
import { Repository } from '../pages/Repository';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getSemanticDiff: vi.fn().mockResolvedValue({ summary: { by_type: {}, total_added: 0, total_removed: 0, total_modified: 0 }, entries: [], total: 0, limit: 200, offset: 0 }),
    createCommit: vi.fn().mockResolvedValue({}),
    createBranch: vi.fn().mockResolvedValue({ public_id: 'feature-new' }),
    listBranches: vi.fn().mockResolvedValue([]),
    listCommits: vi.fn().mockResolvedValue({ commits: [], total: 0, limit: 100, offset: 0 }),
  },
}));

import { workspaceApi } from '../lib/api';

function seedStore() {
  useWorkspaceStore.setState({
    sessionVersion: 1,
    ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any,
    branchRef: 'main',
    branches: [
      { id: 1, public_id: 'main', name: 'main', is_protected: true, is_default: true, permissions: { can_write: false, can_delete: false, can_rename: false, is_protected: true }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
      { id: 2, public_id: 'feature-a', name: 'feature/探索', is_protected: false, is_default: false, head_commit_public_id: 'abc123', permissions: { can_write: true, can_delete: true, can_rename: true, is_protected: false }, workspace_dirty: { is_dirty: true, modified_entities_count: 2 } } as any,
    ],
    currentBranch: { id: 1, public_id: 'main', name: 'main', is_protected: true, is_default: true, permissions: { can_write: false, can_delete: false, can_rename: false, is_protected: true }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
    commits: null,
    branchLoading: false,
    commitLoading: false,
    commitError: null,
  });
}

describe('Version Control Branch UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedStore();
  });

  it('BranchSelector 展示当前分支与受保护标识', () => {
    render(
      <MemoryRouter>
        <BranchSelector />
      </MemoryRouter>
    );
    expect(screen.getByRole('button', { name: /当前分支/ })).toBeTruthy();
    expect(screen.getByText('main')).toBeTruthy();
    expect(screen.getByText('受保护')).toBeTruthy();
  });

  it('切换分支时下拉展示两个分支并关闭', () => {
    render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    // 打开下拉：出现两个分支选项（按钮与列表中可能各出现一次 main）
    fireEvent.click(screen.getByTestId('branch-selector-button'));
    expect(screen.getByText('feature/探索')).toBeTruthy();
    expect(screen.getAllByText('main').length).toBeGreaterThanOrEqual(1);
    // 选择 feature/探索 后下拉关闭（分支选项不再可见）
    fireEvent.click(screen.getAllByText('feature/探索')[0]);
    expect(screen.queryByText('feature/探索')).toBeNull();
  });

  it('main 上不展示直接提交按钮，feature 分支展示', () => {
    const { rerender } = render(
      <MemoryRouter>
        <VersionControlBar />
      </MemoryRouter>
    );
    // main 受保护：不出现提交按钮
    expect(screen.queryByText('提交变更')).toBeNull();

    // 切到可写分支后出现提交按钮
    useWorkspaceStore.setState({
      currentBranch: { id: 2, public_id: 'feature-a', name: 'feature/探索', is_protected: false, is_default: false, head_commit_public_id: 'abc123', permissions: { can_write: true, can_delete: true, can_rename: true, is_protected: false }, workspace_dirty: { is_dirty: true, modified_entities_count: 2 } } as any,
    });
    rerender(
      <MemoryRouter>
        <VersionControlBar />
      </MemoryRouter>
    );
    expect(screen.getByText('提交变更')).toBeTruthy();
  });

  it('受保护 main 上允许创建分支', async () => {
    // 当前分支为受保护 main（can_write=false），仍可创建新分支。
    const onCreated = vi.fn();
    render(
      <MemoryRouter>
        <CreateBranchDialog open onClose={vi.fn()} onCreated={onCreated} />
      </MemoryRouter>
    );
    fireEvent.change(screen.getByPlaceholderText(/feature\//), { target: { value: 'feature/pay' } });
    fireEvent.click(screen.getByText('创建'));
    await waitFor(() => expect(workspaceApi.createBranch).toHaveBeenCalled());
  });

  it('存在未保存编辑时切换分支需经全局确认', () => {
    useWorkspaceStore.setState({ editDirty: true, pendingBranchRef: null });
    render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId('branch-selector-button'));
    fireEvent.click(screen.getByText('feature/探索'));
    // 切换被推迟：pendingBranchRef 置为目标，未直接导航。
    expect(useWorkspaceStore.getState().pendingBranchRef).toBe('feature-a');

    // 全局确认弹窗独立渲染在 App 层：展示并支持放弃/取消。
    const { rerender } = render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSwitchConfirmDialog />
      </MemoryRouter>
    );
    expect(screen.getByText('放弃并切换')).toBeTruthy();

    // 取消：保留编辑状态，pending 清空。
    fireEvent.click(screen.getByText('取消'));
    expect(useWorkspaceStore.getState().pendingBranchRef).toBeNull();
    expect(useWorkspaceStore.getState().editDirty).toBe(true);

    // 再次触发，选择放弃：清空 editDirty、自增 editDiscardVersion。
    useWorkspaceStore.setState({ editDirty: true, pendingBranchRef: 'feature-a' });
    rerender(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSwitchConfirmDialog />
      </MemoryRouter>
    );
    const beforeVersion = useWorkspaceStore.getState().editDiscardVersion;
    fireEvent.click(screen.getAllByText('放弃并切换')[0]);
    const state = useWorkspaceStore.getState();
    expect(state.editDirty).toBe(false);
    expect(state.pendingBranchRef).toBeNull();
    expect(state.editDiscardVersion).toBe(beforeVersion + 1);
  });

  it('requestBranchSwitch 干净状态下直接返回 true，脏状态返回 false', () => {
    useWorkspaceStore.setState({ editDirty: false, isGenerating: false });
    expect(useWorkspaceStore.getState().requestBranchSwitch('feature-a')).toBe(true);
    useWorkspaceStore.setState({ editDirty: true });
    expect(useWorkspaceStore.getState().requestBranchSwitch('feature-a')).toBe(false);
    expect(useWorkspaceStore.getState().pendingBranchRef).toBe('feature-a');
  });

  it('仓库分支列表切换同样走未保存守卫', () => {
    useWorkspaceStore.setState({
      editDirty: true,
      pendingBranchRef: null,
      ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any,
      branchRef: 'main',
      branches: [
        { id: 1, public_id: 'main', name: 'main', is_protected: true, is_default: true, permissions: { can_write: false, can_delete: false, can_rename: false, is_protected: true }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
        { id: 2, public_id: 'feature-a', name: 'feature/探索', is_protected: false, is_default: false, permissions: { can_write: true, can_delete: true, can_rename: true, is_protected: false }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
      ],
      currentBranch: { id: 1, public_id: 'main', name: 'main', is_protected: true, is_default: true, permissions: { can_write: false, can_delete: false, can_rename: false, is_protected: true }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
      commits: null,
    });
    render(
      <MemoryRouter initialEntries={['/projects/project-123/repo']}>
        <Repository />
      </MemoryRouter>
    );
    fireEvent.click(screen.getAllByText('feature/探索')[0]);
    // 分支列表点击被守卫拦截：pendingBranchRef 置为目标，未导航。
    expect(useWorkspaceStore.getState().pendingBranchRef).toBe('feature-a');
  });

  it('已在仓库页时，顶部 new_branch=1 深链会再次打开创建弹窗', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any,
      branchRef: 'main',
      branches: [
        { id: 1, public_id: 'main', name: 'main', is_protected: true, is_default: true, permissions: { can_write: false, can_delete: false, can_rename: false, is_protected: true }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
        { id: 2, public_id: 'feature-a', name: 'feature/探索', is_protected: false, is_default: false, permissions: { can_write: true, can_delete: true, can_rename: true, is_protected: false }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
      ],
      currentBranch: { id: 1, public_id: 'main', name: 'main', is_protected: true, is_default: true, permissions: { can_write: false, can_delete: false, can_rename: false, is_protected: true }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
      commits: null,
    });

    function Harness() {
      const nav = useNavigate();
      return (
        <>
          <button onClick={() => nav('/projects/project-123/repo?new_branch=1')}>go-new-branch</button>
          <Repository />
        </>
      );
    }
    render(
      <MemoryRouter initialEntries={['/projects/project-123/repo']}>
        <Routes>
          <Route path="/projects/project-123/repo" element={<Harness />} />
        </Routes>
      </MemoryRouter>
    );
    // 初始无创建弹窗
    expect(screen.queryByText('新建分支')).toBeNull();
    // 同页导航：仅改 search 参数，组件不重新挂载
    fireEvent.click(screen.getByText('go-new-branch'));
    await waitFor(() => expect(screen.getByText('新建分支')).toBeTruthy());
  });

  it('SemanticDiffView 将 entity_type/change_type 传给接口', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any,
      branches: [],
      currentBranch: null,
      commits: null,
    });
    render(
      <MemoryRouter>
        <SemanticDiffView projectId="project-123" entityType="feature" changeType="entity_added" />
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(workspaceApi.getSemanticDiff).toHaveBeenCalledWith(
        'project-123',
        expect.objectContaining({ entity_type: 'feature', change_type: 'entity_added' })
      )
    );
  });
});


describe('BranchSelector 键盘可访问性', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedStore();
  });

  it('打开后焦点在搜索框，ArrowDown 暴露活动项并高亮', () => {
    render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId('branch-selector-button'));
    const search = screen.getByRole('combobox', { name: /搜索/ });
    expect(document.activeElement).toBe(search);
    // ArrowDown 后 activedescendant 指向第一个 option。
    fireEvent.keyDown(search, { key: 'ArrowDown' });
    expect(search.getAttribute('aria-activedescendant')).toBe('branch-option-0');
    // 高亮项具备视觉选中态（类名含 indigo 高亮）——由 activedescendant 暴露给辅助技术。
    const firstOption = screen.getAllByRole('option')[0];
    expect(firstOption.className).toContain('bg-indigo-50');
  });

  it('Enter 选择 ArrowDown 高亮的分支并导航到目标', () => {
    const switched: string[] = [];
    useWorkspaceStore.setState({
      requestBranchSwitch: (branchRef: string) => { switched.push(branchRef); return true; },
    } as any);
    render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId('branch-selector-button'));
    const search = screen.getByRole('combobox', { name: /搜索/ });
    // ArrowDown 一次 → 第一个 option（main）；再 ArrowDown → 第二个（feature/探索）。
    fireEvent.keyDown(search, { key: 'ArrowDown' });
    fireEvent.keyDown(search, { key: 'ArrowDown' });
    fireEvent.keyDown(search, { key: 'Enter' });
    // 导航目标为 feature/探索（第二个分支的 public_id）。
    expect(switched).toEqual(['feature-a']);
    expect(screen.queryByText('feature/探索')).toBeNull();
  });

  it('Escape 关闭下拉并归还焦点到触发按钮', () => {
    render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    const trigger = screen.getByTestId('branch-selector-button');
    fireEvent.click(trigger);
    expect(screen.getByText('feature/探索')).toBeTruthy();
    const search = screen.getByRole('combobox', { name: /搜索/ });
    fireEvent.keyDown(search, { key: 'Escape' });
    expect(screen.queryByText('feature/探索')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('空搜索结果时 Escape 仍能关闭下拉', () => {
    render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId('branch-selector-button'));
    const search = screen.getByRole('combobox', { name: /搜索/ });
    fireEvent.change(search, { target: { value: 'zzz-nothing' } });
    fireEvent.keyDown(search, { key: 'Escape' });
    expect(screen.queryByText('feature/探索')).toBeNull();
  });

  it('option 数量等于分支数量，每个分支仅一个 option，当前分支 aria-selected=true', () => {
    render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId('branch-selector-button'));
    const options = screen.getAllByRole('option');
    // seedStore 有两分支：main + feature/探索。
    expect(options.length).toBe(2);
    // 当前分支（main）aria-selected=true，另一分支 false。
    const mainOption = options.find((o) => o.textContent?.includes('main'));
    const featureOption = options.find((o) => o.textContent?.includes('feature/探索'));
    expect(mainOption?.getAttribute('aria-selected')).toBe('true');
    expect(featureOption?.getAttribute('aria-selected')).toBe('false');
    // 每个 option 有稳定 id 供 activedescendant 引用。
    expect(options[0].getAttribute('id')).toBe('branch-option-0');
  });
});

