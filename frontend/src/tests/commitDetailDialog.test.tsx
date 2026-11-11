// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CommitDetailDialog } from '../components/version-control/CommitDetailDialog';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getCommitDetail: vi.fn(),
  },
}));

import { workspaceApi } from '../lib/api';

const mockDetail = {
  id: 1, public_id: 'c-1', short_id: 'c-1', message: 'feat: add payment',
  state_hash: 'h', schema_version: '1.0', summary: null,
  author_email: 'dev@x.com', created_at: '2026-08-01T00:00:00Z',
  parent_ids: [], parent_public_ids: [], is_merge: false,
  branch_public_ids: [], branch_names: ['main'],
  state: {
    actors: [
      { logical_uuid: 'act-1', name: 'Buyer', confirmation_status: 'confirmed' },
    ],
    features: [
      { logical_uuid: 'feat-1', name: 'Checkout', confirmation_status: 'ai_assumption' },
    ],
    scenarios: [], business_objects: [], flows: [], scopes: [],
  },
} as any;

describe('CommitDetailDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (workspaceApi.getCommitDetail as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail);
  });

  it('打开时加载提交详情并渲染实体分区', async () => {
    render(
      <MemoryRouter>
        <CommitDetailDialog projectId="p1" commitRef="c-1" open onClose={vi.fn()} />
      </MemoryRouter>
    );
    expect(await screen.findByText('提交快照')).toBeTruthy();
    expect(screen.getByText('feat: add payment')).toBeTruthy();
    expect(await screen.findByText(/参与者/)).toBeTruthy();
    expect(screen.getByText('Buyer')).toBeTruthy();
    expect(screen.getByText(/功能/)).toBeTruthy();
    expect(screen.getByText('Checkout')).toBeTruthy();
  });

  it('关闭按钮触发 onClose', async () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <CommitDetailDialog projectId="p1" commitRef="c-1" open onClose={onClose} />
      </MemoryRouter>
    );
    await screen.findByText('提交快照');
    fireEvent.click(screen.getByLabelText('关闭'));
    expect(onClose).toHaveBeenCalled();
  });

  it('无 state 时显示空提示', async () => {
    (workspaceApi.getCommitDetail as ReturnType<typeof vi.fn>).mockResolvedValue({ ...mockDetail, state: null });
    render(
      <MemoryRouter>
        <CommitDetailDialog projectId="p1" commitRef="c-1" open onClose={vi.fn()} />
      </MemoryRouter>
    );
    expect(await screen.findByText('该快照无模型数据')).toBeTruthy();
  });
});
