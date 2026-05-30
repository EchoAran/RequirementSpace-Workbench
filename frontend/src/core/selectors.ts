import type {
  RequirementSpace,
  ActorNode,
  FeatureNode,
  ScenarioNode,
  AcceptanceCriterionNode,
  ScopeNode,
  BusinessObjectNode,
  BusinessObjectAttributeNode,
  FlowNode,
  FlowStepNode,
  PerceptionSlot,
  ScopeStatus,
  Issue,
  Choice,
  ChoiceGroup,
  GoalNode,
  CapabilityNode,
  TaskNode,
  NodeStatus,
  GraphPatch,
  FlowStepType,
  Stage,
  StageGateResult,
  PageHealth,
} from '@/core/schema';

const getConfirmationStatus = (value: unknown): NodeStatus => {
  return value === 'confirmed' || value === 'needs_confirmation' || value === 'ai_assumption'
    ? value
    : 'ai_assumption';
};

export const selectAllNodes = (space: RequirementSpace | null): any[] => {
  if (!space) return [];
  const list: any[] = [];
  (space.actors || []).forEach(a => list.push({ ...a, id: a.actorId.toString(), title: a.actorName, description: a.actorDescription, status: getConfirmationStatus((a as any).confirmationStatus), scopeStatus: 'in_scope' }));
  (space.features || []).forEach(f => list.push({ ...f, id: f.featureId.toString(), title: f.featureName, description: f.featureDescription, status: getConfirmationStatus((f as any).confirmationStatus), scopeStatus: f.scope?.scopeStatus || 'in_scope' }));
  (space.businessObjects || []).forEach(b => list.push({ ...b, id: b.businessObjectId.toString(), title: b.businessObjectName, description: b.businessObjectDescription, status: getConfirmationStatus((b as any).confirmationStatus), scopeStatus: 'in_scope' }));
  (space.flows || []).forEach(fl => {
    list.push({ ...fl, id: fl.flowId.toString(), title: fl.flowName, description: fl.flowDescription, status: getConfirmationStatus((fl as any).confirmationStatus), scopeStatus: 'in_scope' });
    (fl.flowSteps || []).forEach(st => {
      list.push({ ...st, id: st.stepId.toString(), title: st.stepName, description: st.stepDescription, status: getConfirmationStatus((st as any).confirmationStatus), scopeStatus: 'in_scope' });
    });
  });
  return list;
};

export const selectAllIssues = (space: RequirementSpace | null): Issue[] => {
  if (!space) return [];
  return space.issuesCompatible && space.issuesCompatible.length > 0
    ? space.issuesCompatible
    : detectIssues(space);
};

export const selectAllLinks = (): any[] => [];
export const selectAllSlots = (space: RequirementSpace | null): any[] => {
  if (!space || !space.perceptionSlot) return [];
  return [space.perceptionSlot];
};
export const selectAllChoiceGroups = (): any[] => [];
export const selectAllChoices = (): any[] => [];

export const selectPerformerActorIds = (space: RequirementSpace | null, taskId: string | number): number[] => {
  if (!space) return [];
  const numId = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId;
  // If it's a scenario/task
  for (const feat of space.features || []) {
    const sc = (feat.scenarios || []).find(s => s.scenarioId === numId);
    if (sc) return [sc.actorId];
  }
  return [];
};

export const selectPerformerTitle = (space: RequirementSpace | null, taskId: string | number): string | null => {
  if (!space) return null;
  const actorIds = selectPerformerActorIds(space, taskId);
  if (actorIds.length === 0) return '系统';
  const actor = (space.actors || []).find(a => a.actorId === actorIds[0]);
  return actor ? actor.actorName : '系统';
};

// Readiness summary calculation
export type ReadinessDimension = {
  kind: 'goal' | 'role' | 'system' | 'data' | 'ui';
  title: string;
  score: number;
  checked: boolean;
};

export type ReadinessSummary = {
  overallScore: number;
  dimensions: ReadinessDimension[];
};

export const buildReadiness = (space: RequirementSpace | null): ReadinessSummary => {
  if (!space) return { overallScore: 0, dimensions: [] };

  const features = space.features || [];
  const actors = space.actors || [];
  const flows = space.flows || [];
  const businessObjects = space.businessObjects || [];

  // Calculate scores for each dimension
  // 1. Goal (Features) - ratio of features with defined descriptions/names
  const goalScore = features.length > 0 ? 100 : 0;

  // 2. Role - ratio of actors referenced by features
  const linkedActorIds = new Set(features.flatMap(f => f.actorIds || []));
  const actorScore = actors.length > 0 
    ? Math.floor((actors.filter(a => linkedActorIds.has(a.actorId)).length / actors.length) * 100)
    : 0;

  // 3. System - ratio of leaf features with flows
  const leafFeatures = features.filter(f => f.parentId !== null && (f.childrenIds || []).length === 0);
  const flowsLinkedFeatures = new Set(flows.flatMap(f => f.featureIds || []));
  const systemScore = leafFeatures.length > 0
    ? Math.floor((leafFeatures.filter(f => flowsLinkedFeatures.has(f.featureId)).length / leafFeatures.length) * 100)
    : 0;

  // 4. Data - Business object attribute completeness
  const totalBOs = businessObjects.length;
  const completeBOs = businessObjects.filter(b => (b.businessObjectAttributes || []).length > 0).length;
  const dataScore = totalBOs > 0 ? Math.floor((completeBOs / totalBOs) * 100) : 0;

  // 5. UI / Acceptance - scenarios with acceptance criteria ratio
  const totalScenarios = features.flatMap(f => f.scenarios || []);
  const completeScenarios = totalScenarios.filter(s => (s.acceptanceCriteria || []).length > 0).length;
  const uiScore = totalScenarios.length > 0 ? Math.floor((completeScenarios / totalScenarios.length) * 100) : 0;

  const dims: ReadinessDimension[] = [
    { kind: 'goal', title: '系统目标就绪', score: goalScore, checked: goalScore >= 80 },
    { kind: 'role', title: '执行角色覆盖', score: actorScore, checked: actorScore >= 80 },
    { kind: 'system', title: '业务流程闭环', score: systemScore, checked: systemScore >= 80 },
    { kind: 'data', title: '业务对象建模', score: dataScore, checked: dataScore >= 80 },
    { kind: 'ui', title: '验收场景覆盖', score: uiScore, checked: uiScore >= 80 },
  ];

  const overallScore = Math.floor(dims.reduce((sum, d) => sum + d.score, 0) / dims.length);

  return { overallScore, dimensions: dims };
};

// -------------------------------------------------------------
// Stage-Gate Refactored Core Rule & Gate Evaluators
// -------------------------------------------------------------

