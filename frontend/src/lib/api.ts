import {
  RequirementSpace,
  WorkspaceListItem,
  ProjectCreationDraft,
  ProjectCreationConfirmResponse,
  ProjectCreationDiscardResponse,
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
    await http.delete<{ project_id: number; message: string }>(`/projects/${id}`);
  },
  deletePerceptionSlot: async (projectId: number): Promise<any> => {
    return http.delete<any>(`/projects/${projectId}/perception-slot`);
  },
  updateProject: async (projectId: number, payload: { name: string; description: string }): Promise<any> => {
    return http.put<any>(`/projects/${projectId}`, payload);
  },
  unlockStage: async (projectId: number, stage: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/unlock-stage`, { stage });
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
  createActor: async (projectId: number, payload: { name: string; description: string }) => {
    return http.post<any>(`/projects/${projectId}/actors`, payload);
  },
  updateActor: async (projectId: number, actorId: number, payload: { name?: string; description?: string }) => {
    return http.put<any>(`/projects/${projectId}/actors/${actorId}`, payload);
  },
  deleteActor: async (projectId: number, actorId: number) => {
    return http.delete<any>(`/projects/${projectId}/actors/${actorId}`);
  },
  createFeature: async (projectId: number, payload: { name: string; description: string; parent_id: number | null }) => {
    return http.post<any>(`/projects/${projectId}/features`, payload);
  },
  updateFeature: async (projectId: number, featureId: number, payload: { name?: string; description?: string; actor_ids?: number[] }) => {
    return http.put<any>(`/projects/${projectId}/features/${featureId}`, payload);
  },
  deleteFeature: async (projectId: number, featureId: number) => {
    return http.delete<any>(`/projects/${projectId}/features/${featureId}`);
  },
  createScenario: async (projectId: number, payload: { feature_id: number; actor_id: number; name: string; content: string }) => {
    return http.post<any>(`/projects/${projectId}/scenarios`, payload);
  },
  updateScenario: async (projectId: number, scenarioId: number, payload: { name?: string; content?: string }) => {
    return http.put<any>(`/projects/${projectId}/scenarios/${scenarioId}`, payload);
  },
  deleteScenario: async (projectId: number, scenarioId: number) => {
    return http.delete<any>(`/projects/${projectId}/scenarios/${scenarioId}`);
  },
  createAcceptanceCriterion: async (projectId: number, scenarioId: number, payload: { content: string; position?: number }) => {
    return http.post<any>(`/projects/${projectId}/scenarios/${scenarioId}/acceptance_criteria`, payload);
  },
  updateAcceptanceCriterion: async (projectId: number, scenarioId: number, acId: number, payload: { content: string }) => {
    return http.put<any>(`/projects/${projectId}/scenarios/${scenarioId}/acceptance_criteria/${acId}`, payload);
  },
  deleteAcceptanceCriterion: async (projectId: number, scenarioId: number, acId: number) => {
    return http.delete<any>(`/projects/${projectId}/scenarios/${scenarioId}/acceptance_criteria/${acId}`);
  },
  createBusinessObject: async (projectId: number, payload: { name: string; description: string }) => {
    return http.post<any>(`/projects/${projectId}/business_objects`, payload);
  },
  updateBusinessObject: async (projectId: number, boId: number, payload: { name?: string; description?: string }) => {
    return http.put<any>(`/projects/${projectId}/business_objects/${boId}`, payload);
  },
  deleteBusinessObject: async (projectId: number, boId: number) => {
    return http.delete<any>(`/projects/${projectId}/business_objects/${boId}`);
  },
  createBusinessObjectAttribute: async (projectId: number, boId: number, payload: { name: string; description: string; data_type: string; example: string }) => {
    return http.post<any>(`/projects/${projectId}/business_objects/${boId}/attributes`, payload);
  },
  updateBusinessObjectAttribute: async (projectId: number, boId: number, attrId: number, payload: { name?: string; description?: string; data_type?: string; example?: string }) => {
    return http.put<any>(`/projects/${projectId}/business_objects/${boId}/attributes/${attrId}`, payload);
  },
  deleteBusinessObjectAttribute: async (projectId: number, boId: number, attrId: number) => {
    return http.delete<any>(`/projects/${projectId}/business_objects/${boId}/attributes/${attrId}`);
  },
  createFlow: async (projectId: number, payload: { name: string; description: string; feature_ids?: number[] }) => {
    return http.post<any>(`/projects/${projectId}/flows`, payload);
  },
  updateFlow: async (projectId: number, flowId: number, payload: { name?: string; description?: string; feature_ids?: number[] }) => {
    return http.put<any>(`/projects/${projectId}/flows/${flowId}`, payload);
  },
  deleteFlow: async (projectId: number, flowId: number) => {
    return http.delete<any>(`/projects/${projectId}/flows/${flowId}`);
  },
  createFlowStep: async (projectId: number, flowId: number, payload: { name: string; description: string; step_type: string; actor_ids?: number[]; input_business_object_ids?: number[]; output_business_object_ids?: number[]; next_step_ids?: number[] }) => {
    return http.post<any>(`/projects/${projectId}/flows/${flowId}/steps`, payload);
  },
  updateFlowStep: async (projectId: number, flowId: number, stepId: number, payload: { name?: string; description?: string; step_type?: string; actor_ids?: number[]; input_business_object_ids?: number[]; output_business_object_ids?: number[]; next_step_ids?: number[] }) => {
    return http.put<any>(`/projects/${projectId}/flows/${flowId}/steps/${stepId}`, payload);
  },
  deleteFlowStep: async (projectId: number, flowId: number, stepId: number) => {
    return http.delete<any>(`/projects/${projectId}/flows/${flowId}/steps/${stepId}`);
  },
  reorderFlowSteps: async (projectId: number, flowId: number, stepIds: number[]) => {
    return http.put<any>(`/projects/${projectId}/flows/${flowId}/steps/reorder`, { step_ids: stepIds });
  },
  updateScope: async (projectId: number, featureId: number, payload: { status: string; reason: string; positive_summary?: string | null; negative_summary?: string | null }) => {
    return http.put<any>(`/projects/${projectId}/features/${featureId}/scope`, payload);
  },
  createActorGenerationDraft: async (projectId: number): Promise<any> => {
    return http.post<any>('/actor_generation_drafts', { project_id: projectId });
  },
  confirmActorGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/actor_generation_drafts/${draftId}/confirm`);
  },
  createFeatureGenerationDraft: async (projectId: number): Promise<any> => {
    return http.post<any>('/feature_generation_drafts', { project_id: projectId });
  },
  confirmFeatureGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/feature_generation_drafts/${draftId}/confirm`);
  },
  createFlowGenerationDraft: async (projectId: number): Promise<any> => {
    return http.post<any>('/flow_generation_drafts', { project_id: projectId });
  },
  confirmFlowGenerationDraft: async (draftId: string): Promise<any> => {
    return http.post<any>(`/flow_generation_drafts/${draftId}/confirm`);
  },
  createScenarioGenerationDraft: async (projectId: number, featureId?: number): Promise<any> => {
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
  createAcceptanceCriteriaGenerationDraft: async (projectId: number, scenarioIds?: number[]): Promise<any> => {
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
  createScopeGenerationDraft: async (projectId: number): Promise<any> => {
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
  exportMarkdown: async (projectId: string | number): Promise<string> => {
    return http.get<string>(`/projects/${projectId}/export/markdown`);
  },
  exportJson: async (projectId: string | number): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/export/json`);
  },
  refineUserRequirements: async (projectId: string | number, feedback: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/user-requirements/refine`, {
      user_feedback: feedback
    });
  },
  impactPreview: async (projectId: string | number, featureId?: number, nextStatus?: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/impact-preview`, {
      feature_id: featureId,
      next_status: nextStatus,
    });
  },
  generatePrototypePreview: async (projectId: string | number, forceRegenerate = true): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/prototype-preview`, {
      force_regenerate: forceRegenerate,
    });
  },
  getLatestPrototypePreview: async (projectId: string | number): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/prototype-preview/latest`);
  },
  listAuditLogs: async (projectId: string | number): Promise<any[]> => {
    return http.get<any[]>(`/projects/${projectId}/audit-logs`);
  },
  listIssues: async (projectId: number, stage: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/issues`, { stage });
  },
  updateIssueStatus: async (projectId: number, issueId: string, status: string): Promise<any> => {
    return http.put<any>(`/projects/${projectId}/issues/status`, {
      issue_id: issueId,
      status,
    });
  },
  resolveIssue: async (projectId: number, payload: { issue_id?: string; issue_code: string; stage?: string; target: any | null; metadata?: any }): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/issues/resolve`, payload);
  },
  getNextSuggestion: async (projectId: number, stage: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/next-suggestion`, { stage });
  },
  rediagnoseNextSuggestion: async (projectId: number, stage: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/next-suggestion/rediagnose`, { stage });
  },
  startNextSuggestion: async (projectId: number, payload: { stage: string; suggestion_code: string; target?: any | null; query?: string | null }): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/next-suggestion/start`, payload);
  },
  createSlotFillingDraft: async (projectId: number, perceptionJobId: number, fillerKind: string): Promise<any> => {
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
  listChoiceGroups: async (projectId: number, status?: string): Promise<any[]> => {
    return http.get<any[]>(`/projects/${projectId}/choice_groups`, { status });
  },
  acceptChoice: async (projectId: number, choiceId: number): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/choices/${choiceId}/accept`);
  },
  rejectChoice: async (projectId: number, choiceId: number): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/choices/${choiceId}/reject`);
  },
  skipKano: async (projectId: number): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/scope/skip_kano`);
  },
  resetKano: async (projectId: number): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/scope/reset_kano`);
  },
  prepareShadowDraft: async (projectId: number): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/preview-shadow-drafts`);
  },
  getShadowDraft: async (projectId: number, draftId: string): Promise<any> => {
    return http.get<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}`);
  },
  discardShadowDraft: async (projectId: number, draftId: string): Promise<any> => {
    return http.delete<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}`);
  },
  commitShadowDraft: async (projectId: number, draftId: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}/commit`);
  },
  regenerateShadowDraft: async (projectId: number, draftId: string, feedback?: string): Promise<any> => {
    return http.post<any>(`/projects/${projectId}/preview-shadow-drafts/${draftId}/regenerate`, {
      user_feedback: feedback,
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
};
