import { RequirementSpaceIR } from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json();
}

export const workspaceApi = {
  health: () => request<{ status: string }>('/api/health'),
  list: () => request<{ id: string; name: string; idea: string; updatedAt: string; status: string; issueCount: number; nodeCount: number; }[]>('/api/workspaces'),
  getDefault: () => request<RequirementSpaceIR>('/api/workspaces/default'),
  getById: (id: string) => request<RequirementSpaceIR>(`/api/workspaces/${id}`),
  bootstrap: (prompt: string) =>
    request<RequirementSpaceIR>('/api/workspaces/bootstrap', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    }),
  analyzePrompt: (prompt: string) =>
    request<{
      taskType: string;
      goals: string[];
      actors: string[];
      flows: string[];
      objects: string[];
      questions: string[];
    }>('/api/prompts/analyze', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    }),
  patchNode: (workspaceId: string, nodeId: string, updates: Record<string, unknown>) =>
    request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/nodes/${nodeId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),
  patchNodeStatus: (workspaceId: string, nodeId: string, status: string) =>
    request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/nodes/${nodeId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  patchNodeScope: (workspaceId: string, nodeId: string, scopeStatus: string) =>
    request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/nodes/${nodeId}/scope`, {
      method: 'PATCH',
      body: JSON.stringify({ scopeStatus }),
    }),
  patchIssueStatus: (workspaceId: string, issueId: string, status: string) =>
    request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/issues/${issueId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  generateCandidateForIssue: (workspaceId: string, issueId: string) =>
    request<{ result: Record<string, string>; workspace: RequirementSpaceIR }>(
      `/api/workspaces/${workspaceId}/issues/${issueId}/generate-candidate`,
      { method: 'POST' }
    ),
  acceptChoice: (workspaceId: string, choiceId: string) =>
    request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/choices/${choiceId}/accept`, {
      method: 'POST',
    }),
  rejectChoice: (workspaceId: string, choiceId: string) =>
    request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/choices/${choiceId}/reject`, {
      method: 'POST',
    }),
  diagnose: (workspaceId: string, scope?: unknown) =>
    request<{ result: Record<string, unknown>; workspace: RequirementSpaceIR }>(
      `/api/workspaces/${workspaceId}/diagnose`,
      {
        method: 'POST',
        body: JSON.stringify({ scope: scope || null }),
      }
    ),
  applyPatch: (workspaceId: string, patch: Record<string, unknown>) =>
    request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/patch`, {
      method: 'POST',
      body: JSON.stringify(patch),
    }),
  createIssue: (workspaceId: string, payload: Record<string, unknown>) =>
    request<{ issueId: string; workspace: RequirementSpaceIR }>(`/api/workspaces/${workspaceId}/issues`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  addChoiceToGroup: (workspaceId: string, choiceGroupId: string, payload: Record<string, unknown>) =>
    request<{ choiceId: string; workspace: RequirementSpaceIR }>(
      `/api/workspaces/${workspaceId}/choice-groups/${choiceGroupId}/choices`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),
  exportWorkspace: (workspaceId: string) => request<RequirementSpaceIR>(`/api/workspaces/${workspaceId}/export`),
};