export const detectStageIssues = (space: RequirementSpace | null, stage: Stage): Issue[] => {
  if (!space) return [];
  const issues: Issue[] = [];

  const actors = space.actors || [];
  const features = space.features || [];
  const leafFeatures = features.filter(f => f.parentId !== null && !(features.some(child => child.parentId === f.featureId)));

  if (stage === 'what') {
    // 1. Roles without features (Warning Issue, low severity, non-blocking)
    for (const actor of actors) {
      const isUsed = features.some(f => (f.actorIds || []).includes(actor.actorId));
      if (!isUsed) {
        issues.push({
          id: `rule_actor_unlinked_${actor.actorId}`,
          stage: 'what',
          domain: 'actor',
          title: '参与者角色未关联任何功能',
          description: `参与者 "${actor.actorName}" 目前在系统能力树中没有被任何功能结点引用，请为其添加相应功能，或删除该闲置角色。`,
          severity: 'low',
          blocking: false,
          status: 'open',
          relatedNodeIds: [actor.actorId.toString()],
          suggestedProjection: 'role'
        });
      }
    }

    // 2. Features without Actors (High severity, blocking)
    // Non-equilibrium algorithm:
    const featuresWithActors = leafFeatures.filter(f => (f.actorIds || []).length > 0);
    if (leafFeatures.length > 0 && featuresWithActors.length > 0 && featuresWithActors.length < leafFeatures.length) {
      // Some have, some don't -> Report Issue
      for (const feat of leafFeatures) {
        if ((feat.actorIds || []).length === 0) {
          issues.push({
            id: `rule_feature_no_actor_${feat.featureId}`,
            stage: 'what',
            domain: 'feature_actor_binding',
            title: '功能结点未关联任何角色',
            description: `功能 "${feat.featureName}" 目前未指定任何参与者（执行人），请在该能力的右侧面板中绑定执行角色。`,
            severity: 'high',
            blocking: true,
            status: 'open',
            relatedNodeIds: [feat.featureId.toString()],
            suggestedProjection: 'goal'
          });
        }
      }
    }

    // 3. Leaf Features with empty Scenarios (Medium severity, blocking)
    // Non-equilibrium algorithm:
    const featuresWithScenarios = leafFeatures.filter(f => (f.scenarios || []).length > 0);
    if (leafFeatures.length > 0 && featuresWithScenarios.length > 0 && featuresWithScenarios.length < leafFeatures.length) {
      for (const feat of leafFeatures) {
        if ((feat.scenarios || []).length === 0) {
          issues.push({
            id: `rule_feature_no_scenarios_${feat.featureId}`,
            stage: 'what',
            domain: 'scenario',
            title: '叶子功能未定义成功场景',
            description: `功能结点 "${feat.featureName}" 作为叶子业务结点，尚未描述任何典型成功场景（User Story），可能导致需求不够具象化。`,
            severity: 'medium',
            blocking: true,
            status: 'open',
            relatedNodeIds: [feat.featureId.toString()],
            suggestedProjection: 'goal'
          });
        }
      }
    }

    // 4. Scenarios without AC (High severity, blocking)
    // Non-equilibrium algorithm:
    const allScenarios = features.flatMap(f => f.scenarios || []);
    const scenariosWithAC = allScenarios.filter(s => (s.acceptanceCriteria || []).length > 0);
    if (allScenarios.length > 0 && scenariosWithAC.length > 0 && scenariosWithAC.length < allScenarios.length) {
      for (const feat of features) {
        for (const sc of feat.scenarios || []) {
          if ((sc.acceptanceCriteria || []).length === 0) {
            issues.push({
              id: `rule_scenario_no_ac_${sc.scenarioId}`,
              stage: 'what',
              domain: 'ac',
              title: '成功场景缺少验收标准',
              description: `功能 "${feat.featureName}" 下的场景 "${sc.scenarioName}" 缺少对应的成功标准 (AC)，开发与测试人员将无法验证功能终态。`,
              severity: 'high',
              blocking: true,
              status: 'open',
              relatedNodeIds: [feat.featureId.toString()],
              suggestedProjection: 'goal'
            });
          }
        }
      }
    }
  }

  if (stage === 'how') {
    const flows = space.flows || [];
    const businessObjects = space.businessObjects || [];

    // 1. Flow steps references check (High severity, blocking)
    for (const flow of flows) {
      const steps = flow.flowSteps || [];
      for (const step of steps) {
        if (step.actorIds && step.actorIds.length > 0) {
          const invalidActor = step.actorIds.some(aid => !actors.some(act => act.actorId === aid));
          if (invalidActor) {
            issues.push({
              id: `rule_step_invalid_actor_${step.stepId}`,
              stage: 'how',
              domain: 'step',
              title: '流程步骤引用了不存在的角色',
              description: `流程 "${flow.flowName}" 的步骤 "${step.stepName}" 引用了不存在的参与者角色。`,
              severity: 'high',
              blocking: true,
              status: 'open',
              relatedNodeIds: [flow.flowId.toString()],
              suggestedProjection: 'system'
            });
          }
        }

        const allBOReferences = [...(step.inputBusinessObjectIds || []), ...(step.outputBusinessObjectIds || [])];
        const invalidBO = allBOReferences.some(boid => !businessObjects.some(bo => bo.businessObjectId === boid));
        if (invalidBO) {
          issues.push({
            id: `rule_step_invalid_bo_${step.stepId}`,
            stage: 'how',
            domain: 'step',
            title: '流程步骤引用了损坏的数据对象',
            description: `流程 "${flow.flowName}" 的步骤 "${step.stepName}" 引用了已删除或不存在的数据对象，请核对数据源。`,
            severity: 'high',
            blocking: true,
            status: 'open',
            relatedNodeIds: [flow.flowId.toString()],
            suggestedProjection: 'system'
          });
        }
      }
    }

    // 2. Business Objects Attributes (Medium severity, blocking)
    // Non-equilibrium algorithm:
    const objectsWithAttributes = businessObjects.filter(bo => (bo.businessObjectAttributes || []).length > 0);
    if (businessObjects.length > 0 && objectsWithAttributes.length > 0 && objectsWithAttributes.length < businessObjects.length) {
      for (const bo of businessObjects) {
        if ((bo.businessObjectAttributes || []).length === 0) {
          issues.push({
            id: `rule_bo_no_attrs_${bo.businessObjectId}`,
            stage: 'how',
            domain: 'business_object_attribute',
            title: '业务对象缺少字段属性定义',
            description: `数据实体 "${bo.businessObjectName}" 没有包含任何具体字段属性，建议在其下添加代表业务字段的属性（如 ID、名称、状态等）。`,
            severity: 'medium',
            blocking: true,
            status: 'open',
            relatedNodeIds: [bo.businessObjectId.toString()],
            suggestedProjection: 'data'
          });
        }
      }
    }
    // 3. Flow Steps Non-equilibrium check (Medium severity, blocking)
    const flowsWithSteps = flows.filter(f => (f.flowSteps || []).length > 0);
    if (flows.length > 0 && flowsWithSteps.length > 0 && flowsWithSteps.length < flows.length) {
      for (const flow of flows) {
        if ((flow.flowSteps || []).length === 0) {
          issues.push({
            id: `rule_flow_no_steps_${flow.flowId}`,
            stage: 'how',
            domain: 'step',
            title: '业务流程缺少步骤编排',
            description: `业务流程 "${flow.flowName}" 尚未进行步骤和泳道编排，请补充核心流转步骤。`,
            severity: 'medium',
            blocking: true,
            status: 'open',
            relatedNodeIds: [flow.flowId.toString()],
            suggestedProjection: 'system'
          });
        }
      }
    }
  }

  if (stage === 'scope') {
    // 1. Leaf features without Scope Decisions (Medium severity, blocking)
    // Non-equilibrium algorithm:
    const featuresWithScope = leafFeatures.filter(f => f.scope && f.scope.scopeStatus);
    if (leafFeatures.length > 0 && featuresWithScope.length > 0 && featuresWithScope.length < leafFeatures.length) {
      for (const feat of leafFeatures) {
        if (!feat.scope || !feat.scope.scopeStatus) {
          issues.push({
            id: `rule_feature_no_scope_${feat.featureId}`,
            stage: 'scope',
            domain: 'scope_decision',
            title: '叶子功能缺少范围规划',
            description: `叶子能力 "${feat.featureName}" 尚未进行交付范围规划（本期/暂缓/排除），请进入 Scope 页面进行范围选择。`,
            severity: 'medium',
            blocking: true,
            status: 'open',
            relatedNodeIds: [feat.featureId.toString()],
            suggestedProjection: 'data'
          });
        }
      }
    }
  }

  return issues;
};

