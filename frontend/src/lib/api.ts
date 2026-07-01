import {
  RequirementSpace,
  WorkspaceListItem,
  ProjectCreationDraft,
  ProjectCreationConfirmResponse,
  ProjectCreationDiscardResponse,
  ProjectCreationChoiceGroup,
  ProjectCreationChoiceItem,
  ProjectCreationChoiceGroupDeferResponse,
  ProjectMember,
} from '@/core/schema';
import { http } from './http';

export const workspaceApi = {
  healthCheck: async () => {
    return http.get<{ status: string; message: string }>('/health');
  },
  list: async (): Promise<WorkspaceListItem[]> => {
    return http.get<WorkspaceListItem[]>('/projects');
  },
  getById: async (id: string | number): Promise<RequirementSpace> => {
    return http.get<RequirementSpace>(`/projects/${id}`);
  },
  delete: async (id: string | number): Promise<void> => {
    await http.delete<{ project_id: string; message: string }>(`/projects/${id}`);
  },
  deletePerceptionSlot: async (projectId: string): Promise<any> => {
    return http.delete<any>(`/projects/${projectId}/perception-slot`);
  },
  updateProject: async (projectId: string, payload: { name: string; description: string }): Promise<any> => {
    return http.put<any>(`/projects/${projectId}`, payload);
  },
  unlockStage: async (projectId: string, stage: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/unlock-stage`, { stage });
  },
  /** 鏇存柊浠绘剰鑺傜偣鐨勭‘璁ょ姸鎬侊紙ai_assumption / needs_confirmation / confirmed锛?*/
  updateNodeConfirmationStatus: async (
    projectId: string,
    nodeKind: string,
    nodeId: number,
    confirmationStatus: string,
  ): Promise<void> => {
    await http.patch(`/projects/${projectId}/node-status`, {
      node_kind: nodeKind,
      node_id: nodeId,
      confirmation_status: confirmationStatus,
    });
  },
  /** 鎵归噺鏇存柊涓€缁勮妭鐐圭殑纭鐘舵€?*/
  batchUpdateNodeConfirmationStatus: async (
    projectId: string,
    nodes: Array<{ node_kind: string; node_id: number; confirmation_status?: string }>,
    confirmationStatus: string,
  ): Promise<any> => {
    return http.patch<any>(`/projects/${projectId}/node-status/batch`, {
      nodes: nodes.map((node) => ({
        ...node,
        confirmation_status: node.confirmation_status || confirmationStatus,
      })),
      confirmation_status: confirmationStatus,
    });
  },
  createBlankProject: async (payload: { user_requirements: string; project_name?: string; project_description?: string }): Promise<ProjectCreationConfirmResponse> => {
    return http.post<ProjectCreationConfirmResponse>('/blank_projects', payload);
  },
  createProjectCreationDraft: async (payload: { user_requirements: string; project_name?: string; project_description?: string }): Promise<ProjectCreationDraft> => {
    return http.post<ProjectCreationDraft>('/project_creation_drafts', payload);
  },
  regenerateProjectCreationDraft: async (draftId: string, feedback?: string): Promise<ProjectCreationDraft> => {
    return http.post<ProjectCreationDraft>(`/project_creation_drafts/${draftId}/regenerate`, { user_feedback: feedback });
  },
  confirmProjectCreationDraft: async (draftId: string): Promise<ProjectCreationConfirmResponse> => {
    return http.post<ProjectCreationConfirmResponse>(`/project_creation_drafts/${draftId}/confirm`);
  },
  discardProjectCreationDraft: async (draftId: string): Promise<ProjectCreationDiscardResponse> => {
    return http.delete<ProjectCreationDiscardResponse>(`/project_creation_drafts/${draftId}`);
  },
  createActor: async (projectId: string, payload: { name: string; description: string }) => {
    return http.post<any>(`/projects/${projectId}/actors`, payload);
  },
  updateActor: async (projectId: string, actorId: number, payload: { name?: string; description?: string; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/actors/${actorId}`, payload);
  },
  deleteActor: async (projectId: string, actorId: number) => {
    return http.delete<any>(`/projects/${projectId}/actors/${actorId}`);
  },
  createFeature: async (projectId: string, payload: { name: string; description: string; parent_id: number | null }) => {
    return http.post<any>(`/projects/${projectId}/features`, payload);
  },
  updateFeature: async (projectId: string, featureId: number, payload: { name?: string; description?: string; actor_ids?: number[]; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/features/${featureId}`, payload);
  },
  deleteFeature: async (projectId: string, featureId: number) => {
    return http.delete<any>(`/projects/${projectId}/features/${featureId}`);
  },
  createScenario: async (projectId: string, payload: { feature_id: number; actor_id: number; name: string; content: string }) => {
    return http.post<any>(`/projects/${projectId}/scenarios`, payload);
  },
  updateScenario: async (projectId: string, scenarioId: number, payload: { name?: string; content?: string; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/scenarios/${scenarioId}`, payload);
  },
  deleteScenario: async (projectId: string, scenarioId: number) => {
    return http.delete<any>(`/projects/${projectId}/scenarios/${scenarioId}`);
  },
  createAcceptanceCriterion: async (projectId: string, scenarioId: number, payload: { content: string; position?: number }) => {
    return http.post<any>(`/projects/${projectId}/scenarios/${scenarioId}/acceptance_criteria`, payload);
  },
  updateAcceptanceCriterion: async (projectId: string, scenarioId: number, acId: number, payload: { content: string; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/scenarios/${scenarioId}/acceptance_criteria/${acId}`, payload);
  },
  deleteAcceptanceCriterion: async (projectId: string, scenarioId: number, acId: number) => {
    return http.delete<any>(`/projects/${projectId}/scenarios/${scenarioId}/acceptance_criteria/${acId}`);
  },
  createBusinessObject: async (projectId: string, payload: { name: string; description: string }) => {
    return http.post<any>(`/projects/${projectId}/business_objects`, payload);
  },
  updateBusinessObject: async (projectId: string, boId: number, payload: { name?: string; description?: string; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/business_objects/${boId}`, payload);
  },
  deleteBusinessObject: async (projectId: string, boId: number) => {
    return http.delete<any>(`/projects/${projectId}/business_objects/${boId}`);
  },
  createBusinessObjectAttribute: async (projectId: string, boId: number, payload: { name: string; description: string; data_type: string; example: string }) => {
    return http.post<any>(`/projects/${projectId}/business_objects/${boId}/attributes`, payload);
  },
  updateBusinessObjectAttribute: async (projectId: string, boId: number, attrId: number, payload: { name?: string; description?: string; data_type?: string; example?: string; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/business_objects/${boId}/attributes/${attrId}`, payload);
  },
  deleteBusinessObjectAttribute: async (projectId: string, boId: number, attrId: number) => {
    return http.delete<any>(`/projects/${projectId}/business_objects/${boId}/attributes/${attrId}`);
  },
  createFlow: async (projectId: string, payload: { name: string; description: string; feature_ids?: number[] }) => {
    return http.post<any>(`/projects/${projectId}/flows`, payload);
  },
  updateFlow: async (projectId: string, flowId: number, payload: { name?: string; description?: string; feature_ids?: number[]; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/flows/${flowId}`, payload);
  },
  deleteFlow: async (projectId: string, flowId: number) => {
    return http.delete<any>(`/projects/${projectId}/flows/${flowId}`);
  },
  createFlowStep: async (projectId: string, flowId: number, payload: { name: string; description: string; step_type: string; actor_ids?: number[]; input_business_object_ids?: number[]; output_business_object_ids?: number[]; next_step_ids?: number[] }) => {
    return http.post<any>(`/projects/${projectId}/flows/${flowId}/steps`, payload);
  },
  updateFlowStep: async (projectId: string, flowId: number, stepId: number, payload: { name?: string; description?: string; step_type?: string; actor_ids?: number[]; input_business_object_ids?: number[]; output_business_object_ids?: number[]; next_step_ids?: number[]; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/flows/${flowId}/steps/${stepId}`, payload);
  },
  deleteFlowStep: async (projectId: string, flowId: number, stepId: number) => {
    return http.delete<any>(`/projects/${projectId}/flows/${flowId}/steps/${stepId}`);
  },
  reorderFlowSteps: async (projectId: string, flowId: number, stepIds: number[]) => {
    return http.put<any>(`/projects/${projectId}/flows/${flowId}/steps/reorder`, { step_ids: stepIds });
  },
  updateScope: async (projectId: string, featureId: number, payload: { status: string; reason: string; positive_summary?: string | null; negative_summary?: string | null; last_seen_updated_at?: string }) => {
    return http.put<any>(`/projects/${projectId}/features/${featureId}/scope`, payload);
  },
  createActorGenerationDraft: async (projectId: string): Promise<any> => {
    return http.post<any>('/actor_generation_drafts', { project_id: projectId });
  },
  confirmActorGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/actor_generation_drafts/${draftId}/confirm`);
  },
  createFeatureGenerationDraft: async (projectId: string): Promise<any> => {
    return http.post<any>('/feature_generation_drafts', { project_id: projectId });
  },
  confirmFeatureGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/feature_generation_drafts/${draftId}/confirm`);
  },
  createFlowGenerationDraft: async (projectId: string): Promise<any> => {
    return http.post<any>('/flow_generation_drafts', { project_id: projectId });
  },
  confirmFlowGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/flow_generation_drafts/${draftId}/confirm`);
  },
  createScenarioGenerationDraft: async (projectId: string, featureId?: number): Promise<any> => {
    if (featureId !== undefined && featureId !== null) {
      return http.post<any>('/scenario_generation_drafts/single', {
        project_id: projectId,
        feature_id: featureId,
      });
    }
    return http.post<any>('/scenario_generation_drafts/full', {
      project_id: projectId,
    });
  },
  confirmScenarioGenerationDraft: async (draftId: string, payload: { generate_acceptance_criteria: boolean }): Promise<any> => {
    return http.post<any>(`/scenario_generation_drafts/${draftId}/confirm`, payload);
  },
  createAcceptanceCriteriaGenerationDraft: async (projectId: string, scenarioIds?: number[]): Promise<any> => {
    if (!scenarioIds || scenarioIds.length === 0) {
      return http.post<any>('/acceptance_criteria_generation_drafts/full', {
        project_id: projectId,
      });
    }
    if (scenarioIds.length === 1) {
      return http.post<any>('/acceptance_criteria_generation_drafts/single', {
        project_id: projectId,
        scenario_id: scenarioIds[0],
      });
    }
    return http.post<any>('/acceptance_criteria_generation_drafts/batch', {
      project_id: projectId,
      scenario_ids: scenarioIds,
    });
  },
  confirmAcceptanceCriteriaGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/acceptance_criteria_generation_drafts/${draftId}/confirm`);
  },
  createScopeGenerationDraft: async (projectId: string): Promise<any> => {
    return http.post<any>('/scope_generation_drafts', { project_id: projectId });
  },
  confirmScopeGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/scope_generation_drafts/${draftId}/confirm`);
  },
  discardDraft: async (draftId: string, draftType?: string | null): Promise<any> => {
    const paths: Record<string, string> = {
      project: `/project_creation_drafts/${draftId}`,
      actor: `/actor_generation_drafts/${draftId}`,
      feature: `/feature_generation_drafts/${draftId}`,
      flow: `/flow_generation_drafts/${draftId}`,
      scenario: `/scenario_generation_drafts/${draftId}`,
      ac: `/acceptance_criteria_generation_drafts/${draftId}`,
      scope: `/scope_generation_drafts/${draftId}`,
    };
    return http.delete<any>(paths[draftType || 'actor'] || paths.actor);
  },
  regenerateActorGenerationDraft: async (draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/actor_generation_drafts/${draftId}/regenerate`, { user_feedback: feedback });
  },
  regenerateFeatureGenerationDraft: async (draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/feature_generation_drafts/${draftId}/regenerate`, { user_feedback: feedback });
  },
  regenerateFlowGenerationDraft: async (draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/flow_generation_drafts/${draftId}/regenerate`, { user_feedback: feedback });
  },
  regenerateScenarioGenerationDraft: async (draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/scenario_generation_drafts/${draftId}/regenerate`, { user_feedback: feedback });
  },
  regenerateAcceptanceCriteriaGenerationDraft: async (draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/acceptance_criteria_generation_drafts/${draftId}/regenerate`, { user_feedback: feedback });
  },
  regenerateScopeGenerationDraft: async (draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/scope_generation_drafts/${draftId}/regenerate`, { user_feedback: feedback });
  },
  exportMarkdown: async (projectId: string): Promise<string> => {
    return http.get<string>(`/projects/${projectId}/export/markdown`);
  },
  exportJson: async (projectId: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/export/json`);
  },
  refineUserRequirements: async (projectId: string, feedback: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/user-requirements/refine`, {
      user_feedback: feedback
    });
  },
  impactPreview: async (projectId: string, featureId?: number, nextStatus?: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/impact-preview`, {
      feature_id: featureId,
      next_status: nextStatus,
    });
  },
  generatePrototypePreview: async (projectId: string, forceRegenerate = true): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/prototype-preview`, {
      force_regenerate: forceRegenerate,
    });
  },
  getLatestPrototypePreview: async (projectId: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/prototype-preview/latest`);
  },
  listAuditLogs: async (projectId: string): Promise<any[]> => {
    return http.get<any[]>(`/projects/${projectId}/audit-logs`);
  },
  listFindings: async (projectId: string, params: { stage?: string; view?: string; action?: string }): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/findings`, params);
  },
  updateFindingStatus: async (projectId: string, findingId: string, status: string): Promise<any> => {
    return http.put<any>(`/projects/${projectId}/findings/status`, {
      finding_id: findingId,
      status,
    });
  },
  resolveIssue: async (projectId: string, payload: { issue_id?: string; issue_code: string; stage?: string; target: any | null; metadata?: any }): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/issues/resolve`, payload);
  },
  getNextSuggestion: async (projectId: string, stage: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/next-suggestion`, { stage });
  },
  rediagnoseNextSuggestion: async (projectId: string, stage: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/next-suggestion/rediagnose`, { stage });
  },
  createSlotFillingDraft: async (projectId: string, perceptionJobId: number, fillerKind: string): Promise<any> => {
    const kind = fillerKind === 'ac' || fillerKind === 'acceptanceCriteria' || fillerKind === 'acceptance_criterion'
      ? 'acceptance_criteria'
      : fillerKind;
    return http.post<any>(`/perception_slot_filling_drafts/${kind}`, {
      project_id: projectId,
      perception_job_id: perceptionJobId,
    });
  },
  confirmSlotFillingDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/perception_slot_filling_drafts/${draftId}/confirm`);
  },
  discardSlotFillingDraft: async (draftId: string): Promise<any> => {
    return http.delete<any>(`/perception_slot_filling_drafts/${draftId}`);
  },
  regenerateSlotFillingDraft: async (draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/perception_slot_filling_drafts/${draftId}/regenerate`, {
      user_feedback: feedback,
    });
  },
  // Phase 3: Generation choice group (actor, scenario, etc.)
  createGenerationChoiceGroup: async (payload: {
    project_id: string;
    generation_type: string;
    target?: any;
    candidate_count?: number;
    user_feedback?: string | null;
  }): Promise<any> => {
    return http.post<any>('/generation_choice_groups', payload);
  },

  // Phase 3: Discard a project-level choice group
  discardChoiceGroup: async (projectId: string, groupId: number): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/choice_groups/${groupId}/discard`);
  },

  listChoiceGroups: async (projectId: string, status?: string): Promise<any[]> => {
    return http.get<any[]>(`/projects/${projectId}/choice_groups`, { status });
  },
  acceptChoice: async (projectId: string, choiceId: number, force = false): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/choices/${choiceId}/accept`, { force });
  },
  rejectChoice: async (projectId: string, choiceId: number): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/choices/${choiceId}/reject`);
  },
  // Phase 5b: Regenerate choice group or single choice
  regenerateChoiceGroup: async (projectId: string, groupId: number, feedback?: string): Promise<any> => {
    const query = feedback ? `?feedback=${encodeURIComponent(feedback)}` : '';
    return http.post<any>(`/projects/${projectId}/choice_groups/${groupId}/regenerate${query}`);
  },
  regenerateChoice: async (projectId: string, choiceId: number, feedback?: string): Promise<any> => {
    const query = feedback ? `?feedback=${encodeURIComponent(feedback)}` : '';
    return http.post<any>(`/projects/${projectId}/choices/${choiceId}/regenerate${query}`);
  },
  skipKano: async (projectId: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/scope/skip_kano`);
  },
  resetKano: async (projectId: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/scope/reset_kano`);
  },
  getActiveShadowDraft: async (projectId: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/preview-shadow-drafts/active`);
  },
  prepareShadowDraft: async (projectId: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/preview-shadow-drafts`);
  },
  getShadowDraft: async (projectId: string, draftId: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}`);
  },
  discardShadowDraft: async (projectId: string, draftId: string): Promise<any> => {
    return http.delete<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}`);
  },
  commitShadowDraft: async (projectId: string, draftId: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}/commit`);
  },
  regenerateShadowDraft: async (projectId: string, draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}/regenerate`, {
      user_feedback: feedback,
    });
  },
  // AI Conversational Add Session (Phase 3)
  createAIAddSession: async (payload: {
    project_id: string;
    target_type: string;
    anchor?: Record<string, any>;
  }): Promise<any> => {
    return http.post<any>('/ai_add_sessions', payload);
  },
  getAIAddSession: async (sessionId: number): Promise<any> => {
    return http.get<any>(`/ai_add_sessions/${sessionId}`);
  },
  getAIAddSessionMessages: async (sessionId: number): Promise<any> => {
    return http.get<any>(`/ai_add_sessions/${sessionId}/messages`);
  },
  sendAIAddSessionMessage: async (sessionId: number, content: string): Promise<any> => {
    return http.post<any>(`/ai_add_sessions/${sessionId}/messages`, { content });
  },
  generateAIAddObjectDraft: async (sessionId: number): Promise<any> => {
    return http.post<any>(`/ai_add_sessions/${sessionId}/generate_draft`);
  },
  confirmAIAddObjectDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/ai_object_generation_drafts/${draftId}/confirm`);
  },
  discardAIAddObjectDraft: async (draftId: string): Promise<any> => {
    return http.delete<any>(`/ai_object_generation_drafts/${draftId}`);
  },

  // AI Edit session helper
  createAIEditSession: async (projectId: string, targetId: number, targetType: string): Promise<any> => {
    return http.post<any>('/ai_add_sessions', {
      project_id: projectId,
      target_type: `edit_${targetType}`,
      anchor: { target_id: targetId, target_type: targetType },
    });
  },

  // Project Interview
  interviewChat: async (messages: { role: string; content: string }[]): Promise<any> => {
    return http.post<any>('/project_interview/chat', { messages });
  },
  completeInterview: async (name: string, description: string, userRequirements: string): Promise<any> => {
    return http.post<any>('/project_interview/complete', {
      name,
      description,
      user_requirements: userRequirements,
    });
  },

  // AI Explain (Q&A)
  explainAI: async (projectId: string, scope: any, question: string): Promise<any> => {
    return http.post<any>('/ai/explain', {
      project_id: projectId,
      scope,
      question,
    });
  },

  // Issue Repair Drafts (P2)
  confirmRepairDraft: async (projectId, draftId) => {
    return http.post(`/projects/${projectId}/issue_repair_drafts/${draftId}/confirm`);
  },
  discardRepairDraft: async (projectId, draftId) => {
    return http.post(`/projects/${projectId}/issue_repair_drafts/${draftId}/discard`);
  },
  regenerateRepairDraft: async (projectId, draftId) => {
    return http.post(`/projects/${projectId}/issue_repair_drafts/${draftId}/regenerate`);
  },

  // 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
  // Phase 2: Project Creation Choice Group API
  // 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
  createProjectCreationChoiceGroup: async (payload: {
    user_requirements: string;
    candidate_count?: number;
    user_feedback?: string;
  }): Promise<ProjectCreationChoiceGroup> => {
    return http.post<ProjectCreationChoiceGroup>('/project_creation_choice_groups', payload);
  },

  getProjectCreationChoiceGroup: async (groupId: string): Promise<ProjectCreationChoiceGroup> => {
    return http.get<ProjectCreationChoiceGroup>(`/project_creation_choice_groups/${groupId}`);
  },

  listOpenProjectCreationChoiceGroups: async (): Promise<ProjectCreationChoiceGroup[]> => {
    return http.get<ProjectCreationChoiceGroup[]>('/project_creation_choice_groups', { status: 'open' });
  },

  acceptProjectCreationChoice: async (groupId: string, choiceId: string): Promise<ProjectCreationConfirmResponse> => {
    return http.post<ProjectCreationConfirmResponse>(
      `/project_creation_choice_groups/${groupId}/choices/${choiceId}/accept`
    );
  },

  discardProjectCreationChoiceGroup: async (groupId: string): Promise<{ message: string; group_id: string }> => {
    return http.post<{ message: string; group_id: string }>(
      `/project_creation_choice_groups/${groupId}/discard`
    );
  },

  deferProjectCreationChoiceGroup: async (groupId: string): Promise<ProjectCreationChoiceGroupDeferResponse> => {
    return http.post<ProjectCreationChoiceGroupDeferResponse>(
      `/project_creation_choice_groups/${groupId}/defer`
    );
  },

  listProjectMembers: async (projectId: string): Promise<ProjectMember[]> => {
    return http.get<ProjectMember[]>(`/projects/${projectId}/members`);
  },

  addProjectMember: async (projectId: string, email: string, role: string): Promise<ProjectMember> => {
    return http.post<ProjectMember>(`/projects/${projectId}/members`, { email, role });
  },

  updateProjectMember: async (projectId: string, memberId: number, role: string, status: string): Promise<ProjectMember> => {
    return http.patch<ProjectMember>(`/projects/${projectId}/members/${memberId}`, { role, status });
  },

  removeProjectMember: async (projectId: string, memberId: number): Promise<void> => {
    await http.delete(`/projects/${projectId}/members/${memberId}`);
  },

  createConfirmationTask: async (
    projectId: string,
    payload: {
      nodeKind: string;
      nodeId: number;
      assignedToUserId: number;
      title?: string;
      description?: string;
      priority?: string;
      dueAt?: string;
    }
  ): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/tasks/confirm-node`, payload);
  },

  listProjectTasks: async (
    projectId: string,
    params?: {
      status?: string;
      taskType?: string;
      assignedToUserId?: number;
      createdByUserId?: number;
      targetType?: string;
      targetId?: string;
    }
  ): Promise<any[]> => {
    return http.get<any[]>(`/projects/${projectId}/tasks`, params);
  },

  listMyTasks: async (
    params?: {
      role?: string;
      status?: string;
      taskType?: string;
      projectId?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<any[]> => {
    return http.get<any[]>('/me/tasks', params);
  },

  decideTask: async (
    projectId: string,
    taskId: number,
    payload: {
      decision: string;
      decisionNote?: string;
    }
  ): Promise<any> => {
    return http.patch<any>(`/projects/${projectId}/tasks/${taskId}/decision`, payload);
  },

  cancelTask: async (
    projectId: string,
    taskId: number
  ): Promise<any> => {
    return http.patch<any>(`/projects/${projectId}/tasks/${taskId}/cancel`);
  },

  createBatchConfirmTask: async (
    projectId: string,
    payload: {
      targets: Array<{ nodeKind: string; nodeId: number }>;
      assignedToUserId: number;
      title?: string;
      description?: string;
      priority?: string;
      dueAt?: string;
    }
  ): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/tasks/confirm-nodes`, payload);
  },

  getProjectConfirmationSummary: async (
    projectId: string
  ): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/confirmation-summary`);
  },

  listNotifications: async (): Promise<any[]> => {
    return http.get<any[]>('/me/notifications');
  },

  markNotificationsRead: async (notificationIds?: number[]): Promise<any> => {
    return http.put<any>('/me/notifications/read', { notificationIds });
  },

  getProjectLLMConfig: async (projectId: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/llm-config`);
  },

  updateProjectLLMConfig: async (
    projectId: string,
    payload: { api_url: string; api_key: string; model_name: string }
  ): Promise<any> => {
    // Convert to snake_case payload for backend
    return http.put<any>(`/projects/${projectId}/llm-config`, payload);
  },

  deleteProjectLLMConfig: async (projectId: string): Promise<any> => {
    return http.delete<any>(`/projects/${projectId}/llm-config`);
  },

  testProjectLLMConfig: async (
    projectId: string,
    payload: { api_url: string; api_key: string; model_name: string }
  ): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/llm-config/test`, payload);
  },
};
