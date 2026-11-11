import { renderWithEffects as render } from './renderWithEffects';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { BranchSelector } from '../components/version-control/BranchSelector';
import { VersionControlBar } from '../components/version-control/VersionControlBar';
import { CreateBranchDialog } from '../components/version-control/CreateBranchDialog';
import { SemanticDiffView } from '../components/version-control/SemanticDiffView';
import { CommitDetailDialog } from '../components/version-control/CommitDetailDialog';
import { BranchSwitchConfirmDialog } from '../components/version-control/BranchSwitchConfirmDialog';
import { Repository } from '../pages/Repository';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getSemanticDiff: vi.fn().mockResolvedValue({ summary: { by_type: {}, total_added: 0, total_removed: 0, total_modified: 0 }, entries: [], total: 0, limit: 200, offset: 0 }),
    createCommit: vi.fn().mockResolvedValue({}),
    createBranch: vi.fn().mockResolvedValue({ public_id: 'feature-new' }),
    listBranches: vi.fn().mockResolvedValue([]),
    listCommits: vi.fn().mockResolvedValue({ commits: [], total: 0, limit: 100, offset: 0 }),
    getCommitDetail: vi.fn().mockResolvedValue(null),
    listProjectMembers: vi.fn().mockResolvedValue([]),
  },
}));

import { workspaceApi } from '../lib/api';

import { useAuthStore } from '../store/useAuthStore';

