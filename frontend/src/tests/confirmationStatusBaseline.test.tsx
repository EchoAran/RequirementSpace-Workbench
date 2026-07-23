import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { StatusBadge } from '../components/shared/StatusBadge';
import { NodeStatusToText } from '../core/presentationLabels';

describe('confirmationStatusBaseline - StatusBadge rendering', () => {
  it('renders confirmed state correctly', () => {
    render(<StatusBadge status="confirmed" />);
    const badge = screen.getByText(NodeStatusToText.confirmed);
    expect(badge).toBeDefined();
    expect(badge.className).toContain('text-emerald-700');
  });

  it('renders needs_confirmation state correctly', () => {
    render(<StatusBadge status="needs_confirmation" />);
    const badge = screen.getByText(NodeStatusToText.needs_confirmation);
    expect(badge).toBeDefined();
    expect(badge.className).toContain('text-amber-700');
  });

  it('renders ai_assumption state correctly', () => {
    render(<StatusBadge status="ai_assumption" />);
    const badge = screen.getByText(NodeStatusToText.ai_assumption);
    expect(badge).toBeDefined();
    expect(badge.className).toContain('text-indigo-700');
  });
});