export const evaluateMissingKinds = (space: RequirementSpace | null, stage: Stage): string[] => {
  if (!space) return [];
  const missing: string[] = [];

  const actors = space.actors || [];
  const features = space.features || [];
  const leafFeatures = features.filter(f => f.parentId !== null && !(features.some(child => child.parentId === f.featureId)));

  if (stage === 'what') {
    if (actors.length === 0) {
      missing.push('missing_actor');
    }
    if (features.length === 0) {
      missing.push('missing_feature');
    }
    
    const featuresWithActors = leafFeatures.filter(f => (f.actorIds || []).length > 0);
    if (leafFeatures.length > 0 && featuresWithActors.length === 0) {
      missing.push('missing_feature_actor_binding');
    }

    const featuresWithScenarios = leafFeatures.filter(f => (f.scenarios || []).length > 0);
    if (leafFeatures.length > 0 && featuresWithScenarios.length === 0) {
      missing.push('missing_scenario');
    }

    const allScenarios = features.flatMap(f => f.scenarios || []);
    const scenariosWithAC = allScenarios.filter(s => (s.acceptanceCriteria || []).length > 0);
    if (allScenarios.length > 0 && scenariosWithAC.length === 0) {
      missing.push('missing_acceptance_criteria');
    }
  }

  if (stage === 'how') {
    const flows = space.flows || [];
    const businessObjects = space.businessObjects || [];

    if (flows.length === 0) {
      missing.push('missing_flow');
    } else {
      const anyEmptySteps = flows.some(f => (f.flowSteps || []).length === 0);
      if (anyEmptySteps) {
        missing.push('missing_flow_step');
      }

      // Check for invalid topology using linear position indices
      const invalidTopology = flows.some(f => {
        const steps = f.flowSteps || [];
        if (steps.length === 0) return false;
        const positions = steps.map(s => s.position || 0).sort((a,b) => a-b);
        const hasDuplicate = new Set(positions).size !== positions.length;
        return hasDuplicate;
      });
      if (invalidTopology) {
        missing.push('invalid_flow_topology');
      }
    }

    // Business Objects all lack Attributes
    const objectsWithAttributes = businessObjects.filter(bo => (bo.businessObjectAttributes || []).length > 0);
    if (businessObjects.length > 0 && objectsWithAttributes.length === 0) {
      missing.push('missing_business_object_attribute');
    }
  }

  if (stage === 'scope') {
    const featuresWithScope = leafFeatures.filter(f => f.scope && f.scope.scopeStatus);
    if (leafFeatures.length > 0 && featuresWithScope.length === 0) {
      missing.push('missing_scope_decision');
    }
    if (space.kanoStatus !== 'generated' && space.kanoStatus !== 'skipped') {
      if (space.kanoStatus === 'failed') {
        missing.push('kano_failed_retry');
      } else {
        missing.push('missing_kano_analysis');
      }
    }
  }

  return missing;
};

export const buildSinglePerceptionSlot = (
  space: RequirementSpace | null,
  stage: Stage,
  issues: Issue[],
  missingKinds: string[]
): PerceptionSlot | undefined => {
  if (!space) return undefined;

  const actors = space.actors || [];
  const features = space.features || [];
  const flows = space.flows || [];
  const leafFeatures = features.filter(f => f.parentId !== null && !(features.some(child => child.parentId === f.featureId)));

  // A. Onboarding slots check
  if (stage === 'what' && actors.length === 0 && features.length === 0) {
    return {
      id: 'what_onboarding',
      stage: 'what',
      blocking: false,
      kind: 'what_onboarding',
      description: '欢迎进入要做什么阶段，请先创建系统参与者与核心功能能力。',
      actions: {
        manual: { label: '开始创建', targetRoute: '/what' },
        ai: { label: 'AI 生成角色与能力', endpoint: '/api/actor_generation_drafts' }
      }
    };
  }

  if (stage === 'how' && flows.length === 0 && (space.businessObjects || []).length === 0) {
    return {
      id: 'how_onboarding',
      stage: 'how',
      blocking: false,
      kind: 'how_onboarding',
      description: '欢迎进入怎么运作阶段，请为您的系统核心能力设计第一个业务主流程。',
      actions: {
        manual: { label: '手动创建流程', targetRoute: '/flow' },
        ai: { label: 'AI 一键生成流程', endpoint: '/api/flow_generation_drafts' }
      }
    };
  }

  // Generative Perception Slot check
  if (space.perceptionSlot) {
    const pKind = (space.perceptionSlot.perceptionKind || '') as string;
    const isHowSlot = pKind === 'FLOW' || pKind === 'FLOW_STEP' || pKind === '流程主结点' || pKind === '流程步骤结点';
    const slotStage = ((space.perceptionSlot as any).stage || (isHowSlot ? 'how' : 'what')) as Stage;

    if (slotStage === stage) {
      return {
        id: space.perceptionSlot.perceptionSlotId?.toString() || 'generative_slot',
        stage: slotStage,
        blocking: true,
        kind: 'generative_perception_slot',
        perceptionKind: space.perceptionSlot.perceptionKind,
        description: `建议补充以下内容：${space.perceptionSlot.perceptionDescription || ''}`,
        actions: {
          manual: {
            label: '手动补充',
            targetRoute: slotStage === 'how' ? '/flow' : '/what',
            focusMode: 'highlight'
          },
          ai: {
            label: 'AI 智能填槽'
          }
        }
      };
    }
  }

  // B. Ordered Priority Scan for Active Blocking Slots
  const hasGap = (kind: string, issueDomain: string) => {
    return missingKinds.includes(kind) || issues.some(i => i.domain === issueDomain && i.blocking);
  };

  // 1. missing_actor
  if (hasGap('missing_actor', 'actor')) {
    return {
      id: 'slot_missing_actor',
      stage: 'what',
      blocking: true,
      kind: 'missing_actor',
      description: '当前还没有系统参与者角色，请先补充角色定义。',
      actions: {
        manual: { label: '添加角色', targetRoute: '/what', focusMode: 'modal' },
        ai: { label: 'AI 生成角色', endpoint: '/api/actor_generation_drafts' }
      }
    };
  }

  // 2. missing_feature
  if (hasGap('missing_feature', 'feature')) {
    return {
      id: 'slot_missing_feature',
      stage: 'what',
      blocking: true,
      kind: 'missing_feature',
      description: '当前还没有核心能力结点，请先梳理业务功能树。',
      actions: {
        manual: { label: '添加功能', targetRoute: '/what' },
        ai: { label: 'AI 推演功能树', endpoint: '/api/feature_generation_drafts' }
      }
    };
  }

  // 3. missing_feature_actor_binding
  if (hasGap('missing_feature_actor_binding', 'feature_actor_binding')) {
    const badFeat = leafFeatures.find(f => (f.actorIds || []).length === 0);
    return {
      id: 'slot_missing_feature_actor_binding',
      stage: 'what',
      blocking: true,
      kind: 'missing_feature_actor_binding',
      description: '存在功能结点尚未绑定执行角色，请补充角色关联。',
      targetKind: 'feature',
      targetId: badFeat?.featureId,
      actions: {
        manual: { 
          label: '去绑定角色', 
          targetRoute: '/what', 
          targetId: badFeat?.featureId, 
          focusMode: 'highlight' 
        }
      }
    };
  }

  // 4. missing_scenario
  if (hasGap('missing_scenario', 'scenario')) {
    const badFeat = leafFeatures.find(f => (f.scenarios || []).length === 0);
    return {
      id: 'slot_missing_scenario',
      stage: 'what',
      blocking: true,
      kind: 'missing_scenario',
      description: '部分叶子业务结点还没有成功典型场景，请补充对应的 User Story。',
      targetKind: 'feature',
      targetId: badFeat?.featureId,
      actions: {
        manual: { 
          label: '添加场景', 
          targetRoute: '/what', 
          targetId: badFeat?.featureId, 
          focusMode: 'scroll' 
        },
        ai: { label: 'AI 生成场景', endpoint: `/api/scenario_generation_drafts` }
      }
    };
  }

  // 5. missing_acceptance_criteria
  if (hasGap('missing_acceptance_criteria', 'ac')) {
    const badFeat = features.find(f => (f.scenarios || []).some(s => (s.acceptanceCriteria || []).length === 0));
    return {
      id: 'slot_missing_acceptance_criteria',
      stage: 'what',
      blocking: true,
      kind: 'missing_acceptance_criteria',
      description: '存在典型验收场景缺少验收标准（AC），请补充可验证的完成条件。',
      targetKind: 'feature',
      targetId: badFeat?.featureId,
      actions: {
        manual: { 
          label: '完善AC', 
          targetRoute: '/what', 
          targetId: badFeat?.featureId, 
          focusMode: 'highlight' 
        },
        ai: { label: 'AI 补齐标准', endpoint: `/api/acceptance_criteria_generation_drafts` }
      }
    };
  }

  // 6. missing_flow
  if (hasGap('missing_flow', 'flow')) {
    return {
      id: 'slot_missing_flow',
      stage: 'how',
      blocking: true,
      kind: 'missing_flow',
      description: '当前缺少核心业务主流程，请补充代表系统流转的业务流程模型。',
      actions: {
        manual: { label: '创建业务流程', targetRoute: '/flow' },
        ai: { label: 'AI 一键生成流程', endpoint: '/api/flow_generation_drafts' }
      }
    };
  }

  // 7. invalid_flow_topology / missing_flow_step
  if (hasGap('invalid_flow_topology', 'step') || missingKinds.includes('missing_flow_step')) {
    return {
      id: 'slot_invalid_flow_topology',
      stage: 'how',
      blocking: true,
      kind: 'invalid_flow_topology',
      description: '检测到业务流程步骤尚未编排完整，或步骤顺序链路存在问题，请检查拓扑结构。',
      actions: {
        manual: { label: '编排步骤', targetRoute: '/flow' }
      }
    };
  }

  // 8. missing_business_object_attribute
  if (hasGap('missing_business_object_attribute', 'business_object_attribute')) {
    const bo = (space.businessObjects || []).find(b => (b.businessObjectAttributes || []).length === 0);
    return {
      id: 'slot_missing_business_object_attribute',
      stage: 'how',
      blocking: true,
      kind: 'missing_business_object_attribute',
      description: '存在数据实体尚未定义业务字段属性，请补充数据模型。',
      targetKind: 'business_object',
      targetId: bo?.businessObjectId,
      actions: {
        manual: { 
          label: '定义字段', 
          targetRoute: '/flow', 
          targetId: bo?.businessObjectId, 
          focusMode: 'highlight' 
        }
      }
    };
  }

  // 9. missing_scope_decision
  if (hasGap('missing_scope_decision', 'scope_decision')) {
    const badFeat = leafFeatures.find(f => !f.scope || !f.scope.scopeStatus);
    return {
      id: 'slot_missing_scope_decision',
      stage: 'scope',
      blocking: true,
      kind: 'missing_scope_decision',
      description: '部分业务叶子功能尚未制定交付计划，请完成范围划分。',
      targetKind: 'feature',
      targetId: badFeat?.featureId,
      actions: {
        ai: { label: 'AI 自动划分范围' }
      }
    };
  }

  // 10. missing_kano_analysis / kano_failed_retry
  if (hasGap('missing_kano_analysis', 'kano_analysis') || hasGap('kano_failed_retry', 'kano_analysis')) {
    const kStatus = space.kanoStatus || 'missing';
    let desc = '交付范围尚未完成分析，请先生成范围划分建议。';
    let aiLabel = 'AI 自动划分范围';
    
    if (kStatus === 'generating') {
      desc = 'AI 正在分析系统功能卡片并推演交付安排，请稍候。';
      aiLabel = 'AI 正在划分范围';
    } else if (kStatus === 'draft_ready') {
      desc = 'AI 已生成范围划分建议草稿，请在下方核对并确认发布计划。';
      aiLabel = 'AI 自动划分范围';
    } else if (kStatus === 'failed') {
      desc = '范围划分建议生成失败，请重新发起 AI 划分。';
      aiLabel = 'AI 自动划分范围';
    }

    return {
      id: kStatus === 'failed' ? 'slot_kano_failed_retry' : 'slot_missing_kano_analysis',
      stage: 'scope',
      blocking: true,
      kind: kStatus === 'failed' ? 'kano_failed_retry' : 'missing_kano_analysis',
      description: desc,
      actions: {
        ai: { label: aiLabel }
      }
    };
  }

  // 11. Stage gate transition confirmation slot (when static mandatory checks pass but stage is not unlocked)
  if ((stage === 'what' || stage === 'how') && evaluateMandatoryChecks(space, stage) && !space.unlockedStages?.includes(stage)) {
    return {
      id: `slot_${stage}_gate_confirm`,
      stage: stage,
      blocking: true,
      kind: 'stage_gate_transition_confirm',
      description: `${stage === 'what' ? 'What' : 'How'} 阶段基础建模规则已满足。建议先运行 AI 智能诊断检查潜在缺口，再决定是否进入下一阶段。`,
      actions: {
        manual: {
          label: '申请进入下一阶段',
          focusMode: 'modal'
        },
        ai: {
          label: 'AI 智能诊断 (推荐)'
        }
      }
    };
  }

  return undefined;
};

