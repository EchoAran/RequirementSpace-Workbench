import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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
    render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    expect(await screen.findByText('Add payment flow')).toBeTruthy();
    expect(screen.getByText('Fix login')).toBeTruthy();
    expect(screen.getByText('进行中')).toBeTruthy();
    expect(screen.getByText('已批准')).toBeTruthy();
  });

  it('New MR button is visible', () => {
    render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    expect(screen.getByText('新建 MR')).toBeTruthy();
  });

  it('clicking New MR opens dialog and selecting branches triggers preview', async () => {
    render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    // 打开创建对话框
    fireEvent.click(screen.getByText('新建 MR'));

    // 对话框展示 source / target 分支选择
    expect(screen.getByText('创建合并请求')).toBeTruthy();
    expect(screen.getByText('源分支')).toBeTruthy();
    expect(screen.getByText('目标分支')).toBeTruthy();

    // 选择分支触发 preview
    const selects = document.querySelectorAll('select');
    fireEvent.change(selects[0], { target: { value: 'bp1' } });
    fireEvent.change(selects[1], { target: { value: 'main' } });

    const { workspaceApi } = await import('../lib/api');
    expect(workspaceApi.previewMergeRequest).toHaveBeenCalledWith('project-123', {
      source_branch_public_id: 'bp1',
      target_branch_public_id: 'main',
    });
  });

  it('submitting create MR calls createMergeRequest with correct params', async () => {
    const { workspaceApi } = await import('../lib/api');
    render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    fireEvent.click(screen.getByText('新建 MR'));

    const selects = document.querySelectorAll('select');
    fireEvent.change(selects[0], { target: { value: 'bp1' } });
    fireEvent.change(selects[1], { target: { value: 'main' } });

    // 填写标题
    const titleInput = screen.getByPlaceholderText(/概括变更/i);
    fireEvent.change(titleInput, { target: { value: 'My feature MR' } });

    // 提交
    fireEvent.click(screen.getByText('创建 MR'));
    await new Promise((r) => setTimeout(r, 50));

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

    render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Add payment flow'));

    // stale review 显示原因
    expect(await screen.findByText(/已过期/)).toBeTruthy();
    expect(screen.getByText(/source_branch_advanced/)).toBeTruthy();

    // 评论锚点展示
    expect(screen.getByText('e1-uuid')).toBeTruthy();
    expect(screen.getAllByText(/description/).length).toBeGreaterThan(0);

    // 阻塞原因可读化
    expect(screen.getByText('等待管理员/所有者批准')).toBeTruthy();
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

    render(<MemoryRouter><MergeRequestView projectId="project-123" /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Add payment flow'));

    // 等待 SemanticDiffView 加载并渲染 entry
    const entryBtn = await screen.findByText('Payment');
    fireEvent.click(entryBtn);

    // 评论表单出现
    const textarea = screen.getByPlaceholderText('添加评审评论…');
    fireEvent.change(textarea, { target: { value: 'needs better description' } });

    // 勾选 required
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    // 提交评论
    fireEvent.click(screen.getByText('发表评论'));
    await new Promise((r) => setTimeout(r, 50));

    expect(workspaceApi.addMergeRequestComment).toHaveBeenCalledWith('project-123', 'mr-1', expect.objectContaining({
      entity_uuid: 'feat-uuid',
      field_path: 'description',
      comment: 'needs better description',
      required: true,
    }));
  });
});
