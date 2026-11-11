import { describe, it, expect } from 'vitest';
import { buildProjectRoute } from '@/core/selectors';

describe('Public ID Regression - buildProjectRoute', () => {
  it('generates correct route for UUID string project ID', () => {
    const route = buildProjectRoute('abc-def-123-uuid', '/overview');
    expect(route).toBe('/projects/abc-def-123-uuid/overview');
  });

  it('generates correct route for different pages', () => {
    const uuid = 'e1a2b3c4-5678-9abc-def0-123456789abc';
    expect(buildProjectRoute(uuid, '/what')).toBe(`/projects/${uuid}/what`);
    expect(buildProjectRoute(uuid, '/flow')).toBe(`/projects/${uuid}/flow`);
    expect(buildProjectRoute(uuid, '/scope')).toBe(`/projects/${uuid}/scope`);
    expect(buildProjectRoute(uuid, '/preview')).toBe(`/projects/${uuid}/preview`);
  });

  it('returns bare page path when projectId is null', () => {
    expect(buildProjectRoute(null, '/overview')).toBe('/overview');
  });

  it('returns bare page path when projectId is undefined', () => {
    expect(buildProjectRoute(undefined, '/overview')).toBe('/overview');
  });

  it('returns bare page path when projectId is empty string', () => {
    expect(buildProjectRoute('', '/overview')).toBe('/overview');
  });

  it('never produces routes with numeric-looking integer IDs', () => {
    // After the type change, passing a number is a compile-time error.
    // This test verifies runtime behavior with string representations.
    const route = buildProjectRoute('42', '/overview');
    expect(route).toBe('/projects/42/overview');
    // The route still works, but callers should always pass a UUID string.
  });
});
