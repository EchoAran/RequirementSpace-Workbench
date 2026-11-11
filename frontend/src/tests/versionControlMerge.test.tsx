import { renderWithEffects as render } from './renderWithEffects';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../lib/api', () => {
  return {
    workspaceApi: {
      getMergePreview: vi.fn(),
      performMerge: vi.fn(),
    },
  };
});

import { workspaceApi } from '../lib/api';
import { ConflictResolutionView } from '../components/version-control/ConflictResolutionView';

const mockConflict = {
  conflict_id: 'conflict-1',
  conflict_type: 'same_field_different_value',
  entity_type: 'feature',
  entity_uuid: 'feat-1',
  entity_name: '订单支付',
  path: 'description',
  parent_uuid: null,
  parent_type: null,
  base_value: 'base text',
  target_value: 'target text',
  source_value: 'source text',
  related_entity_type: null,
  related_entity_uuid: null,
  related_entity_name: null,
  choices: ['target', 'source'],
  resolved: false,
};

const mockPreview = {
  merge_base_public_id: 'base-1',
  source_head_public_id: 'src-1',
  target_head_public_id: 'tgt-1',
  conflict_count: 1,
  conflicts: [mockConflict],
  auto_merged_summary: { total_changed: 1, total_auto_merged: 0, total_conflicts: 1 },
};

describe('ConflictResolutionView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (workspaceApi.getMergePreview as ReturnType<typeof vi.fn>).mockResolvedValue(mockPreview);
  });

  it('渲染冲突队列、base/target/source 三列与进度', async () => {
    await render(
      <MemoryRouter>
        <ConflictResolutionView
          projectId="project-1"
          mrRef="mr-1"
          sourceBranchName="feature/pay"
          targetBranchName="main"
          onMerged={vi.fn()}
          onCancel={vi.fn()}
          onError={vi.fn()}
        />
      </MemoryRouter>
    );
    expect(await screen.findByText('订单支付')).toBeTruthy();
    expect(screen.getByText('base text')).toBeTruthy();
    expect(screen.getByText('target text')).toBeTruthy();
    expect(screen.getByText('source text')).toBeTruthy();
  });

  it('选择 keep-source 后合并按钮启用，点击调用 performMerge', async () => {
    const onMerged = vi.fn();
    await render(
      <MemoryRouter>
        <ConflictResolutionView
          projectId="project-1"
          mrRef="mr-1"
          sourceBranchName="feature/pay"
          targetBranchName="main"
          onMerged={onMerged}
          onCancel={vi.fn()}
          onError={vi.fn()}
        />
      </MemoryRouter>
    );
    await screen.findByText('订单支付');

    // 未解决时合并按钮禁用
    const mergeBtn = screen.getByText('合并到目标分支');
    expect((mergeBtn as HTMLButtonElement).disabled).toBe(true);

    // 选择 keep-source
    await act(async () => fireEvent.click(screen.getByText('保留来源分支')));

    // 全部解决后合并按钮启用
    expect((mergeBtn as HTMLButtonElement).disabled).toBe(false);

    (workspaceApi.performMerge as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: 'merged', merged_commit_public_id: 'mc-1', target_head_public_id: 'mc-1',
    });
    await act(async () => fireEvent.click(mergeBtn));

    expect(workspaceApi.performMerge).toHaveBeenCalledWith(
      'project-1', 'mr-1',
      expect.objectContaining({
        resolutions: expect.arrayContaining([
          expect.objectContaining({ conflict_id: 'conflict-1', choice: 'source' }),
        ]),
        merge_base_public_id: 'base-1',
        source_head_public_id: 'src-1',
        target_head_public_id: 'tgt-1',
      })
    );
    expect(onMerged).toHaveBeenCalled();
  });

  it('无冲突时显示无冲突提示', async () => {
    (workspaceApi.getMergePreview as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockPreview, conflict_count: 0, conflicts: [],
    });
    await render(
      <MemoryRouter>
        <ConflictResolutionView
          projectId="project-1"
          mrRef="mr-1"
          sourceBranchName="feature/pay"
          targetBranchName="main"
          onMerged={vi.fn()}
          onCancel={vi.fn()}
          onError={vi.fn()}
        />
      </MemoryRouter>
    );
    expect(await screen.findByText('此 MR 没有需要解决的冲突')).toBeTruthy();
  });

  it('手工编辑字段值后以 manual 选择提交', async () => {
    const onMerged = vi.fn();
    await render(
      <MemoryRouter>
        <ConflictResolutionView
          projectId="project-1"
          mrRef="mr-1"
          sourceBranchName="feature/pay"
          targetBranchName="main"
          onMerged={onMerged}
          onCancel={vi.fn()}
          onError={vi.fn()}
        />
      </MemoryRouter>
    );
    await screen.findByText('订单支付');

    const manualInput = screen.getByPlaceholderText('输入自定义值');
    await act(async () => fireEvent.change(manualInput, { target: { value: 'custom text' } }));
    await act(async () => fireEvent.click(screen.getByText('应用手工值')));

    (workspaceApi.performMerge as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: 'merged', merged_commit_public_id: 'mc-1', target_head_public_id: 'mc-1',
    });
    await act(async () => fireEvent.click(screen.getByText('合并到目标分支')));

    expect(workspaceApi.performMerge).toHaveBeenCalledWith(
      'project-1', 'mr-1',
      expect.objectContaining({
        resolutions: expect.arrayContaining([
          expect.objectContaining({ conflict_id: 'conflict-1', choice: 'manual', manual_value: 'custom text' }),
        ]),
        merge_base_public_id: 'base-1',
        source_head_public_id: 'src-1',
        target_head_public_id: 'tgt-1',
      })
    );
  });
});