function seedStore() {
  useAuthStore.setState({
    user: { id: 1, email: 'admin@test.com', role: 'admin' } as any,
    isAuthenticated: true,
  });
  (workspaceApi.listProjectMembers as ReturnType<typeof vi.fn>).mockResolvedValue([
    { userId: 1, email: 'admin@test.com', role: 'owner' },
  ]);
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

  it('BranchSelector 展示当前分支与受保护标识', async () => {
    await render(
      <MemoryRouter>
        <BranchSelector />
      </MemoryRouter>
    );
    expect(screen.getByRole('button', { name: /当前分支/ })).toBeTruthy();
    expect(screen.getByText('main')).toBeTruthy();
    expect(screen.getByText('受保护')).toBeTruthy();
  });

  it('当前分支详情尚未加载时不显示 main', async () => {
    useWorkspaceStore.setState({ branchRef: 'feature-a', currentBranch: null });
    await render(<MemoryRouter><BranchSelector /></MemoryRouter>);
    expect(screen.getByTestId('branch-selector-button').textContent).not.toContain('main');
  });

  it('切换分支时下拉展示两个分支并关闭', async () => {
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    // 打开下拉：出现两个分支选项（按钮与列表中可能各出现一次 main）
    await act(async () => fireEvent.click(screen.getByTestId('branch-selector-button')));
    expect(screen.getByText('feature/探索')).toBeTruthy();
    expect(screen.getAllByText('main').length).toBeGreaterThanOrEqual(1);
    // 选择 feature/探索 后下拉关闭（分支选项不再可见）
    await act(async () => fireEvent.click(screen.getAllByText('feature/探索')[0]));
    expect(screen.queryByText('feature/探索')).toBeNull();
  });

  it('main 上不展示直接提交按钮，feature 分支展示', async () => {
    const { rerender } = await render(
      <MemoryRouter>
        <VersionControlBar />
      </MemoryRouter>
    );
    // main 受保护：不出现提交按钮
    expect(screen.queryByText('提交变更')).toBeNull();

    // 切到可写分支后出现提交按钮
    await act(async () => useWorkspaceStore.setState({
      currentBranch: { id: 2, public_id: 'feature-a', name: 'feature/探索', is_protected: false, is_default: false, head_commit_public_id: 'abc123', permissions: { can_write: true, can_delete: true, can_rename: true, is_protected: false }, workspace_dirty: { is_dirty: true, modified_entities_count: 2 } } as any,
    }));
    await rerender(
      <MemoryRouter>
        <VersionControlBar />
      </MemoryRouter>
    );
    expect(screen.getByText('提交变更')).toBeTruthy();
  });

  it('受保护 main 上允许创建分支', async () => {
    // 当前分支为受保护 main（can_write=false），仍可创建新分支。
    const onCreated = vi.fn();
    await render(
      <MemoryRouter>
        <CreateBranchDialog open onClose={vi.fn()} onCreated={onCreated} />
      </MemoryRouter>
    );
    await act(async () => fireEvent.change(screen.getByPlaceholderText(/feature\//), { target: { value: 'feature/pay' } }));
    const createBtn = await screen.findByText('创建');
    await act(async () => fireEvent.click(createBtn));
    await waitFor(() => expect(workspaceApi.createBranch).toHaveBeenCalled());
  });

  it.each([undefined, null, 'history-commit'])(
    '创建分支传递当前分支，显式提交 %s 优先',
    async (sourceCommitPublicId) => {
      useWorkspaceStore.setState({ branchRef: 'feature-a' });
      await render(<CreateBranchDialog open onClose={vi.fn()} sourceCommitPublicId={sourceCommitPublicId} />);
      await act(async () => fireEvent.change(screen.getByPlaceholderText(/feature\//), { target: { value: 'feature/child' } }));
      const createButton = await screen.findByRole('button', { name: '创建' });
      await waitFor(() => expect((createButton as HTMLButtonElement).disabled).toBe(false));
      await act(async () => fireEvent.click(createButton));
      await waitFor(() => expect(workspaceApi.createBranch).toHaveBeenCalled());
      const [projectId, payload] = vi.mocked(workspaceApi.createBranch).mock.calls[0];
      expect(projectId).toBe('project-123');
      expect(payload.source_commit_public_id).toBe(sourceCommitPublicId || undefined);
      expect(payload.source_branch_public_id).toBe(sourceCommitPublicId ? undefined : 'feature-a');
    },
  );

  it.each(['branch', 'deep-link', 'commit'])(
    '仓库选中历史提交后通过 %s 入口创建分支使用对应起点',
    async (entry) => {
      const state = useWorkspaceStore.getState();
      const branches = state.branches!;
      const historyCommit = {
        id: 10, public_id: 'history-commit', short_id: 'history1', message: 'Historical snapshot',
        state_hash: 'hash', schema_version: '1', created_at: '2026-11-01T00:00:00Z',
        parent_ids: [], parent_public_ids: [], is_merge: false,
        branch_public_ids: ['main'], branch_names: ['main'],
      };
      const commitList = { commits: [historyCommit], total: 1, limit: 100, offset: 0 };
      vi.mocked(workspaceApi.listBranches).mockResolvedValueOnce(branches);
      vi.mocked(workspaceApi.listCommits).mockResolvedValueOnce(commitList);
      useWorkspaceStore.setState({
        branchRef: 'feature-a', currentBranch: branches[1], commits: commitList,
      });
      function Harness() {
        const navigate = useNavigate();
        return <>
          <button onClick={() => navigate('/projects/project-123/repo?branch=feature-a&new_branch=1')}>new-branch-link</button>
          <Repository />
        </>;
      }
      await render(<MemoryRouter initialEntries={['/projects/project-123/repo?branch=feature-a']}><Harness /></MemoryRouter>);
      await act(async () => fireEvent.click(await screen.findByRole('button', { name: 'Historical snapshot, history1' })));
      if (entry === 'deep-link') {
        await act(async () => fireEvent.click(screen.getByText('new-branch-link')));
      } else {
        await act(async () => fireEvent.click(screen.getByRole('button', { name: entry === 'commit' ? '从此提交创建分支' : '新建分支' })));
      }
      await act(async () => fireEvent.change(await screen.findByPlaceholderText(/feature\//), { target: { value: 'feature/child' } }));
      const createButton = await screen.findByRole('button', { name: '创建' });
      await waitFor(() => expect((createButton as HTMLButtonElement).disabled).toBe(false));
      await act(async () => fireEvent.click(createButton));
      await waitFor(() => expect(workspaceApi.createBranch).toHaveBeenCalled());
      const [projectId, payload] = vi.mocked(workspaceApi.createBranch).mock.calls[0];
      expect(projectId).toBe('project-123');
      expect(payload.source_commit_public_id).toBe(entry === 'commit' ? 'history-commit' : undefined);
      expect(payload.source_branch_public_id).toBe(entry === 'commit' ? undefined : 'feature-a');
    },
  );

  it('存在未保存编辑时切换分支需经全局确认', async () => {
    useWorkspaceStore.setState({ editDirty: true, pendingBranchRef: null });
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    await act(async () => fireEvent.click(screen.getByTestId('branch-selector-button')));
    await act(async () => fireEvent.click(screen.getByText('feature/探索')));
    // 切换被推迟：pendingBranchRef 置为目标，未直接导航。
    expect(useWorkspaceStore.getState().pendingBranchRef).toBe('feature-a');

    // 全局确认弹窗独立渲染在 App 层：展示并支持放弃/取消。
    const { rerender } = await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSwitchConfirmDialog />
      </MemoryRouter>
    );
    expect(screen.getByText('放弃并切换')).toBeTruthy();

    // 取消：保留编辑状态，pending 清空。
    await act(async () => fireEvent.click(screen.getByText('取消')));
    expect(useWorkspaceStore.getState().pendingBranchRef).toBeNull();
    expect(useWorkspaceStore.getState().editDirty).toBe(true);

    // 再次触发，选择放弃：清空 editDirty、自增 editDiscardVersion。
    await act(async () => useWorkspaceStore.setState({ editDirty: true, pendingBranchRef: 'feature-a' }));
    await rerender(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSwitchConfirmDialog />
      </MemoryRouter>
    );
    const beforeVersion = useWorkspaceStore.getState().editDiscardVersion;
    await act(async () => fireEvent.click(screen.getAllByText('放弃并切换')[0]));
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

  it('仓库分支列表切换同样走未保存守卫', async () => {
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
    vi.mocked(workspaceApi.listBranches).mockResolvedValueOnce(useWorkspaceStore.getState().branches!);
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/repo']}>
        <Repository />
      </MemoryRouter>
    );
    await act(async () => fireEvent.click(screen.getAllByText('feature/探索')[0]));
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
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/repo']}>
        <Routes>
          <Route path="/projects/project-123/repo" element={<Harness />} />
        </Routes>
      </MemoryRouter>
    );
    // 初始无创建弹窗
    expect(screen.queryByText('新建分支')).toBeNull();
    // 同页导航：仅改 search 参数，组件不重新挂载
    await act(async () => fireEvent.click(screen.getByText('go-new-branch')));
    await waitFor(() => expect(screen.getByText('新建分支')).toBeTruthy());
  });

  it('SemanticDiffView 将 entity_type/change_type 传给接口', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any,
      branches: [],
      currentBranch: null,
      commits: null,
    });
    await render(
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

  it('打开后焦点在搜索框，ArrowDown 暴露活动项并高亮', async () => {
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    await act(async () => fireEvent.click(screen.getByTestId('branch-selector-button')));
    const search = screen.getByRole('combobox', { name: /搜索/ });
    expect(document.activeElement).toBe(search);
    // ArrowDown 后 activedescendant 指向第一个 option。
    await act(async () => fireEvent.keyDown(search, { key: 'ArrowDown' }));
    expect(search.getAttribute('aria-activedescendant')).toBe('branch-option-0');
    // 高亮项具备视觉选中态（类名含 indigo 高亮）——由 activedescendant 暴露给辅助技术。
    const firstOption = screen.getAllByRole('option')[0];
    expect(firstOption.className).toContain('bg-indigo-50');
  });

  it('Enter 选择 ArrowDown 高亮的分支并导航到目标', async () => {
    const switched: string[] = [];
    useWorkspaceStore.setState({
      requestBranchSwitch: (branchRef: string) => { switched.push(branchRef); return true; },
    } as any);
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    await act(async () => fireEvent.click(screen.getByTestId('branch-selector-button')));
    const search = screen.getByRole('combobox', { name: /搜索/ });
    // ArrowDown 一次 → 第一个 option（main）；再 ArrowDown → 第二个（feature/探索）。
    await act(async () => fireEvent.keyDown(search, { key: 'ArrowDown' }));
    await act(async () => fireEvent.keyDown(search, { key: 'ArrowDown' }));
    await act(async () => fireEvent.keyDown(search, { key: 'Enter' }));
    // 导航目标为 feature/探索（第二个分支的 public_id）。
    expect(switched).toEqual(['feature-a']);
    expect(screen.queryByText('feature/探索')).toBeNull();
  });

  it('Escape 关闭下拉并归还焦点到触发按钮', async () => {
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    const trigger = screen.getByTestId('branch-selector-button');
    await act(async () => fireEvent.click(trigger));
    expect(screen.getByText('feature/探索')).toBeTruthy();
    const search = screen.getByRole('combobox', { name: /搜索/ });
    await act(async () => fireEvent.keyDown(search, { key: 'Escape' }));
    expect(screen.queryByText('feature/探索')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('空搜索结果时 Escape 仍能关闭下拉', async () => {
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    await act(async () => fireEvent.click(screen.getByTestId('branch-selector-button')));
    const search = screen.getByRole('combobox', { name: /搜索/ });
    await act(async () => fireEvent.change(search, { target: { value: 'zzz-nothing' } }));
    await act(async () => fireEvent.keyDown(search, { key: 'Escape' }));
    expect(screen.queryByText('feature/探索')).toBeNull();
  });

  it('option 数量等于分支数量，每个分支仅一个 option，当前分支 aria-selected=true', async () => {
    await render(
      <MemoryRouter initialEntries={['/projects/project-123/what']}>
        <BranchSelector />
      </MemoryRouter>
    );
    await act(async () => fireEvent.click(screen.getByTestId('branch-selector-button')));
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

  it('CommitDetailDialog 正确渲染全模型快照（包含 project_metadata、feature_relations、attributes 等）并支持深层搜索', async () => {
    (workspaceApi.getCommitDetail as any).mockResolvedValue({
      public_id: 'commit-test-123',
      short_id: 'commit-123',
      message: '测试提交全模型',
      created_at: new Date().toISOString(),
      author_email: 'tester@example.com',
      branch_names: ['main'],
      state: {
        project_metadata: {
          user_requirements: '电商支付平台需求说明',
          kano_status: 'analyzed',
          unlocked_stages: 'what,how,scope',
        },
        actors: [
          { logical_uuid: 'act-1', name: '买家用户', description: '普通移动端消费者' },
        ],
        features: [
          { logical_uuid: 'feat-1', name: '扫码支付', description: '微信/支付宝聚合支付', actor_logical_uuids: ['act-1'] },
        ],
        feature_relations: [
          { logical_uuid: 'frel-1', parent_feature_logical_uuid: 'feat-root', child_feature_logical_uuid: 'feat-1', position: 0 },
        ],
        scenarios: [
          {
            logical_uuid: 'scen-1',
            name: '用户主扫付款成功',
            feature_logical_uuid: 'feat-1',
            actor_logical_uuid: 'act-1',
            content: '出示付款码被扫后扣款成功',
            acceptance_criteria: [{ logical_uuid: 'ac-1', content: '余额扣减准确' }],
          },
        ],
        flows: [
          {
            logical_uuid: 'flow-1',
            name: '收单扣款流程',
            description: '主扫扣款编排',
            feature_logical_uuids: ['feat-1'],
            steps: [
              {
                logical_uuid: 'step-1',
                name: '校验额度',
                position: 0,
                step_type: 'system',
                actor_logical_uuids: ['act-1'],
                input_business_object_logical_uuids: ['bo-1'],
                output_business_object_logical_uuids: ['bo-1'],
              },
            ],
          },
        ],
        scopes: [
          { logical_uuid: 'sc-1', status: 'in_scope', feature_logical_uuid: 'feat-1', kano_category_name: '必备属性', reason: '核心交易闭环' },
        ],
        business_objects: [
          {
            logical_uuid: 'bo-1',
            name: '支付单',
            attributes: [
              { name: 'amount', data_type: 'decimal', example: '100.00' },
              { name: 'status', data_type: 'string' },
            ],
          },
        ],
      },
    });

    await render(
      <MemoryRouter>
        <CommitDetailDialog projectId="project-123" commitRef="commit-test-123" open={true} onClose={vi.fn()} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/电商支付平台需求说明/)).toBeTruthy();
    });

    expect(screen.getByText('买家用户')).toBeTruthy();
    expect(screen.getByText('扫码支付')).toBeTruthy();
    expect(screen.getByText('用户主扫付款成功')).toBeTruthy();
    expect(screen.getByText('收单扣款流程')).toBeTruthy();
    expect(screen.getByText(/校验额度/)).toBeTruthy();
    expect(screen.getByText(/amount: decimal/)).toBeTruthy();
    expect(screen.getByText(/status: string/)).toBeTruthy();
    expect(screen.getByText(/核心交易闭环/)).toBeTruthy();
    expect(screen.getByText(/必备属性/)).toBeTruthy();

    // 验证深层搜索过滤
    const searchInput = screen.getByPlaceholderText(/在当前提交快照中搜索对象/);
    await act(async () => fireEvent.change(searchInput, { target: { value: 'decimal' } }));
    expect(screen.getByText(/amount: decimal/)).toBeTruthy();
    expect(screen.queryByText('买家用户')).toBeNull();
  });

  it('SemanticDiffView 展示分页总数并支持加载更多', async () => {
    (workspaceApi.getSemanticDiff as any).mockResolvedValueOnce({
      summary: { by_type: { feature: { added: 60, modified: 0, removed: 0 } }, total_added: 60, total_removed: 0, total_modified: 0 },
      entries: Array.from({ length: 50 }, (_, i) => ({
        entity_uuid: `feat-${i}`,
        entity_type: 'feature',
        entity_name: `功能 ${i}`,
        change_type: 'added',
        path: `features[${i}]`,
      })),
      total: 60,
      limit: 50,
      offset: 0,
    });

    await render(
      <MemoryRouter>
        <SemanticDiffView projectId="project-123" baseRef="main" targetRef="feature-a" />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/显示 50 \/ 总计 60 项变更/)).toBeTruthy();
      expect(screen.getByText(/加载更多 \(剩余 10 项\)/)).toBeTruthy();
    });
  });

  it('SemanticDiffView 异步追加中途切换查询参数时，取消旧数据混入且恢复新列表加载能力', async () => {
    // 第一次查询：50 项（共 60 项）
    (workspaceApi.getSemanticDiff as any).mockResolvedValueOnce({
      summary: { by_type: { feature: { added: 60, modified: 0, removed: 0 } }, total_added: 60, total_removed: 0, total_modified: 0 },
      entries: Array.from({ length: 50 }, (_, i) => ({
        entity_uuid: `feat-old-${i}`,
        entity_type: 'feature',
        entity_name: `旧功能 ${i}`,
        change_type: 'added',
        path: `features[${i}]`,
      })),
      total: 60,
      limit: 50,
      offset: 0,
    });

    let resolveAppendPromise!: (value: any) => void;
    const appendPromise = new Promise((resolve) => {
      resolveAppendPromise = resolve;
    });

    // 第二次查询（append 请求）：deferred
    (workspaceApi.getSemanticDiff as any).mockReturnValueOnce(appendPromise);

    const { rerender } = await render(
      <MemoryRouter>
        <SemanticDiffView projectId="project-123" baseRef="main" targetRef="feature-a" />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/旧功能 0/)).toBeTruthy();
      expect(screen.getByText(/加载更多 \(剩余 10 项\)/)).toBeTruthy();
    });

    // 点击加载更多，触发 append 请求
    await act(async () => fireEvent.click(screen.getByText(/加载更多 \(剩余 10 项\)/)));

    // 用户切换筛选分支 targetRef="feature-b"（产生第三次 initial 请求）
    (workspaceApi.getSemanticDiff as any).mockResolvedValueOnce({
      summary: { by_type: { feature: { added: 5, modified: 0, removed: 0 } }, total_added: 5, total_removed: 0, total_modified: 0 },
      entries: Array.from({ length: 5 }, (_, i) => ({
        entity_uuid: `feat-new-${i}`,
        entity_type: 'feature',
        entity_name: `新分支功能 ${i}`,
        change_type: 'added',
        path: `features[${i}]`,
      })),
      total: 5,
      limit: 50,
      offset: 0,
    });

    await rerender(
      <MemoryRouter>
        <SemanticDiffView projectId="project-123" baseRef="main" targetRef="feature-b" />
      </MemoryRouter>
    );

    // 等待新查询结果渲染
    await waitFor(() => {
      expect(screen.getByText(/新分支功能 0/)).toBeTruthy();
      expect(screen.queryByText(/旧功能 0/)).toBeNull();
    });

    // 此时旧 append 请求返回
    resolveAppendPromise({
      summary: { by_type: { feature: { added: 60, modified: 0, removed: 0 } }, total_added: 60, total_removed: 0, total_modified: 0 },
      entries: Array.from({ length: 10 }, (_, i) => ({
        entity_uuid: `feat-old-${50 + i}`,
        entity_type: 'feature',
        entity_name: `旧功能 ${50 + i}`,
        change_type: 'added',
        path: `features[${50 + i}]`,
      })),
      total: 60,
      limit: 50,
      offset: 50,
    });

    // 验证新列表绝不混入旧 append 的数据，且加载状态正常
    await waitFor(() => {
      expect(screen.queryByText(/旧功能 50/)).toBeNull();
      expect(screen.getByText(/新分支功能 0/)).toBeTruthy();
      expect(screen.queryByText(/加载更多/)).toBeNull(); // 共 5 项无更多
    });
  });
});