export const evaluateMandatoryChecks = (space: RequirementSpace | null, stage: Stage): boolean => {
  if (!space) return false;

  const actors = space.actors || [];
  const features = space.features || [];
  const leafFeatures = features.filter(f => f.parentId !== null && !(features.some(child => child.parentId === f.featureId)));

  if (stage === 'what') {
    if (actors.length === 0) return false;
    if (leafFeatures.length === 0) return false;
    
    const allBound = leafFeatures.every(f => (f.actorIds || []).length > 0);
    if (!allBound) return false;

    const allHaveScenarios = leafFeatures.every(f => (f.scenarios || []).length > 0);
    if (!allHaveScenarios) return false;

    const allScenarios = leafFeatures.flatMap(f => f.scenarios || []);
    const allHaveAC = allScenarios.every(s => (s.acceptanceCriteria || []).length > 0);
    if (!allHaveAC) return false;

    return true;
  }

  if (stage === 'how') {
    const flows = space.flows || [];
    const businessObjects = space.businessObjects || [];

    if (flows.length === 0) return false;
    
    const allHaveSteps = flows.every(f => (f.flowSteps || []).length > 0);
    if (!allHaveSteps) return false;

    for (const flow of flows) {
      for (const step of flow.flowSteps || []) {
        if (step.actorIds && step.actorIds.length > 0) {
          const invalidActor = step.actorIds.some(aid => !actors.some(act => act.actorId === aid));
          if (invalidActor) return false;
        }
        const allBOs = [...(step.inputBusinessObjectIds || []), ...(step.outputBusinessObjectIds || [])];
        const invalidBO = allBOs.some(boid => !businessObjects.some(bo => bo.businessObjectId === boid));
        if (invalidBO) return false;
      }
    }

    if (businessObjects.length > 0) {
      const objectsWithAttributes = businessObjects.filter(bo => (bo.businessObjectAttributes || []).length > 0);
      if (objectsWithAttributes.length === 0) return false;
    }

    return true;
  }

  if (stage === 'scope') {
    if (leafFeatures.length === 0) return false;
    
    const allHaveScope = leafFeatures.every(f => f.scope && f.scope.scopeStatus);
    if (!allHaveScope) return false;

    if (space.kanoStatus !== 'generated' && space.kanoStatus !== 'skipped') {
      return false;
    }

    return true;
  }

  return false;
};

export const buildStageGate = (space: RequirementSpace | null, stage: Stage): StageGateResult => {
  const issues = detectStageIssues(space, stage);
  const missingKinds = evaluateMissingKinds(space, stage);
  const slot = buildSinglePerceptionSlot(space, stage, issues, missingKinds);
  const mandatoryChecksPassed = evaluateMandatoryChecks(space, stage);

  const passed = mandatoryChecksPassed && !(slot && slot.blocking);

  return {
    stage,
    mandatoryChecksPassed,
    passed,
    issues,
    activeSlot: slot || undefined,
    blockingSlot: slot && slot.blocking ? slot : undefined,
    missingKinds
  };
};

export const inferIssueStage = (issue: Issue): Stage | null => {
  if (issue.stage === 'what' || issue.stage === 'how' || issue.stage === 'scope') {
    return issue.stage;
  }

  switch (issue.domain) {
    case 'actor':
    case 'feature':
    case 'feature_actor_binding':
    case 'scenario':
    case 'ac':
      return 'what';
    case 'flow':
    case 'step':
    case 'business_object':
    case 'business_object_attribute':
      return 'how';
    case 'scope_decision':
    case 'kano':
      return 'scope';
    default:
      break;
  }

  switch (issue.suggestedProjection) {
    case 'goal':
    case 'role':
    case 'ui':
      return 'what';
    case 'system':
      return 'how';
    case 'data':
      return 'scope';
    default:
      return null;
  }
};

export const getStageIssues = (space: RequirementSpace | null, stage: Stage): Issue[] => {
  if (!space) return [];

  const compatibleIssues = Array.isArray((space as any).issuesCompatible)
    ? ((space as any).issuesCompatible as Issue[])
    : [];

  return compatibleIssues.filter(
    (issue) => issue.status === 'open' && inferIssueStage(issue) === stage
  );
};

