// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getSemanticDiff: vi.fn().mockResolvedValue({
      summary: { by_type: {}, total_added: 0, total_removed: 0, total_modified: 0 },
      entries: [], total: 0, limit: 200, offset: 0,
    }),
    listBranches: vi.fn().mockResolvedValue([]),
    listCommits: vi.fn().mockResolvedValue({ commits: [], total: 0, limit: 50, offset: 0 }),
  },
}));

import { VersionControlGuidance } from '../components/version-control/VersionControlGuidance';

describe('VersionControlGuidance', () => {
  it('渲染五张引导卡（基线/建分支/main 保护/MR 审批/不支持功能）', () => {
    render(<MemoryRouter><VersionControlGuidance /></MemoryRouter>);
    expect(screen.getByText('版本控制引导')).toBeTruthy();
    expect(screen.getByText('什么是基线版本')).toBeTruthy();
    expect(screen.getByText('何时创建分支')).toBeTruthy();
    expect(screen.getByText('main 分支为什么受保护')).toBeTruthy();
    expect(screen.getByText('合并请求审批规则')).toBeTruthy();
    expect(screen.getByText('暂不支持的 Git 功能')).toBeTruthy();
  });

  it('不支持功能卡片说明 rebase/cherry-pick 等首期不提供', () => {
    render(<MemoryRouter><VersionControlGuidance /></MemoryRouter>);
    expect(screen.getByText(/rebase/)).toBeTruthy();
    expect(screen.getByText(/cherry-pick/)).toBeTruthy();
  });
});
