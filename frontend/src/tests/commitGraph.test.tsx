// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CommitGraph } from '../components/version-control/CommitGraph';
import { CommitSummary } from '../core/versionControl';

const root: CommitSummary = {
  id: 1, public_id: 'c-root', short_id: 'c-rootxx', message: 'root commit',
  state_hash: 'h', schema_version: '1.0', summary: null,
  author_email: 'a@x.com', created_at: '2026-08-01T00:00:00Z',
  parent_ids: [], parent_public_ids: [], is_merge: false,
  branch_public_ids: [], branch_names: ['main'],
} as any;

const a: CommitSummary = {
  id: 2, public_id: 'c-a', short_id: 'c-a', message: 'branch A commit',
  state_hash: 'h', schema_version: '1.0', summary: null,
  author_email: 'a@x.com', created_at: '2026-08-02T00:00:00Z',
  parent_ids: [1], parent_public_ids: ['c-root'], is_merge: false,
  branch_public_ids: [], branch_names: ['feature/a'],
} as any;

const b: CommitSummary = {
  id: 3, public_id: 'c-b', short_id: 'c-b', message: 'branch B commit',
  state_hash: 'h', schema_version: '1.0', summary: null,
  author_email: 'b@x.com', created_at: '2026-08-03T00:00:00Z',
  parent_ids: [1], parent_public_ids: ['c-root'], is_merge: false,
  branch_public_ids: [], branch_names: ['feature/b'],
} as any;

const merge: CommitSummary = {
  id: 4, public_id: 'c-merge', short_id: 'c-merge', message: 'merge commit',
  state_hash: 'h', schema_version: '1.0', summary: null,
  author_email: 'm@x.com', created_at: '2026-08-04T00:00:00Z',
  parent_ids: [3, 2], parent_public_ids: ['c-b', 'c-a'], is_merge: true,
  branch_public_ids: [], branch_names: ['main'],
} as any;

describe('CommitGraph', () => {
  it('渲染全部提交节点与父连线', () => {
    const { container } = render(
      <CommitGraph commits={[merge, b, a, root]} selectedPublicId={null} onSelect={vi.fn()} />
    );
    // 4 个节点按钮。
    expect(screen.getAllByRole('button')).toHaveLength(4);
    // SVG 边：merge→b、merge→a、b→root、a→root = 4 条 path。
    const paths = container.querySelectorAll('svg path');
    expect(paths.length).toBe(4);
  });

  it('merge 提交显示 merge 徽章', () => {
    render(<CommitGraph commits={[merge]} selectedPublicId={null} onSelect={vi.fn()} />);
    expect(screen.getByText('merge commit')).toBeTruthy();
    expect(screen.getByText('merge')).toBeTruthy();
  });

  it('点击节点触发 onSelect 并携带提交', () => {
    const onSelect = vi.fn();
    render(<CommitGraph commits={[merge, root]} selectedPublicId={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByLabelText(/root commit/));
    expect(onSelect).toHaveBeenCalledWith(root);
  });

  it('父提交不在列表时渲染省略标记', () => {
    // 只传 merge（父 b/a 不在列表），应出现省略标记。
    render(<CommitGraph commits={[merge]} selectedPublicId={null} onSelect={vi.fn()} />);
    expect(screen.getByText('…')).toBeTruthy();
  });

  it('选中节点带 aria-current', () => {
    render(<CommitGraph commits={[merge, root]} selectedPublicId="c-root" onSelect={vi.fn()} />);
    const selected = screen.getByLabelText(/root commit/);
    expect(selected.getAttribute('aria-current')).toBe('true');
  });
});