export const buildPageHealth = (space: RequirementSpace | null, path: string): PageHealth => {
  if (!space) {
    return {
      statusCode: 'not_started',
      statusLabel: '未开始',
      disabled: false,
      issueCount: 0,
      hasBlockingSlot: false
    };
  }

  const whatGate = buildStageGate(space, 'what');
  const howGate = buildStageGate(space, 'how');
  const scopeGate = buildStageGate(space, 'scope');
  const whatIssues = getStageIssues(space, 'what');
  const howIssues = getStageIssues(space, 'how');
  const scopeIssues = getStageIssues(space, 'scope');

  if (path === '/what') {
    const hasBlockingSlot = whatGate.blockingSlot !== undefined;
    const isUnused = (space.actors || []).length === 0 && (space.features || []).length === 0;
    
    let statusCode: PageHealth['statusCode'] = 'ready';
    let statusLabel = '已就绪';

    if (isUnused) {
      statusCode = 'not_started';
      statusLabel = '未开始';
    } else if (hasBlockingSlot) {
      statusCode = 'needs_attention';
      statusLabel = '待补齐';
    } else if (whatGate.passed) {
      statusCode = 'ready';
      statusLabel = '已收敛';
    } else {
      statusCode = 'in_progress';
      statusLabel = '进行中';
    }

    return {
      statusCode,
      statusLabel,
      disabled: false,
      issueCount: whatIssues.length,
      hasBlockingSlot,
      nextSlot: whatGate.activeSlot
    };
  }

  if (path === '/flow') {
    const disabled = !whatGate.passed;
    const hasBlockingSlot = howGate.blockingSlot !== undefined;
    const isUnused = (space.flows || []).length === 0;

    let statusCode: PageHealth['statusCode'] = 'locked';
    let statusLabel = '已锁定';

    if (disabled) {
      statusCode = 'locked';
      statusLabel = '待前置就绪';
    } else if (isUnused) {
      statusCode = 'not_started';
      statusLabel = '未开始';
    } else if (hasBlockingSlot) {
      statusCode = 'needs_attention';
      statusLabel = '待补齐';
    } else if (howGate.passed) {
      statusCode = 'ready';
      statusLabel = '已收敛';
    } else {
      statusCode = 'in_progress';
      statusLabel = '进行中';
    }

    return {
      statusCode,
      statusLabel,
      disabled,
      disabledReason: disabled ? '需先补齐 What 阶段的所有核心建模规则' : undefined,
      issueCount: howIssues.length,
      hasBlockingSlot,
      nextSlot: howGate.activeSlot
    };
  }

  if (path === '/scope') {
    const disabled = !whatGate.passed || !howGate.passed;
    const hasBlockingSlot = scopeGate.blockingSlot !== undefined;
    
    const leafFeatures = (space.features || []).filter(f => {
      const isParent = (space.features || []).some(child => child.parentId === f.featureId);
      return f.parentId !== null && !isParent;
    });
    const isUnused = leafFeatures.length > 0 && leafFeatures.every(f => !f.scope || !f.scope.scopeStatus);

    let statusCode: PageHealth['statusCode'] = 'locked';
    let statusLabel = '已锁定';

    if (disabled) {
      statusCode = 'locked';
      statusLabel = '待前置就绪';
    } else if (isUnused) {
      statusCode = 'not_started';
      statusLabel = '未开始';
    } else if (hasBlockingSlot) {
      statusCode = 'needs_attention';
      statusLabel = '待补齐';
    } else if (scopeGate.passed) {
      statusCode = 'ready';
      statusLabel = '已收敛';
    } else {
      statusCode = 'in_progress';
      statusLabel = '进行中';
    }

    return {
      statusCode,
      statusLabel,
      disabled,
      disabledReason: disabled ? '需先补齐 What 和 How 阶段的核心规则' : undefined,
      issueCount: scopeIssues.length,
      hasBlockingSlot,
      nextSlot: scopeGate.activeSlot
    };
  }

  if (path === '/preview') {
    const allGatesPassed = whatGate.passed && howGate.passed && scopeGate.passed;
    
    return {
      statusCode: allGatesPassed ? 'real_ready' : 'shadow_available',
      statusLabel: allGatesPassed ? '已就绪' : '影子预览可用',
      disabled: false,
      issueCount: whatIssues.length + howIssues.length + scopeIssues.length,
      hasBlockingSlot: false
    };
  }

  if (path === '/overview' || path === '/') {
    const totalIssues = whatIssues.length + howIssues.length + scopeIssues.length;
    const hasAnyBlocking = whatGate.blockingSlot || howGate.blockingSlot || scopeGate.blockingSlot;

    return {
      statusCode: hasAnyBlocking ? 'needs_attention' : totalIssues > 0 ? 'in_progress' : 'ready',
      statusLabel: hasAnyBlocking ? '待决策' : '已收敛',
      disabled: false,
      issueCount: totalIssues,
      hasBlockingSlot: hasAnyBlocking !== undefined
    };
  }

  // Dashboard Overview Path fallback
  const totalIssues = whatIssues.length + howIssues.length + scopeIssues.length;
  const hasAnyBlocking = whatGate.blockingSlot || howGate.blockingSlot || scopeGate.blockingSlot;

  return {
    statusCode: hasAnyBlocking ? 'needs_attention' : totalIssues > 0 ? 'in_progress' : 'ready',
    statusLabel: hasAnyBlocking ? '待决策' : '已收敛',
    disabled: false,
    issueCount: totalIssues,
    hasBlockingSlot: hasAnyBlocking !== undefined
  };
};

export type OverviewModel = {
  readiness: ReadinessSummary;
  openIssues: Issue[];
  highRiskIssues: Issue[];
  decisionQueue: Array<{
    id: string;
    kind: 'choiceGroup';
    title: string;
    description: string;
    original: any;
  }>;
  recentChoices: any[];
  openChoiceGroupsCount: number;
  openSlotsCount: number;

  aiAssumptionLedger: any[];
  recentAuditOperations: any[];
};

const choiceGroupTypeLabelMap: Record<string, string> = {
  actor: '参与者',
  scenario: '场景',
  feature: '功能树',
  flow: '流程',
  scope: '范围分析',
  acceptance_criteria: '验收标准',
  project_creation: '项目草稿',
};

const getChoiceGroupDecisionLabel = (choiceGroup: any) => {
  const rawType = choiceGroup.generationType || choiceGroup.generation_type || choiceGroup.sourceType || choiceGroup.source_type;
  return choiceGroupTypeLabelMap[rawType] || null;
};

const getChoiceGroupDecisionDescription = (choiceGroup: any) => {
  const comparisonSummary =
    choiceGroup.statusDetail?.comparisonSummary ||
    choiceGroup.statusDetail?.comparison_summary;
  if (comparisonSummary) {
    return comparisonSummary;
  }

  const label = getChoiceGroupDecisionLabel(choiceGroup);
  const candidateCount = (choiceGroup.choices || []).filter((choice: any) => choice.status === 'candidate').length
    || choiceGroup.successCount
    || choiceGroup.success_count
    || choiceGroup.candidateCount
    || choiceGroup.candidate_count
    || choiceGroup.choices?.length
    || 0;

  if (label) {
    return `AI 已生成 ${candidateCount} 个${label}候选方案，点击查看差异后再决定是否采纳。`;
  }

  return `AI 已生成 ${candidateCount} 个候选方案，点击查看差异后再决定是否采纳。`;
};

