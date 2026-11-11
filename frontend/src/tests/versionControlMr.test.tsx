import { renderWithEffects as render } from './renderWithEffects';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../lib/api', () => {
  const mockMrs = [
    {
      id: 1, public_id: 'mr-1', project_id: 123,
      title: 'Add payment flow', description: null,
      source_branch_name: 'feature/pay', target_branch_name: 'main',
      source_branch_public_id: 'bp1', target_branch_public_id: 'bp2',
      status: 'open', author_user_id: 1, author_email: 'dev@test.com',
      diff_summary: null, active_review_count: 1, total_comments: 2,
      source_head_short: 'abc12345', target_head_short: 'def67890',
      created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-01T00:00:00Z',
    },
    {
      id: 2, public_id: 'mr-2', project_id: 123,
      title: 'Fix login', description: 'Fixes auth flow',
      source_branch_name: 'fix/login', target_branch_name: 'main',
      source_branch_public_id: 'bp3', target_branch_public_id: 'bp2',
      status: 'approved', author_user_id: 2, author_email: 'qa@test.com',
      diff_summary: null, active_review_count: 0, total_comments: 0,
      source_head_short: null, target_head_short: null,
      created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-01T00:00:00Z',
    },
  ];
  return {
    workspaceApi: {
      listMergeRequests: vi.fn().mockResolvedValue({ items: mockMrs, total: 2, limit: 50, offset: 0 }),
      getMergeRequestDetail: vi.fn().mockResolvedValue({
        ...mockMrs[0], source_head_commit_id: 10, source_head_public_id: 'abc12345',
        target_head_commit_id: 20, target_head_public_id: 'def67890',
        merge_base_commit_id: 5, merge_base_public_id: 'base1',
        merged_commit_id: null, merged_commit_public_id: null,
        reviews: [], comments: [], can_approve: false, can_merge: false, blocking_reasons: [],
      }),
      previewMergeRequest: vi.fn().mockResolvedValue({
        merge_base_public_id: 'base1',
        source_head_public_id: 'abc1',
        target_head_public_id: 'h1',
        diff_summary: { total_added: 2, total_removed: 0, total_modified: 1 },
      }),
      reviewMergeRequest: vi.fn(),
      closeMergeRequest: vi.fn(),
      addMergeRequestComment: vi.fn().mockResolvedValue({
        id: 5, author_email: 'dev@test.com', comment: 'needs better description',
        entity_uuid: 'feat-uuid', field_path: 'description',
        required: true, status: 'active',
        effective_source_head_id: 10, expired_by_source_head_id: null,
        created_at: '',
      }),
      resolveMrComment: vi.fn(),
      reopenMrComment: vi.fn(),
      getSemanticDiff: vi.fn().mockResolvedValue({
        summary: { by_type: { feature: { added: 1, removed: 0, modified: 0 } }, total_added: 1, total_removed: 0, total_modified: 0 },
        entries: [
          { change_type: 'field_changed', entity_type: 'feature', entity_uuid: 'feat-uuid', entity_name: 'Payment', parent_uuid: null, parent_type: null, path: 'feature', field: 'description', before: 'old', after: 'new', text_blocks: [], relation_type: null, related_entity_uuid: null, related_entity_name: null, before_position: null, after_position: null },
        ],
        total: 1, limit: 200, offset: 0,
      }),
      createMergeRequest: vi.fn().mockResolvedValue({
        id: 3, public_id: 'mr-3', project_id: 123, title: 'My feature MR', status: 'open',
        source_branch_name: 'feature/pay', target_branch_name: 'main',
        author_email: 'dev@test.com', reviews: [], comments: [],
        can_approve: false, can_merge: false, blocking_reasons: [],
      }),
    },
  };
});

import { MergeRequestView } from '../components/version-control/MergeRequestView';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

