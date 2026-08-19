// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { CompareSelector } from '../components/version-control/CompareSelector';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    listCommits: vi.fn().mockResolvedValue({
      commits: [
        { public_id: 'c-1', short_id: 'c-1', message: 'first', is_merge: false },
        { public_id: 'c-2', short_id: 'c-2', message: 'second', is_merge: true },
      ],
      total: 2, limit: 200, offset: 0,
    }),
  },
}));

function seedBranches() {
  useWorkspaceStore.setState({
    branches: [
      { id: 1, public_id: 'main', name: 'main', is_protected: true },
      { id: 2, public_id: 'feature-a', name: 'feature/a', is_protected: false },
    ] as any,
  });
}

describe('CompareSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedBranches();
  });

  it('渲染基准/目标选择器与交换按钮', () => {
    render(<MemoryRouter><CompareSelector projectId="p1" onChange={vi.fn()} /></MemoryRouter>);
    expect(screen.getByRole('button', { name: 'swap' })).toBeTruthy();
    // 两个 kind 下拉 + 开始比较按钮。
    expect(screen.getAllByRole('combobox').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('变更对比')).toBeTruthy();
  });

  it('选择 commit 后 Apply 携带 commit: 前缀的 ref', async () => {
    const onChange = vi.fn();
    render(<MemoryRouter><CompareSelector projectId="p1" onChange={onChange} /></MemoryRouter>);
    // 基准选 commit 类，值选 c-1。
    fireEvent.change(screen.getByLabelText('基准 基准'), { target: { value: 'commit' } });
    await waitFor(() => expect(screen.getByLabelText('基准 value').querySelector('option[value="c-1"]')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('基准 value'), { target: { value: 'c-1' } });
    fireEvent.click(screen.getByText('变更对比'));
    expect(onChange).toHaveBeenCalledWith('commit:c-1', 'workspace:main');
  });

  it('交换按钮调换 base/target', async () => {
    const onChange = vi.fn();
    render(<MemoryRouter><CompareSelector projectId="p1" onChange={onChange} /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('基准 基准'), { target: { value: 'commit' } });
    await waitFor(() => expect(screen.getByLabelText('基准 value').querySelector('option[value="c-1"]')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('基准 value'), { target: { value: 'c-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'swap' }));
    fireEvent.click(screen.getByText('变更对比'));
    // 交换后 base=workspace, target=commit:c-1。
    expect(onChange).toHaveBeenCalledWith('workspace:main', 'commit:c-1');
  });

  it('从 URL base_ref/target_ref 初始化回读', () => {
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <CompareSelector
          projectId="p1"
          baseRef="commit:c-1"
          targetRef="branch:feature-a"
          onChange={onChange}
        />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByText('变更对比'));
    expect(onChange).toHaveBeenCalledWith('commit:c-1', 'branch:feature-a');
  });
});