export const buildOverviewModel = (space: RequirementSpace | null, auditLogs: any[] = []): OverviewModel => {
  const readiness = buildReadiness(space);
  if (!space) {
    return {
      readiness,
      openIssues: [],
      highRiskIssues: [],
      decisionQueue: [],
      recentChoices: [],
      openChoiceGroupsCount: 0,
      openSlotsCount: 0,

      aiAssumptionLedger: [],
      recentAuditOperations: [],
    };
  }

  const whatGate = buildStageGate(space, 'what');
  const howGate = buildStageGate(space, 'how');
  const scopeGate = buildStageGate(space, 'scope');

  const allIssues = selectAllIssues(space);
  const openIssues = allIssues.filter(i => i.status === 'open');
  const highRiskIssues = openIssues.filter(i => i.severity === 'high');

  const dq: any[] = [];

  // 1. 抉择项：ChoiceGroups (处于 open 状态)
  if (space.choiceGroups) {
    Object.values(space.choiceGroups).forEach((cg: any) => {
      if (cg.status === 'open') {
        const label = getChoiceGroupDecisionLabel(cg);
        dq.push({
          id: cg.id,
          kind: 'choiceGroup' as const,
          title: label ? `${label}方案决策` : `方案决策：方案组 #${cg.id}`,
          description: getChoiceGroupDecisionDescription(cg),
          original: cg,
        });
      }
    });
  }

  // 构建 AI 假设账本：扫描所有实体，收集 confirmationStatus === 'ai_assumption' 的节点
  const ledger: any[] = [];
  const pushLedger = (kind: string, id: number, title: string, source: string, status: string) => {
    if (status === 'ai_assumption') {
      ledger.push({
        kind,
        id: `${kind}-${id}`,
        nodeId: id,
        title,
        source,
        status,
      });
    }
  };
  (space.actors || []).forEach((a: any) =>
    pushLedger('actor', a.actorId, a.actorName, a.actorDescription, a.confirmationStatus)
  );
  (space.features || []).forEach((f: any) => {
    pushLedger('feature', f.featureId, f.featureName, f.featureDescription, f.confirmationStatus);
    if (f.scope?.scopeId) {
      pushLedger(
        'scope',
        f.scope.scopeId,
        f.featureName,
        f.scope.reason || f.featureDescription || '交付范围决策待确认',
        f.scope.confirmationStatus,
      );
    }
    (f.scenarios || []).forEach((s: any) => {
      pushLedger('scenario', s.scenarioId, s.scenarioName, s.scenarioContent, s.confirmationStatus);
      (s.acceptanceCriteria || []).forEach((ac: any) => {
        pushLedger('acceptance_criterion', ac.criterionId, ac.criterionContent?.slice(0, 80), ac.criterionContent, ac.confirmationStatus);
      });
    });
  });
  (space.businessObjects || []).forEach((b: any) => {
    pushLedger('business_object', b.businessObjectId, b.businessObjectName, b.businessObjectDescription, b.confirmationStatus);
  });
  (space.flows || []).forEach((fl: any) =>
    pushLedger('flow', fl.flowId, fl.flowName, fl.flowDescription, fl.confirmationStatus)
  );

  const choicesCompatible = (space as any).choicesCompatible || [];
  const recentChoices = choicesCompatible.filter((c: any) => c.status === 'candidate').slice(0, 3);
  const openChoiceGroupsCount = Object.values(space.choiceGroups || {}).filter((cg: any) => cg.status === 'open').length;

  // 获取当前活跃阶段，仅统计当前阶段的阻塞槽位
  let activeStage: Stage = 'what';
  if (whatGate.passed) {
    activeStage = howGate.passed ? 'scope' : 'how';
  }
  const activeGate = activeStage === 'what' ? whatGate : activeStage === 'how' ? howGate : scopeGate;
  const openSlotsCount = activeGate.blockingSlot ? 1 : 0;

  return {
    readiness,
    openIssues,
    highRiskIssues,
    decisionQueue: dq.slice(0, 5),
    recentChoices,
    openChoiceGroupsCount,
    openSlotsCount,

    aiAssumptionLedger: ledger,
    recentAuditOperations: auditLogs.slice(0, 5),
  };
};

export const projectionPath = (projection: string) => {
  if (projection === 'system') return '/flow';
  if (projection === 'data') return '/scope';
  if (projection === 'ui') return '/preview';
  return '/what';
};

export const buildProjectRoute = (
  projectId: number | string | null | undefined,
  page: '/overview' | '/what' | '/flow' | '/scope' | '/preview'
): string => {
  if (projectId === null || projectId === undefined || projectId === '') return page;
  return `/projects/${projectId}${page}`;
};

export const extractWorkspacePage = (
  pathname: string
): '/overview' | '/what' | '/flow' | '/scope' | '/preview' | null => {
  const match = pathname.match(/\/projects\/[^/]+(\/overview|\/what|\/flow|\/scope|\/preview)$/);
  if (match) {
    return match[1] as '/overview' | '/what' | '/flow' | '/scope' | '/preview';
  }

  if (
    pathname === '/overview' ||
    pathname === '/what' ||
    pathname === '/flow' ||
    pathname === '/scope' ||
    pathname === '/preview'
  ) {
    return pathname;
  }

  return null;
};

// Flow step topology detail
export type StepDetail = {
  inputs: string[];
  outputs: string[];
  rules: string[];
  stateChanges: string[];
  relatedPages: string[];
  relatedIssueIds: string[];
  relatedChoiceIds: string[];
};

export const buildStepDetail = (space: RequirementSpace | null, stepId: string | number): StepDetail => {
  const emptyDetail = { inputs: [], outputs: [], rules: [], stateChanges: [], relatedPages: [], relatedIssueIds: [], relatedChoiceIds: [] };
  if (!space) return emptyDetail;
  const numId = typeof stepId === 'string' ? parseInt(stepId, 10) : stepId;

  // Find step
  let targetStep: FlowStepNode | null = null;
  for (const flow of space.flows || []) {
    const s = (flow.flowSteps || []).find(st => st.stepId === numId);
    if (s) {
      targetStep = s;
      break;
    }
  }

  if (!targetStep) return emptyDetail;

  const inputs = (targetStep.inputBusinessObjectIds || [])
    .map(id => (space.businessObjects || []).find(b => b.businessObjectId === id)?.businessObjectName)
    .filter(Boolean) as string[];

  const outputs = (targetStep.outputBusinessObjectIds || [])
    .map(id => (space.businessObjects || []).find(b => b.businessObjectId === id)?.businessObjectName)
    .filter(Boolean) as string[];

  return {
    inputs,
    outputs,
    rules: ['满足业务主流程条件限制', 'AI 流程流转完整性保障'],
    stateChanges: outputs.map(o => `${o} 状态更新`),
    relatedPages: ['操作控制大屏', '扫码录入页面'],
    relatedIssueIds: [],
    relatedChoiceIds: [],
  };
};

export type SystemProjection = {
  swimlanes: string[];
  abnormalIssues: Issue[];
  getStepsBySwimlane: (lane: string) => FlowStepNode[];
  getNextStepTitles: (stepId: string) => string[];
  getExceptionStepTitles: (stepId: string) => string[];
  getStepSlots: (stepId: string) => any[];
  businessObjects: any[];
  getRelatedStepsForObject: (objectId: string | number) => any[];
};

export const buildSystemProjection = (space: RequirementSpace | null): SystemProjection => {
  const baseLanes = space ? (space.actors || []).map(a => a.actorName) : [];
  const swimlanes = baseLanes.includes('系统') ? baseLanes : [...baseLanes, '系统'];

  const empty = {
    swimlanes,
    abnormalIssues: [],
    getStepsBySwimlane: () => [],
    getNextStepTitles: () => [],
    getExceptionStepTitles: () => [],
    getStepSlots: () => [],
    businessObjects: [],
    getRelatedStepsForObject: () => [],
  };

  if (!space) return empty;

  const issues = space.issuesCompatible && space.issuesCompatible.length > 0
    ? space.issuesCompatible
    : detectIssues(space);
  const abnormalIssues = issues.filter(i => i.suggestedProjection === 'system');

  const allSteps = (space.flows || []).flatMap(f => f.flowSteps || []);

  const getStepsBySwimlane = (lane: string) => {
    return allSteps
      .filter(step => {
        if (lane === '系统') {
          return (step.actorIds || []).length === 0;
        }
        const performerId = (step.actorIds || [])[0];
        const performer = (space.actors || []).find(a => a.actorId === performerId);
        return performer ? performer.actorName === lane : false;
      })
      .map((step, idx) => ({
        ...step,
        id: step.stepId.toString(),
        title: step.stepName,
        description: step.stepDescription,
        status: 'confirmed',
        position: idx + 1
      })) as any[];
  };

  const getNextStepTitles = (stepId: string | number) => {
    const numId = typeof stepId === 'string' ? parseInt(stepId, 10) : stepId;
    const step = allSteps.find(s => s.stepId === numId);
    if (!step) return [];
    return (step.nextStepIds || [])
      .map(nid => allSteps.find(s => s.stepId === nid)?.stepName)
      .filter(Boolean) as string[];
  };

  const getRelatedStepsForObject = (objectId: string | number) => {
    const numId = typeof objectId === 'string' ? parseInt(objectId, 10) : objectId;
    return allSteps
      .filter(s => (s.inputBusinessObjectIds || []).includes(numId) || (s.outputBusinessObjectIds || []).includes(numId))
      .map(step => ({
        ...step,
        id: step.stepId.toString(),
        title: step.stepName,
        description: step.stepDescription,
        status: 'confirmed',
        kind: 'flow_step'
      }));
  };

  return {
    swimlanes,
    abnormalIssues,
    getStepsBySwimlane,
    getNextStepTitles,
    getExceptionStepTitles: () => [],
    getStepSlots: () => [],
    businessObjects: (space.businessObjects || []).map(b => ({
      ...b,
      id: b.businessObjectId.toString(),
      title: b.businessObjectName,
      description: b.businessObjectDescription,
      status: getConfirmationStatus((b as any).confirmationStatus),
    })),
    getRelatedStepsForObject,
  };
};