describe('MergeRequestView', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({
      branches: [
        { id: 1, public_id: 'main', name: 'main', is_protected: true, is_default: true, head_commit_public_id: 'h1', permissions: { can_write: false, can_delete: false, can_rename: false, is_protected: true }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
        { id: 2, public_id: 'bp1', name: 'feature/pay', is_protected: false, is_default: false, head_commit_public_id: 'abc1', permissions: { can_write: true, can_delete: true, can_rename: true, is_protected: false }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
        { id: 3, public_id: 'bp3', name: 'fix/login', is_protected: false, is_default: false, head_commit_public_id: 'def4', permissions: { can_write: true, can_delete: true, can_rename: true, is_protected: false }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } } as any,
      ],
    });
  });

  it('renders MR list with titles and statuses', async () => {
    await render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    expect(await screen.findByText('Add payment flow')).toBeTruthy();
    expect(screen.getByText('Fix login')).toBeTruthy();
    expect(screen.getAllByText('进行中').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('已批准')).toBeTruthy();
  });

  it('New MR button is visible', async () => {
    await render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    expect(screen.getByText('新建 MR')).toBeTruthy();
  });

  it('clicking New MR opens dialog and selecting branches triggers preview', async () => {
    await render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    // 打开创建对话框
    await act(async () => fireEvent.click(screen.getByText('新建 MR')));

    // 对话框展示 source / target 分支选择
    expect(screen.getByText('创建合并请求')).toBeTruthy();
    expect(screen.getByText('源分支')).toBeTruthy();
    expect(screen.getByText('目标分支')).toBeTruthy();

    // 选择分支触发 preview
    const selects = document.querySelectorAll('select');
    await act(async () => fireEvent.change(selects[0], { target: { value: 'bp1' } }));
    await act(async () => fireEvent.change(selects[1], { target: { value: 'main' } }));

    const { workspaceApi } = await import('../lib/api');
    expect(workspaceApi.previewMergeRequest).toHaveBeenCalledWith('project-123', {
      source_branch_public_id: 'bp1',
      target_branch_public_id: 'main',
    });
  });

  it('submitting create MR calls createMergeRequest with correct params', async () => {
    const { workspaceApi } = await import('../lib/api');
    await render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    await act(async () => fireEvent.click(screen.getByText('新建 MR')));

    const selects = document.querySelectorAll('select');
    await act(async () => fireEvent.change(selects[0], { target: { value: 'bp1' } }));
    await act(async () => fireEvent.change(selects[1], { target: { value: 'main' } }));

    // 填写标题
    const titleInput = screen.getByPlaceholderText(/概括变更/i);
    await act(async () => fireEvent.change(titleInput, { target: { value: 'My feature MR' } }));

    // 提交
    await act(async () => fireEvent.click(screen.getByText('创建 MR')));

    expect(workspaceApi.createMergeRequest).toHaveBeenCalledWith('project-123', expect.objectContaining({
      source_branch_public_id: 'bp1',
      target_branch_public_id: 'main',
      title: 'My feature MR',
    }));
  });

  it('selecting MR shows review and blocking reason', async () => {
    const { workspaceApi } = await import('../lib/api');
    // 覆盖详情 mock：包含 stale review 和 blocking_reasons
    (workspaceApi.getMergeRequestDetail as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 1, public_id: 'mr-1', project_id: 123,
      title: 'Add payment flow', description: null,
      source_branch_name: 'feature/pay', target_branch_name: 'main',
      source_branch_public_id: 'bp1', target_branch_public_id: 'bp2',
      status: 'open', author_user_id: 1, author_email: 'dev@test.com',
      diff_summary: null, active_review_count: 1, total_comments: 1,
      source_head_short: 'abc12345', target_head_short: 'def67890',
      created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-01T00:00:00Z',
      source_head_commit_id: 10, source_head_public_id: 'abc12345',
      target_head_commit_id: 20, target_head_public_id: 'def67890',
      merge_base_commit_id: 5, merge_base_public_id: 'base1',
      merged_commit_id: null, merged_commit_public_id: null,
      reviews: [
        { id: 1, reviewer_user_id: 2, reviewer_email: 'admin@test.com', decision: 'approved', comment: 'LGTM', status: 'stale', stale_reason: 'source_branch_advanced', created_at: '', updated_at: '' },
      ],
      comments: [
        { id: 1, author_user_id: 1, author_email: 'dev@test.com', entity_uuid: 'e1-uuid', field_path: 'description', relation_key: null, comment: 'needs update', required: true, status: 'active', effective_source_head_id: 10, expired_by_source_head_id: null, created_at: '' },
      ],
      can_approve: false, can_merge: false,
      blocking_reasons: ['missing_approval'],
    });

    await render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    const mrItem = await screen.findByText('Add payment flow');
    const mrButton = mrItem.closest('button') || mrItem;
    await act(async () => fireEvent.click(mrButton));

    await waitFor(() => {
      expect(workspaceApi.getMergeRequestDetail).toHaveBeenCalled();
    });

    // 切换到概览与评审 tab
    // 切换到概览与评审 tab
    const overviewTab = await screen.findByRole('button', { name: /概览/ });
    await act(async () => fireEvent.click(overviewTab));

    // stale review 显示原因
    expect(await screen.findByText(/已过期/)).toBeTruthy();
    expect(screen.getByText(/source_branch_advanced/)).toBeTruthy();

    // 评论锚点展示：统一时间线中显示行内评论徽标与翻译后的字段名（不再暴露原始 UUID）
    expect(screen.getByText(/行内评论/)).toBeTruthy();
    expect(screen.getByText(/描述说明/)).toBeTruthy();
  });

  it('selecting diff entry and adding anchor comment calls addMergeRequestComment', async () => {
    const { workspaceApi } = await import('../lib/api');
    (workspaceApi.getMergeRequestDetail as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 1, public_id: 'mr-1', project_id: 123,
      title: 'Add payment flow', description: null,
      source_branch_name: 'feature/pay', target_branch_name: 'main',
      source_branch_public_id: 'bp1', target_branch_public_id: 'bp2',
      status: 'open', author_user_id: 1, author_email: 'dev@test.com',
      diff_summary: null, active_review_count: 0, total_comments: 0,
      source_head_short: 'abc12345', target_head_short: 'def67890',
      created_at: '', updated_at: '',
      source_head_commit_id: 10, source_head_public_id: 'abc12345',
      target_head_commit_id: 20, target_head_public_id: 'def67890',
      merge_base_commit_id: 5, merge_base_public_id: 'base1',
      merged_commit_id: null, merged_commit_public_id: null,
      reviews: [], comments: [],
      can_approve: false, can_merge: false, blocking_reasons: [],
    });

    await render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    const mrItem = await screen.findByText('Add payment flow');
    await act(async () => fireEvent.click(mrItem.closest('button') || mrItem));

    // 等待 SemanticDiffView 加载并渲染 entry
    const entryBtn = await screen.findByText('Payment');
    await act(async () => fireEvent.click(entryBtn));

    // 行内评论先进入收起态胶囊，点击胶囊展开评论表单
    await act(async () => fireEvent.click(await screen.findByText(/写评论/)));
    const textarea = screen.getByPlaceholderText('添加评审评论…');
    await act(async () => fireEvent.change(textarea, { target: { value: 'needs better description' } }));

    // 勾选 required
    const checkbox = screen.getByRole('checkbox');
    await act(async () => fireEvent.click(checkbox));

    // 提交评论
    await act(async () => fireEvent.click(screen.getByText('发表评论')));

    expect(workspaceApi.addMergeRequestComment).toHaveBeenCalledWith('project-123', 'mr-1', expect.objectContaining({
      entity_uuid: 'feat-uuid',
      field_path: 'description',
      comment: 'needs better description',
      required: true,
    }));
  });

  it('MergeRequestView 异步追加中途切换状态筛选时，丢弃旧数据混入且正确恢复加载状态', async () => {
    const { workspaceApi } = await import('../lib/api');
    // 第一次查询（all 状态）：50 条
    (workspaceApi.listMergeRequests as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      items: Array.from({ length: 50 }, (_, i) => ({
        id: i + 1,
        public_id: `mr-old-${i + 1}`,
        title: `MR 旧数据 ${i + 1}`,
        status: 'open',
        source_branch_name: 'feat',
        target_branch_name: 'main',
        created_at: '2026-08-01T00:00:00Z',
      })),
      total: 60,
    });

    let resolveAppendPromise!: (val: any) => void;
    const appendPromise = new Promise((resolve) => {
      resolveAppendPromise = resolve;
    });

    // 第二次（append 请求）：deferred
    (workspaceApi.listMergeRequests as ReturnType<typeof vi.fn>).mockReturnValueOnce(appendPromise);

    await render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getByText('MR 旧数据 1')).toBeTruthy();
      expect(screen.getByText(/加载更多 \(剩余 10 个\)/)).toBeTruthy();
    });

    // 点击加载更多，触发 append 请求
    await act(async () => fireEvent.click(screen.getByText(/加载更多 \(剩余 10 个\)/)));

    // 用户切换筛选为已合并 'merged'
    (workspaceApi.listMergeRequests as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      items: [
        {
          id: 99,
          public_id: 'mr-merged-99',
          title: '已合并的新 MR',
          status: 'merged',
          source_branch_name: 'feat',
          target_branch_name: 'main',
          created_at: '2026-08-02T00:00:00Z',
        },
      ],
      total: 1,
    });

    await act(async () => fireEvent.click(screen.getByRole('button', { name: /已合并/ })));

    // 等待新筛选结果渲染
    await waitFor(() => {
      expect(screen.getByText('已合并的新 MR')).toBeTruthy();
      expect(screen.queryByText('MR 旧数据 1')).toBeNull();
    });

    // 此时旧 append 请求返回
    resolveAppendPromise({
      items: Array.from({ length: 10 }, (_, i) => ({
        id: 51 + i,
        public_id: `mr-old-${51 + i}`,
        title: `MR 旧数据 ${51 + i}`,
        status: 'open',
        source_branch_name: 'feat',
        target_branch_name: 'main',
        created_at: '2026-08-01T00:00:00Z',
      })),
      total: 60,
    });

    // 验证新列表绝不混入旧 append 的数据，且加载按钮不会遗留锁死
    await waitFor(() => {
      expect(screen.queryByText('MR 旧数据 51')).toBeNull();
      expect(screen.getByText('已合并的新 MR')).toBeTruthy();
      expect(screen.queryByText(/加载更多/)).toBeNull(); // 仅 1 条，无加载更多
    });
  });
});
