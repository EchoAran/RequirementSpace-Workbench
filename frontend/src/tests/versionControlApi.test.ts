import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../lib/http', () => ({
  http: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import { http } from '../lib/http';
import { workspaceApi } from '../lib/api';

describe('Version Control API 查询参数契约', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('listCommits 直接把查询参数作为 http.get 第二参数传递', async () => {
    (http.get as ReturnType<typeof vi.fn>).mockResolvedValue({ commits: [], total: 0, limit: 10, offset: 0 });
    await workspaceApi.listCommits('project-1', { branch: 'feature-x', limit: 10 });
    expect(http.get).toHaveBeenCalledWith('/projects/project-1/commits', { branch: 'feature-x', limit: 10 });
  });

  it('getSemanticDiff 直接传递 base_ref/target_ref/筛选参数', async () => {
    (http.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      summary: { by_type: {}, total_added: 0, total_removed: 0, total_modified: 0 },
      entries: [],
      total: 0,
      limit: 200,
      offset: 0,
    });
    await workspaceApi.getSemanticDiff('project-1', {
      base_ref: 'commit:abc',
      target_ref: 'commit:def',
      entity_type: 'feature',
      change_type: 'entity_added',
    });
    expect(http.get).toHaveBeenCalledWith('/projects/project-1/diff', {
      base_ref: 'commit:abc',
      target_ref: 'commit:def',
      entity_type: 'feature',
      change_type: 'entity_added',
    });
  });

  it('listCommits 支持 all 参数透传', async () => {
    (http.get as ReturnType<typeof vi.fn>).mockResolvedValue({ commits: [], total: 0, limit: 200, offset: 0 });
    await workspaceApi.listCommits('project-1', { all: true, limit: 200 });
    expect(http.get).toHaveBeenCalledWith('/projects/project-1/commits', { all: true, limit: 200 });
  });

  it('createCommit 通过 POST 发送消息与预期 head', async () => {
    (http.post as ReturnType<typeof vi.fn>).mockResolvedValue({ id: 1 });
    await workspaceApi.createCommit('project-1', {
      message: 'msg',
      expected_head_commit_public_id: 'head-1',
    });
    expect(http.post).toHaveBeenCalledWith('/projects/project-1/commits', {
      message: 'msg',
      expected_head_commit_public_id: 'head-1',
    });
  });

  it('getMergePreview 通过 GET 请求 merge-preview', async () => {
    (http.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      conflict_count: 0, conflicts: [], auto_merged_summary: {},
    });
    await workspaceApi.getMergePreview('project-1', 'mr-1');
    expect(http.get).toHaveBeenCalledWith('/projects/project-1/merge-requests/mr-1/merge-preview');
  });

  it('performMerge 通过 POST 发送 resolutions 与预览 heads', async () => {
    (http.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: 'merged',
      merged_commit_public_id: 'mc-1',
      target_head_public_id: 'mc-1',
    });
    await workspaceApi.performMerge('project-1', 'mr-1', {
      resolutions: [{ conflict_id: 'c1', choice: 'source' }],
      merge_base_public_id: 'base-1',
      source_head_public_id: 'src-1',
      target_head_public_id: 'tgt-1',
    });
    expect(http.post).toHaveBeenCalledWith('/projects/project-1/merge-requests/mr-1/merge', {
      resolutions: [{ conflict_id: 'c1', choice: 'source' }],
      merge_base_public_id: 'base-1',
      source_head_public_id: 'src-1',
      target_head_public_id: 'tgt-1',
    });
  });
});