export type GoalBranchItem =
  | { kind: 'issue'; issue: Issue; projection: string }
  | { kind: 'slot'; slot: any; projection: string }
  | { kind: 'choiceGroup'; choiceGroup: any; projection: string };

export const buildGoalBranchItems = (space: RequirementSpace | null): GoalBranchItem[] => {
  if (!space) return [];
  const items: GoalBranchItem[] = [];

  // Add active perception slot
  if (space.perceptionSlot) {
    const slotStage = ((space.perceptionSlot as any).stage || 'what') as Stage;
    const projection = slotStage === 'how' ? 'system' : slotStage === 'scope' ? 'data' : 'goal';
    items.push({
      kind: 'slot',
      slot: {
        id: space.perceptionSlot.perceptionSlotId.toString(),
        name: space.perceptionSlot.perceptionKind,
        description: space.perceptionSlot.perceptionDescription,
        status: 'empty'
      },
      projection
    });
  }

  // Add relevant rule issues
  const issues = space.issuesCompatible && space.issuesCompatible.length > 0
    ? space.issuesCompatible
    : detectIssues(space);
  issues.forEach(issue => {
    items.push({
      kind: 'issue',
      issue,
      projection: issue.suggestedProjection
    });
  });

  return items;
};

export const normalizeScopeStatus = (status: string | undefined | null): 'current' | 'postponed' | 'exclude' => {
  if (!status) return 'current';
  const s = status.toLowerCase();
  if (s === 'current' || s === 'in_scope' || s === '本期') return 'current';
  if (s === 'postponed' || s === 'deferred' || s === '暂缓') return 'postponed';
  if (s === 'exclude' || s === 'excluded' || s === '排除') return 'exclude';
  return 'current';
};

// Tree-hierarchy feature selectors
export const getRootCapabilities = (space: RequirementSpace | null): any[] => {
  if (!space) return [];
  const features = space.features || [];
  const dbRoot = features.find(f => f.parentId === null);
  if (!dbRoot) return [];
  
  return features
    .filter(f => f.parentId === dbRoot.featureId)
    .map(f => ({
      ...f,
      id: f.featureId.toString(),
      title: f.featureName,
      description: f.featureDescription,
      status: getConfirmationStatus((f as any).confirmationStatus),
      scopeStatus: normalizeScopeStatus(f.scope?.scopeStatus),
      kind: 'feature'
    }));
};

export const getChildCapabilities = (space: RequirementSpace | null, capId: string | number): any[] => {
  if (!space) return [];
  const numId = typeof capId === 'string' ? parseInt(capId, 10) : capId;
  return (space.features || [])
    .filter(f => f.parentId === numId)
    .map(f => ({
      ...f,
      id: f.featureId.toString(),
      title: f.featureName,
      description: f.featureDescription,
      status: getConfirmationStatus((f as any).confirmationStatus),
      scopeStatus: normalizeScopeStatus(f.scope?.scopeStatus),
      kind: 'feature'
    }));
};

export const getTasksForCapability = (space: RequirementSpace | null, capId: string | number): any[] => {
  if (!space) return [];
  const numId = typeof capId === 'string' ? parseInt(capId, 10) : capId;
  const feature = (space.features || []).find(f => f.featureId === numId);
  if (!feature) return [];

  // Map scenarios of this feature as tasks
  return (feature.scenarios || []).map(s => ({
    id: s.scenarioId.toString(),
    title: s.scenarioName,
    outcome: s.scenarioContent,
    status: getConfirmationStatus((s as any).confirmationStatus),
    actorId: s.actorId.toString(),
    scopeStatus: 'in_scope'
  }));
};

export const buildTaskFootprint = (space: RequirementSpace | null, taskId: string | number): { flowStepCount: number; screenCount: number; objectCount: number } => {
  if (!space) return { flowStepCount: 0, screenCount: 0, objectCount: 0 };
  const numId = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId;

  // Locate the scenario matching scenarioId
  let targetScenario: ScenarioNode | null = null;
  for (const f of space.features || []) {
    const s = (f.scenarios || []).find(sc => sc.scenarioId === numId);
    if (s) {
      targetScenario = s;
      break;
    }
  }

  if (!targetScenario) return { flowStepCount: 1, screenCount: 1, objectCount: 1 };

  // Calculate realistic footprints
  const flowStepCount = (space.flows || []).flatMap(f => f.flowSteps || []).filter(step => (step.actorIds || []).includes(targetScenario!.actorId)).length || 1;
  const objectCount = (space.businessObjects || []).length || 1;

  return {
    flowStepCount,
    screenCount: 1,
    objectCount
  };
};

export const formatImpactPreview = (space: RequirementSpace | null, impact: any) => {
  if (!impact) return { goals: [], actors: [], flows: [], objects: [], screens: [] };
  return {
    goals: [],
    actors: [],
    flows: [],
    objects: [],
    screens: []
  };
};

