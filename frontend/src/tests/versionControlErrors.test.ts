import { describe, it, expect } from 'vitest';
import { extractVcError, extractActionError } from '../core/versionControlErrors';

describe('extractVcError', () => {
  it('409 head_changed 映射到 headChanged 并携带 compareRef', () => {
    const e = { status: 409, detail: { code: 'head_changed', compare_ref: 'commit:newhead' } };
    const { token, info } = extractVcError(e);
    expect(token).toBe('versionControl.mergeRequest.headChanged');
    expect(info.compareRef).toBe('commit:newhead');
  });

  it('409 merge_conflict 映射到 mergeConflict', () => {
    const { token, info } = extractVcError({ status: 409, detail: { code: 'merge_conflict', conflict_ids: ['c1'] } });
    expect(token).toBe('versionControl.mergeRequest.errors.mergeConflict');
    expect(info.code).toBe('merge_conflict');
  });

  it('400 merge_blocked 映射到 blocked 并携带 reasons', () => {
    const e = { status: 400, detail: { code: 'merge_blocked', reasons: ['missing_approval'] } };
    const { token, info } = extractVcError(e);
    expect(token).toBe('versionControl.mergeRequest.errors.blocked');
    expect(info.reasons).toEqual(['missing_approval']);
  });

  it('403 映射到 forbidden', () => {
    const { token } = extractVcError({ status: 403, detail: {} });
    expect(token).toBe('versionControl.mergeRequest.errors.forbidden');
  });

  it('其他错误回退到 mergeFailed', () => {
    const { token } = extractVcError({ status: 500, detail: {} });
    expect(token).toBe('versionControl.mergeRequest.mergeFailed');
  });
});

describe('extractActionError', () => {
  it('403 → forbidden, 409 → staleState, 其他 → mergeFailed', () => {
    expect(extractActionError({ status: 403 })).toBe('versionControl.mergeRequest.errors.forbidden');
    expect(extractActionError({ status: 409 })).toBe('versionControl.mergeRequest.errors.staleState');
    expect(extractActionError({ status: 500 })).toBe('versionControl.mergeRequest.mergeFailed');
  });
});