export const groupScopeItems = (space: RequirementSpace | null) => {
  const empty = { inScope: [], deferred: [], dependencies: [], outOfScope: [], excluded: [], undecided: [] };
  if (!space) return empty;

  // Filter leaf capabilities only
  const leafFeatures = (space.features || []).filter(f => {
    const isParent = (space.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && !isParent;
  });

  const mapToNode = (f: FeatureNode) => {
    const parentModule = (space.features || []).find(p => p.featureId === f.parentId);
    const hasScope = f.scope && f.scope.scopeStatus;
    const normStatus = hasScope ? normalizeScopeStatus(f.scope.scopeStatus) : undefined;
    const isDecisionMissing = !hasScope;
    const scopeConfirmationStatus = (f.scope as any)?.confirmationStatus || 'ai_assumption';

    return {
      kind: 'scope' as const,
      id: f.featureId.toString(),
      featureId: f.featureId,
      featureName: f.featureName,
      featureDescription: f.featureDescription,
      title: f.featureName,
      description: f.featureDescription,
      status: scopeConfirmationStatus,
      confirmationStatus: scopeConfirmationStatus,
      scopeStatus: normStatus,
      isDecisionMissing,
      parentModuleName: parentModule ? parentModule.featureName : '未分组模块',
      scope: f.scope ? {
        ...f.scope,
        confirmationStatus: scopeConfirmationStatus,
        scopeStatus: normStatus
      } : {
        kind: 'scope' as const,
        scopeId: undefined as any,
        scopeStatus: normStatus as any,
        reason: '',
        confirmationStatus: 'ai_assumption' as const,
        positiveSummary: null,
        negativeSummary: null,
        positivePictureBase64: null,
        negativePictureBase64: null,
        kanoCategory: null,
        kanoCategoryName: null
      }
    };
  };

  const mapped = leafFeatures.map(mapToNode);

  return {
    inScope: mapped.filter(f => f.scopeStatus === 'current'),
    deferred: mapped.filter(f => f.scopeStatus === 'postponed'),
    dependencies: [],
    outOfScope: [],
    excluded: mapped.filter(f => f.scopeStatus === 'exclude'),
    undecided: mapped.filter(f => f.isDecisionMissing),
  };
};

export const buildPreviewCheckpoints = (space: RequirementSpace | null) => {
  if (!space) {
    return [
      { id: 'initial', title: '初始输入', projection: 'goal', passed: false, checks: [] },
      { id: 'structure', title: '结构成型', projection: 'goal', passed: false, checks: [] },
      { id: 'flow', title: '流程闭环', projection: 'system', passed: false, checks: [] },
      { id: 'delivery', title: '交付确认', projection: 'ui', passed: false, checks: [] },
    ];
  }

  const checkpoints = [
    {
      id: 'initial',
      title: '初始输入',
      projection: 'goal',
      checks: [
        { label: '存在核心目标', passed: space.projectName !== '' },
        { label: '存在主要角色', passed: (space.actors || []).length > 0 },
      ],
      passed: false,
    },
    {
      id: 'structure',
      title: '结构成型',
      projection: 'goal',
      checks: [
        { label: '存在功能定义', passed: (space.features || []).length > 0 },
        { label: '存在关键验收场景', passed: (space.features || []).some(f => (f.scenarios || []).length > 0) },
      ],
      passed: false,
    },
    {
      id: 'flow',
      title: '流程闭环',
      projection: 'system',
      checks: [
        { label: '存在流程步骤', passed: (space.flows || []).some(f => (f.flowSteps || []).length > 0) },
        { label: '无严重业务缺陷', passed: (space.issuesCompatible && space.issuesCompatible.length > 0 ? space.issuesCompatible : detectIssues(space)).filter(i => i.severity === 'high').length === 0 },
      ],
      passed: false,
    },
    {
      id: 'delivery',
      title: '交付确认',
      projection: 'ui',
      checks: [
        { label: '存在业务数据建模', passed: (space.businessObjects || []).length > 0 },
        { label: '已完成范围划分', passed: (space.features || []).some(f => f.scope !== null) },
      ],
      passed: false,
    },
  ];

  return checkpoints.map(c => ({
    ...c,
    passed: c.checks.every(chk => chk.passed)
  }));
};

export const buildRolePages = (space: RequirementSpace | null, actorId: string | null): any[] => {
  if (!space || !actorId) return [];
  const numId = typeof actorId === 'string' ? parseInt(actorId, 10) : actorId;
  const actor = (space.actors || []).find(a => a.actorId === numId);
  if (!actor) return [];

  // Filter leaf capabilities only associated with this actor
  const leafFeatures = (space.features || []).filter(f => {
    const isParent = (space.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && !isParent && (f.actorIds || []).includes(numId);
  });

  return leafFeatures.map(f => {
    // Find steps in flows associated with this feature and this actor
    const relatedSteps = (space.flows || [])
      .filter(flow => (flow.featureIds || []).includes(f.featureId))
      .flatMap(flow => flow.flowSteps || [])
      .filter(step => (step.actorIds || []).includes(numId))
      .map(step => step.stepName);

    return {
      id: `screen_feat_${f.featureId}`,
      name: `【${f.featureName}】操作界面`,
      desc: f.featureDescription || `提供给 ${actor.actorName} 用于执行 ${f.featureName} 的交互界面。`,
      featureName: f.featureName,
      scenarios: f.scenarios || [],
      relatedSteps: relatedSteps.length > 0 ? relatedSteps : [`操作与处理 ${f.featureName}`],
      actions: (f.scenarios || []).map(s => s.scenarioName)
    };
  });
};

export const buildPlaybackForActor = (space: RequirementSpace | null, actorId: string | null) => {
  if (!space || !actorId) return [];
  const pages = buildRolePages(space, actorId);
  return pages.map(page => ({
    screenId: page.id,
    screenTitle: page.name,
    stepIds: page.relatedSteps,
    stepTitles: page.relatedSteps
  }));
};

export const getGuardRedirect = (
  path: string,
  space: RequirementSpace | null
): { targetRoute: string; errorToast: string } | undefined => {
  if (!space) return undefined;

  const whatGate = buildStageGate(space, 'what');
  const howGate = buildStageGate(space, 'how');

  if (path === '/flow') {
    if (!whatGate.passed) {
      return {
        targetRoute: '/what',
        errorToast: '⚠️ 需先补齐 What 阶段：至少存在角色与叶子功能，每个功能需关联角色、典型场景，且所有成功标准非空，且无阻碍性感知槽。'
      };
    }
  }

  if (path === '/scope') {
    if (!whatGate.passed) {
      return {
        targetRoute: '/what',
        errorToast: '⚠️ 需先补齐 What 阶段：至少存在角色与叶子功能，每个功能需关联角色、典型场景，且所有成功标准非空，且无阻碍性感知槽。'
      };
    }
    if (!howGate.passed) {
      return {
        targetRoute: '/flow',
        errorToast: '⚠️ 需先补齐 How 阶段：至少存在一条核心业务流程且拓扑关联关系完整，字段属性满足非平衡校验，且无阻碍性感知槽。'
      };
    }
  }

  return undefined;
};

export const detectIssues = (space: RequirementSpace | null): Issue[] => {
  if (!space) return [];
  const issues: Issue[] = [];

  const actors = space.actors || [];
  const features = space.features || [];
  const businessObjects = space.businessObjects || [];
  const flows = space.flows || [];

  // 1. Roles without features
  for (const actor of actors) {
    const isUsed = features.some((f) => (f.actorIds || []).includes(actor.actorId));
    if (!isUsed) {
      issues.push({
        id: `rule_actor_unlinked_${actor.actorId}`,
        title: `参与者角色未关联任何功能`,
        description: `参与者 "${actor.actorName}" 目前在系统架构中没有被任何功能结点引用，请为其添加相应功能，或删除该闲置角色。`,
        severity: 'medium',
        status: 'open',
        relatedNodeIds: [actor.actorId.toString()],
        suggestedProjection: 'role',
        category: 'rule_gap',
      });
    }
  }

  // 2. Features without roles
  for (const feature of features) {
    if ((feature.actorIds || []).length === 0) {
      issues.push({
        id: `rule_feature_no_actor_${feature.featureId}`,
        title: `功能结点未关联任何角色`,
        description: `功能 "${feature.featureName}" 目前未指定任何参与者（执行人），请在该功能的右侧面板中绑定执行角色。`,
        severity: 'high',
        status: 'open',
        relatedNodeIds: [feature.featureId.toString()],
        suggestedProjection: 'goal',
        category: 'rule_gap',
      });
    }

    // 3. Leaf features with empty scenarios
    const isLeaf = (feature.childrenIds || []).length === 0;
    if (isLeaf && (feature.scenarios || []).length === 0) {
      issues.push({
        id: `rule_feature_no_scenarios_${feature.featureId}`,
        title: `叶子功能未定义验收场景`,
        description: `功能结点 "${feature.featureName}" 作为叶子业务结点，尚未描述任何典型成功场景（User Story），可能导致需求不够具象化。`,
        severity: 'medium',
        status: 'open',
        relatedNodeIds: [feature.featureId.toString()],
        suggestedProjection: 'goal',
        category: 'rule_gap',
      });
    }

    // 4. Scenarios without AC
    for (const sc of feature.scenarios || []) {
      if ((sc.acceptanceCriteria || []).length === 0) {
        issues.push({
          id: `rule_scenario_no_ac_${sc.scenarioId}`,
          title: `成功场景缺少验收标准`,
          description: `功能 "${feature.featureName}" 下的场景 "${sc.scenarioName}" 缺少对应的成功标准 (AC)，开发与测试人员将无法验证功能终态。`,
          severity: 'high',
          status: 'open',
          relatedNodeIds: [feature.featureId.toString()],
          suggestedProjection: 'goal',
          category: 'rule_gap',
        });
      }
    }
  }

  // 5. Business objects without attributes
  for (const bo of businessObjects) {
    if ((bo.businessObjectAttributes || []).length === 0) {
      issues.push({
        id: `rule_bo_no_attrs_${bo.businessObjectId}`,
        title: `业务对象缺少字段属性定义`,
        description: `数据实体 "${bo.businessObjectName}" 没有包含任何具体字段属性，建议在其下添加代表业务字段的属性（如 ID、名称、状态等）。`,
        severity: 'medium',
        status: 'open',
        relatedNodeIds: [bo.businessObjectId.toString()],
        suggestedProjection: 'data',
        category: 'rule_gap',
      });
    }
  }

  // 6. Flows without steps
  for (const flow of flows) {
    if ((flow.flowSteps || []).length === 0) {
      issues.push({
        id: `rule_flow_no_steps_${flow.flowId}`,
        title: `业务流程未定义任何步骤`,
        description: `业务流 "${flow.flowName}" 属于空壳流程，没有任何流转的执行步骤，请为其配置用户/系统步骤。`,
        severity: 'high',
        status: 'open',
        relatedNodeIds: [flow.flowId.toString()],
        suggestedProjection: 'system',
      });
    }
  }

  return issues;
};
