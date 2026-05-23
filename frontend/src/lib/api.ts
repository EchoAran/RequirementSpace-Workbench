import {
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
  ScopeStatus
} from '@/core/schema';

// Helper to generate IDs
const generateIntId = (): number => Math.floor(1000 + Math.random() * 9000);
const generateStringId = (prefix: string): string => `${prefix}_${Math.random().toString(36).substring(2, 9)}`;

// Storage keys
const STORAGE_KEY = 'rs_workspace_spaces';
const DRAFT_STORAGE_KEY = 'rs_workspace_drafts';

// -------------------------------------------------------------
// Realistic Demo Templates for Bootstrap
// -------------------------------------------------------------
const getBootstrapTemplate = (projectName: string, prompt: string): RequirementSpace => {
  const projectId = generateIntId();

  // 1. Actors
  const actors: ActorNode[] = [
    {
      kind: 'actor',
      actorId: 101,
      actorName: '固定资产管理员',
      actorDescription: '负责资产卡片的日常入库录入、属性调整与调拨发起，是系统最核心的操作者。'
    },
    {
      kind: 'actor',
      actorId: 102,
      actorName: '财务审批经理',
      actorDescription: '审阅折旧分析报告、资产估值变化，并审批高价值固定资产的报废与调拨。'
    }
  ];

  // 2. Scenarios (Success standard / Acceptance criteria embedded)
  const scenariosForFeature21: ScenarioNode[] = [
    {
      kind: 'scenario',
      scenarioId: 201,
      scenarioName: '新购固定资产一键扫码入库',
      scenarioContent: '当管理员收到新购设备时，通过移动端摄像头扫描设备条形码，系统自动检索原产信息并生成预填卡片，管理员只需补充存放位置即可完成登记。',
      featureId: 21,
      actorId: 101,
      acceptanceCriteria: [
        { kind: 'acceptance_criterion', criterionId: 2011, criterionContent: '扫码后应在 1.5 秒内自动匹配品牌、型号，正确率不低于 98%' },
        { kind: 'acceptance_criterion', criterionId: 2012, criterionContent: '支持断网暂存，网络恢复后自动断点续传完成最终入库' }
      ]
    }
  ];

  const scenariosForFeature22: ScenarioNode[] = [
    {
      kind: 'scenario',
      scenarioId: 202,
      scenarioName: '年终自动计提累计折旧并推送财务凭证',
      scenarioContent: '在年终结账日，系统自动运行折旧引擎，针对“本期”范围内的资产运用双倍余额递减法计提折旧，更新账面价值并向财务系统推送过账凭证。',
      featureId: 22,
      actorId: 102,
      acceptanceCriteria: [
        { kind: 'acceptance_criterion', criterionId: 2021, criterionContent: '支持对不同资产类别（如机器设备、电子设备）配置独立的折旧计算规则' },
        { kind: 'acceptance_criterion', criterionId: 2022, criterionContent: '计算完成后需展示详细的折旧摊销明细表以供财务审计' }
      ]
    }
  ];

  // 3. Features forming a Tree
  const features: FeatureNode[] = [
    {
      kind: 'feature',
      featureId: 1,
      featureName: '资产综合运营主控板',
      featureDescription: '为资产管理员与决策层提供公司全网固定资产的价值分布、折旧速率、闲置率分析以及感知预警看板。',
      actorIds: [101, 102],
      parentId: null,
      childrenIds: [11, 12],
      scenarios: [],
      scope: {
        kind: 'scope',
        scopeId: 1001,
        scopeStatus: '本期',
        reason: '作为项目统一门户与总览界面，综合运营主控板是第一优先级交付件。',
        positiveSummary: '有助于决策层实时掌控资产状况，降低不合理闲置成本。',
        negativeSummary: '前期需要人工清理大批底账，可能导致主板数据初期的不准确。',
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    },
    {
      kind: 'feature',
      featureId: 11,
      featureName: '全维度数据大屏展示',
      featureDescription: '支持价值环形分布图、高负荷预警大屏展示，实时映射资产流动状态。',
      actorIds: [102],
      parentId: 1,
      childrenIds: [],
      scenarios: [],
      scope: {
        kind: 'scope',
        scopeId: 1002,
        scopeStatus: '本期',
        reason: '数据大屏是汇报核心，需支持图表动态下钻。',
        positiveSummary: '界面极为现代直观，方便多视角分析。',
        negativeSummary: '对后台数据处理的吞吐量与时效性要求极高。',
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    },
    {
      kind: 'feature',
      featureId: 12,
      featureName: '协同预警快速处置通道',
      featureDescription: '承载感知槽的唯一预警提示（PerceptionSlot），允许点击后弹出快速填充处置卡片。',
      actorIds: [101],
      parentId: 1,
      childrenIds: [],
      scenarios: [],
      scope: {
        kind: 'scope',
        scopeId: 1003,
        scopeStatus: '本期',
        reason: '提供需求一致性诊断自愈交互，为系统敏捷演化提供闭环保障。',
        positiveSummary: '将传统 PRD 梳理变为交互式问答，用户体验感极佳。',
        negativeSummary: '底层对 AI 推演的准确性依赖程度极高。',
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    },
    {
      kind: 'feature',
      featureId: 2,
      featureName: '固定资产卡片生命周期管理',
      featureDescription: '从登记、状态更新、年数总和折旧计算到申请调拨及报废处理的生命全周期数字化底账。',
      actorIds: [101],
      parentId: null,
      childrenIds: [21, 22],
      scenarios: [],
      scope: {
        kind: 'scope',
        scopeId: 1004,
        scopeStatus: '本期',
        reason: '资产管理系统的底层数据支撑结构，优先级极高。',
        positiveSummary: '取代 Excel 手工管理，实现一物一码追踪。',
        negativeSummary: '需要设计庞大的业务对象表结构以支持自定义属性。',
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    },
    {
      kind: 'feature',
      featureId: 21,
      featureName: '智能资产登记建档',
      featureDescription: '提供资产条码扫描、拍照识别录入，自动生成包含原值、存放地的标准资产卡片。',
      actorIds: [101],
      parentId: 2,
      childrenIds: [],
      scenarios: scenariosForFeature21,
      scope: {
        kind: 'scope',
        scopeId: 1005,
        scopeStatus: '本期',
        reason: '这是系统的核心入口功能，没有登记就无法进行生命周期管理。',
        positiveSummary: '极大缩短了资产盘点时间，避免人工错漏。',
        negativeSummary: '移动端摄像头扫码存在弱光下的识别障碍风险。',
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    },
    {
      kind: 'feature',
      featureId: 22,
      featureName: '双倍余额智能折旧计算器',
      featureDescription: '基于资产购置时间、折旧年限与预计净残值，定期批量计提累计折旧并完成账面价值抵减。',
      actorIds: [101, 102],
      parentId: 2,
      childrenIds: [],
      scenarios: scenariosForFeature22,
      scope: {
        kind: 'scope',
        scopeId: 1006,
        scopeStatus: '暂缓',
        reason: '由于资产折旧公式复杂且前期数据清洗量大，此高级引擎可作为二期功能。',
        positiveSummary: '减少财务月末核算工作量，提高数据严谨性。',
        negativeSummary: '需与外部金蝶 ERP 财务系统联调，开发工期较长。',
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    }
  ];

  // 4. Business Objects
  const businessObjects: BusinessObjectNode[] = [
    {
      kind: 'business_object',
      businessObjectId: 301,
      businessObjectName: '固定资产卡片 (AssetCard)',
      businessObjectDescription: '存储实物资产全量元数据，包括条码、资产类别、折旧率、当前残值、责任部门及实物照片。',
      businessObjectAttributes: [
        {
          kind: 'business_object_attribute',
          businessObjectAttributeId: 3011,
          businessObjectAttributeName: 'assetCode',
          businessObjectAttributeDescription: '资产唯一标识条码编码',
          businessObjectAttributeType: 'String',
          businessObjectAttributeExample: 'AST-2026-0089'
        },
        {
          kind: 'business_object_attribute',
          businessObjectAttributeId: 3012,
          businessObjectAttributeName: 'originalValue',
          businessObjectAttributeDescription: '购置时的原始价值（原币/本币）',
          businessObjectAttributeType: 'BigDecimal',
          businessObjectAttributeExample: '12800.00'
        },
        {
          kind: 'business_object_attribute',
          businessObjectAttributeId: 3013,
          businessObjectAttributeName: 'netValue',
          businessObjectAttributeDescription: '计提折旧后的账面净价值',
          businessObjectAttributeType: 'BigDecimal',
          businessObjectAttributeExample: '8400.00'
        },
        {
          kind: 'business_object_attribute',
          businessObjectAttributeId: 3014,
          businessObjectAttributeName: 'lifecycleStatus',
          businessObjectAttributeDescription: '资产状态：闲置、领用中、维修中、报废',
          businessObjectAttributeType: 'Enum',
          businessObjectAttributeExample: '领用中'
        }
      ]
    }
  ];

  // 5. Flows & FlowSteps
  const flows: FlowNode[] = [
    {
      kind: 'flow',
      flowId: 401,
      flowName: '资产领用与调拨主管审批流',
      flowDescription: '规范非本部门固定资产的调拨流程，包括领用申请、部门主管预审批、资产管理员出库划拨。',
      featureIds: [12, 21],
      flowSteps: [
        {
          kind: 'flow_step',
          stepId: 4011,
          stepName: '发起调拨领用申请',
          stepDescription: '资产管理员选择一张“闲置”状态的资产卡片，填写目标使用部门和理由，提交申请。',
          stepType: 'actorAction',
          actorIds: [101],
          inputBusinessObjectIds: [301],
          outputBusinessObjectIds: [],
          nextStepIds: [4012]
        },
        {
          kind: 'flow_step',
          stepId: 4012,
          stepName: '部门主管线上审批',
          stepDescription: '调拨发起部门主管和目标领用部门主管审阅调拨原因，决定批准或退回修改。',
          stepType: 'judgment',
          actorIds: [102],
          inputBusinessObjectIds: [301],
          outputBusinessObjectIds: [],
          nextStepIds: [4013]
        },
        {
          kind: 'flow_step',
          stepId: 4013,
          stepName: '系统流转并变更资产归属',
          stepDescription: '双向审批通过后，系统自动修改固定资产卡片的“责任部门”与“ lifecycleStatus ”字段，生成出库划拨指令。',
          stepType: 'systemAction',
          actorIds: [],
          inputBusinessObjectIds: [],
          outputBusinessObjectIds: [301],
          nextStepIds: []
        }
      ]
    }
  ];

  // 6. Active Suggestion (PerceptionSlot - Global recommendation)
  const perceptionSlot: PerceptionSlot = {
    kind: 'perception_slot',
    perceptionSlotId: 801,
    perceptionKind: '功能叶子结点',
    perceptionDescription: '主功能域『固定资产卡片生命周期管理』目前只配备了“登记”和“折旧”，为了业务闭环，建议补充一个用于『资产调拨处置』的第三级叶子节点功能。'
  };

  return {
    kind: 'requirement_space',
    projectId,
    projectName: projectName || '固定资产数字化协作建模空间',
    projectDescription: prompt.substring(0, 100) || '基于双倍折旧与一物一码的高一致性数字化建模工作台',
    userRequirements: prompt || '我想搭建一个全生命周期固定资产系统。',
    perceptionSlot,
    actors,
    features,
    businessObjects,
    flows
  };
};

// -------------------------------------------------------------
// Database Persistence Helpers
// -------------------------------------------------------------
const loadSpacesFromStore = (): RequirementSpace[] => {
  try {
    const list = localStorage.getItem(STORAGE_KEY);
    return list ? JSON.parse(list) : [];
  } catch {
    return [];
  }
};

const saveSpacesToStore = (spaces: RequirementSpace[]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(spaces));
};

const loadDraftsFromStore = (): Record<string, any> => {
  try {
    const list = localStorage.getItem(DRAFT_STORAGE_KEY);
    return list ? JSON.parse(list) : {};
  } catch {
    return {};
  }
};

const saveDraftsToStore = (drafts: Record<string, any>) => {
  localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(drafts));
};

// Initialize with a rich project if none exists so the app isn't empty on load
const ensureInitialProjects = () => {
  const list = loadSpacesFromStore();
  const isLegacy = list.length > 0 && list.some(s => 
    !s.actors || !s.features || !s.businessObjects || !s.flows || !s.projectId
  );
  if (list.length === 0 || isLegacy) {
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    } catch (e) {}
    const defaultSpace = getBootstrapTemplate(
      '智能资产管理工作台 (本地示范)',
      '构建一套一物一码资产卡片，能够拍照录入，自动按部门划拨，支持财务在年终时运行年数总和折旧计提算法，生成审计图表。'
    );
    saveSpacesToStore([defaultSpace]);
  }
};
ensureInitialProjects();

// -------------------------------------------------------------
// Core Mock API Implementation (Perfect representation of backend routers)
// -------------------------------------------------------------
export const workspaceApi = {
  // 1. List Projects
  list: async () => {
    const list = loadSpacesFromStore();
    return list.map(s => ({
      id: s.projectId.toString(),
      name: s.projectName,
      idea: s.userRequirements,
      updatedAt: new Date().toISOString(), // Mock modification time
      status: s.features.some(f => f.scope?.scopeStatus === '暂缓') ? '待确认缺口' : '设计中',
      issueCount: s.features.filter(f => f.actorIds.length === 0).length, // Mismatched rule counts
      nodeCount: s.actors.length + s.features.length + s.businessObjects.length + s.flows.length
    }));
  },

  // 2. Get Project by ID
  getById: async (id: string | number): Promise<RequirementSpace> => {
    const list = loadSpacesFromStore();
    const pid = typeof id === 'string' ? parseInt(id, 10) : id;
    const space = list.find(s => s.projectId === pid);
    if (!space) throw new Error(`项目空间 '${pid}' 未找到`);
    return space;
  },

  // 3. Save Project (For manual edits / updates)
  save: async (space: RequirementSpace): Promise<RequirementSpace> => {
    const list = loadSpacesFromStore();
    const index = list.findIndex(s => s.projectId === space.projectId);
    if (index === -1) {
      list.push(space);
    } else {
      list[index] = space;
    }
    saveSpacesToStore(list);
    return space;
  },

  // 4. Delete Project
  delete: async (id: string | number): Promise<void> => {
    const list = loadSpacesFromStore();
    const pid = typeof id === 'string' ? parseInt(id, 10) : id;
    const filtered = list.filter(s => s.projectId !== pid);
    saveSpacesToStore(filtered);
  },

  // -------------------------------------------------------------
  // Onboarding & Project Creation Drafts
  // -------------------------------------------------------------
  createBlankProject: async (payload: { user_requirements: string; project_name?: string; project_description?: string }) => {
    const pid = generateIntId();
    const space: RequirementSpace = {
      kind: 'requirement_space',
      projectId: pid,
      projectName: payload.project_name || '全新空白产品模型',
      projectDescription: payload.project_description || '自力更生，由零起点的产品定义模型。',
      userRequirements: payload.user_requirements,
      perceptionSlot: {
        kind: 'perception_slot',
        perceptionSlotId: generateIntId(),
        perceptionKind: '角色结点',
        perceptionDescription: '当前项目为空白起点。为了开启建模，建议在 What 阶段首先创建系统关键参与者角色。'
      },
      actors: [],
      features: [],
      businessObjects: [],
      flows: []
    };

    const list = loadSpacesFromStore();
    list.push(space);
    saveSpacesToStore(list);

    return {
      project_id: pid,
      project_name: space.projectName,
      project_description: space.projectDescription,
      message: 'project_created'
    };
  },

  createProjectCreationDraft: async (payload: { user_requirements: string; project_name?: string; project_description?: string }) => {
    const draftId = generateStringId('draft_proj');
    const userRequirements = payload.user_requirements;
    const projectName = payload.project_name || 'AI 推演：资产协同看板';
    const projectDescription = payload.project_description || '智能构建公司设备生命周期建模流程。';

    // Mock generated list
    const actors = [
      { actor_name: '系统资产管理员', actor_description: '操作建档、报废、发起内部移交流程。' },
      { actor_name: '部门主管审批人', actor_description: '负责所在部门名下资产移出或申领的决策通过。' }
    ];

    const features = [
      { feature_name: '资产信息总控看板', feature_description: '图形化展现资产类别、金额折损与异常感知槽。', actor_names: ['系统资产管理员'] },
      { feature_name: '扫码即录自动建档', feature_description: '一键扫描设备资产贴纸条码，读取出厂信息入库。', actor_names: ['系统资产管理员'] },
      { feature_name: '双边线上审核调拨流', feature_description: '双向审批通过，流转固定资产卡片，自动记录折旧变化。', actor_names: ['部门主管审批人', '系统资产管理员'] }
    ];

    const draft = {
      draft_id: draftId,
      user_requirements: userRequirements,
      project_preview: { project_name: projectName, project_description: projectDescription },
      actors,
      features
    };

    const drafts = loadDraftsFromStore();
    drafts[draftId] = draft;
    saveDraftsToStore(drafts);

    return draft;
  },

  regenerateProjectCreationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    const existing = drafts[draftId];
    if (!existing) throw new Error('draft_not_found');

    // Make slight modification to show mock regeneration
    const updated = {
      ...existing,
      project_preview: {
        project_name: existing.project_preview.project_name + ' (重推演版)',
        project_description: '根据优化诉求，重塑了折旧计提算法及Kano看板模块的依赖拓扑。'
      },
      features: [
        ...existing.features,
        { feature_name: '高级累计折旧计提计算器', feature_description: '支持年限总和法与年数余额递减法的批量折旧批处理。', actor_names: ['财务审批经理'] }
      ]
    };

    drafts[draftId] = updated;
    saveDraftsToStore(drafts);
    return updated;
  },

  confirmProjectCreationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    const draft = drafts[draftId];
    if (!draft) throw new Error('draft_not_found');

    const pid = generateIntId();
    const space: RequirementSpace = {
      kind: 'requirement_space',
      projectId: pid,
      projectName: draft.project_preview.project_name,
      projectDescription: draft.project_preview.project_description,
      userRequirements: draft.user_requirements,
      perceptionSlot: {
        kind: 'perception_slot',
        perceptionSlotId: generateIntId(),
        perceptionKind: '场景结点',
        perceptionDescription: '项目底账框架已生成！为了描述具体用例需求，建议前往 What 阶段，为『扫码即录自动建档』功能创建一条成功业务场景。'
      },
      actors: draft.actors.map((a: any, i: number) => ({
        kind: 'actor',
        actorId: 200 + i,
        actorName: a.actor_name,
        actorDescription: a.actor_description
      })),
      features: draft.features.map((f: any, i: number) => ({
        kind: 'feature',
        featureId: 300 + i,
        featureName: f.feature_name,
        featureDescription: f.feature_description,
        actorIds: [200], // Associate with first actor
        parentId: null,
        childrenIds: [],
        scenarios: [],
        scope: {
          kind: 'scope',
          scopeId: 400 + i,
          scopeStatus: '本期',
          reason: '基于 AI 初始化导入默认判定。',
          positiveSummary: '有助于核心流程贯通。',
          negativeSummary: '略微增加系统复杂度。',
          positivePictureBase64: null,
          negativePictureBase64: null
        }
      })),
      businessObjects: [],
      flows: []
    };

    const list = loadSpacesFromStore();
    list.push(space);
    saveSpacesToStore(list);

    delete drafts[draftId];
    saveDraftsToStore(drafts);

    return {
      project_id: pid,
      project_name: space.projectName,
      project_description: space.projectDescription,
      message: 'project_created'
    };
  },

  discardProjectCreationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    delete drafts[draftId];
    saveDraftsToStore(drafts);
    return { draft_id: draftId, message: 'draft_discarded' };
  },

  // -------------------------------------------------------------
  // Actor Generation Drafts
  // -------------------------------------------------------------
  createActorGenerationDraft: async (projectId: number) => {
    const draftId = generateStringId('draft_actor');
    const actors = [
      { actor_name: '高级备件管理员', actor_description: '监管仓库备品备件调拨与损耗折余统计。' },
      { actor_name: '盘点外协人员', actor_description: '使用扫码枪定期录入实物资产，进行财务数据预校验。' }
    ];

    const draft = { draft_id: draftId, project_id: projectId, actors };
    const drafts = loadDraftsFromStore();
    drafts[draftId] = draft;
    saveDraftsToStore(drafts);

    return draft;
  },

  confirmActorGenerationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    const draft = drafts[draftId];
    if (!draft) throw new Error('draft_not_found');

    const space = await workspaceApi.getById(draft.project_id);
    const addedActors: ActorNode[] = draft.actors.map((a: any, i: number) => ({
      kind: 'actor',
      actorId: generateIntId(),
      actorName: a.actor_name,
      actorDescription: a.actor_description
    }));

    space.actors = [...space.actors, ...addedActors];
    space.perceptionSlot = null; // Clear suggestion
    await workspaceApi.save(space);

    delete drafts[draftId];
    saveDraftsToStore(drafts);

    return {
      project_id: space.projectId,
      actor_count: addedActors.length,
      message: 'actors_created'
    };
  },

  // -------------------------------------------------------------
  // Feature Generation Drafts
  // -------------------------------------------------------------
  createFeatureGenerationDraft: async (projectId: number) => {
    const draftId = generateStringId('draft_feat');
    const features = [
      { feature_name: '多层库存调配划拨引擎', feature_description: '支持分库、货位、多级审批链的备品流转核心枢纽。', actor_names: ['高级备件管理员'] },
      { feature_name: '条码库标签定制化设计', feature_description: '支持自定义资产条码排版格式并一键驱动外协热敏打印机。', actor_names: ['盘点外协人员'] }
    ];

    const draft = { draft_id: draftId, project_id: projectId, features };
    const drafts = loadDraftsFromStore();
    drafts[draftId] = draft;
    saveDraftsToStore(drafts);

    return draft;
  },

  confirmFeatureGenerationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    const draft = drafts[draftId];
    if (!draft) throw new Error('draft_not_found');

    const space = await workspaceApi.getById(draft.project_id);
    const addedFeatures: FeatureNode[] = draft.features.map((f: any, i: number) => ({
      kind: 'feature',
      featureId: generateIntId(),
      featureName: f.feature_name,
      featureDescription: f.feature_description,
      actorIds: space.actors.length > 0 ? [space.actors[0].actorId] : [],
      parentId: null,
      childrenIds: [],
      scenarios: [],
      scope: {
        kind: 'scope',
        scopeId: generateIntId(),
        scopeStatus: '本期',
        reason: 'AI 导入推荐核心能力模块。',
        positiveSummary: '增强系统底账可用性。',
        negativeSummary: null,
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    }));

    space.features = [...space.features, ...addedFeatures];
    space.perceptionSlot = null; // Clear suggestion
    await workspaceApi.save(space);

    delete drafts[draftId];
    saveDraftsToStore(drafts);

    return {
      project_id: space.projectId,
      feature_count: addedFeatures.length,
      message: 'features_created'
    };
  },

  // -------------------------------------------------------------
  // Flow & Business Object Generation Drafts
  // -------------------------------------------------------------
  createFlowGenerationDraft: async (projectId: number) => {
    const draftId = generateStringId('draft_flow');

    const business_objects = [
      {
        business_object_name: '资产盘点实录 (AssetAudit)',
        business_object_description: '包含外协扫码所得条形码、拍照核实状况、经纬度及实录账面偏差率。',
        business_object_attributes: [
          { business_object_attribute_name: 'auditId', business_object_attribute_description: '盘点历史日志主ID', business_object_attribute_type: 'int', business_object_attribute_example: '9002' },
          { business_object_attribute_name: 'biasRate', business_object_attribute_description: '盘点实物与资产库的差异率数值', business_object_attribute_type: 'double', business_object_attribute_example: '0.04' }
        ]
      }
    ];

    const flows = [
      {
        flow_name: '定期批量数据大盘审计流程',
        flow_description: '将外协实物盘点数据与账面折余凭证进行差额比对，触发感知异常推送主管审阅。',
        feature_names: ['全维度数据大屏展示'],
        flow_steps: [
          { step_name: '采集离线扫码盘点数据', step_description: '导入扫码实录并检查经纬度与拍照状态。', step_type: 'actorAction', actor_names: ['固定资产管理员'], input_business_object_names: ['资产盘点实录'], output_business_object_names: [] },
          { step_name: '比对折余资产偏差率', step_description: '自动对实盘数量和财务账面进行核销审计，过滤高风险偏差。', step_type: 'systemAction', actor_names: [], input_business_object_names: [], output_business_object_names: [] },
          { step_name: '生成预警推送至主管端', step_description: '当偏离度大于 5% 时生成决策任务送审财务审批经理。', step_type: 'judgment', actor_names: ['财务审批经理'], input_business_object_names: [], output_business_object_names: [] }
        ]
      }
    ];

    const draft = {
      draft_id: draftId,
      project_id: projectId,
      generation_mode: 'full',
      leaf_feature_count: 3,
      business_objects,
      flows
    };

    const drafts = loadDraftsFromStore();
    drafts[draftId] = draft;
    saveDraftsToStore(drafts);

    return draft;
  },

  confirmFlowGenerationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    const draft = drafts[draftId];
    if (!draft) throw new Error('draft_not_found');

    const space = await workspaceApi.getById(draft.project_id);

    // 1. Add business objects
    const addedObjects: BusinessObjectNode[] = draft.business_objects.map((bo: any) => {
      const boId = generateIntId();
      return {
        kind: 'business_object',
        businessObjectId: boId,
        businessObjectName: bo.business_object_name,
        businessObjectDescription: bo.business_object_description,
        businessObjectAttributes: bo.business_object_attributes.map((attr: any) => ({
          kind: 'business_object_attribute',
          businessObjectAttributeId: generateIntId(),
          businessObjectAttributeName: attr.business_object_attribute_name,
          businessObjectAttributeDescription: attr.business_object_attribute_description,
          businessObjectAttributeType: attr.business_object_attribute_type,
          businessObjectAttributeExample: attr.business_object_attribute_example
        }))
      };
    });

    // 2. Add flows
    let stepCount = 0;
    const addedFlows: FlowNode[] = draft.flows.map((fl: any) => {
      const flId = generateIntId();
      const steps: FlowStepNode[] = fl.flow_steps.map((st: any, i: number) => {
        stepCount++;
        return {
          kind: 'flow_step',
          stepId: generateIntId(),
          position: i + 1,
          stepName: st.step_name,
          stepDescription: st.step_description,
          stepType: st.step_type as any,
          actorIds: space.actors.length > 0 ? [space.actors[0].actorId] : [],
          inputBusinessObjectIds: addedObjects.length > 0 ? [addedObjects[0].businessObjectId] : [],
          outputBusinessObjectIds: [],
          nextStepIds: [] // Will link later
        };
      });

      // Simple sequential link
      for (let i = 0; i < steps.length - 1; i++) {
        steps[i].nextStepIds = [steps[i + 1].stepId];
      }

      return {
        kind: 'flow',
        flowId: flId,
        flowName: fl.flow_name,
        flowDescription: fl.flow_description,
        featureIds: space.features.length > 0 ? [space.features[0].featureId] : [],
        flowSteps: steps
      };
    });

    space.businessObjects = [...space.businessObjects, ...addedObjects];
    space.flows = [...space.flows, ...addedFlows];
    space.perceptionSlot = null; // Clear suggestion
    await workspaceApi.save(space);

    delete drafts[draftId];
    saveDraftsToStore(drafts);

    return {
      project_id: space.projectId,
      business_object_count: addedObjects.length,
      flow_count: addedFlows.length,
      flow_step_count: stepCount,
      message: 'flows_created'
    };
  },

  // -------------------------------------------------------------
  // Scenario Generation Drafts
  // -------------------------------------------------------------
  createScenarioGenerationDraft: async (projectId: number, featureId?: number) => {
    const draftId = generateStringId('draft_scen');

    // Simulate scenario generation preview
    const scenarios = [
      {
        feature_id: featureId || 21,
        feature_name: '扫码即录自动建档',
        actor_id: 101,
        actor_name: '固定资产管理员',
        scenario_name: '多品备件拍照录入入库场景',
        scenario_content: '备件管理员收齐整箱调拨阀门时，启用拍照多品检索功能，AI 自动切片分离出四个不同阀门垫圈，用户一键确认即可批量登账入库。'
      }
    ];

    const draft = {
      draft_id: draftId,
      project_id: projectId,
      generation_mode: featureId ? 'single' : 'full',
      feature_id: featureId || null,
      scenarios
    };

    const drafts = loadDraftsFromStore();
    drafts[draftId] = draft;
    saveDraftsToStore(drafts);

    return draft;
  },

  confirmScenarioGenerationDraft: async (draftId: string, payload: { generate_acceptance_criteria: boolean }) => {
    const drafts = loadDraftsFromStore();
    const draft = drafts[draftId];
    if (!draft) throw new Error('draft_not_found');

    const space = await workspaceApi.getById(draft.project_id);
    let totalCriteria = 0;

    const addedScenarios: ScenarioNode[] = draft.scenarios.map((sc: any) => {
      const scId = generateIntId();
      const criteria: AcceptanceCriterionNode[] = payload.generate_acceptance_criteria ? [
        { kind: 'acceptance_criterion', criterionId: generateIntId(), criterionContent: '图像识别阀门垫圈类别符合率达 95% 以上' },
        { kind: 'acceptance_criterion', criterionId: generateIntId(), criterionContent: '批量确认按钮的延迟响应小于 500 毫秒' }
      ] : [];

      totalCriteria += criteria.length;

      return {
        kind: 'scenario',
        scenarioId: scId,
        scenarioName: sc.scenario_name,
        scenarioContent: sc.scenario_content,
        featureId: sc.feature_id,
        actorId: sc.actor_id,
        acceptanceCriteria: criteria
      };
    });

    // Append to corresponding features
    space.features = space.features.map(feat => {
      const matchScenarios = addedScenarios.filter(s => s.featureId === feat.featureId);
      if (matchScenarios.length > 0) {
        return {
          ...feat,
          scenarios: [...feat.scenarios, ...matchScenarios]
        };
      }
      return feat;
    });

    space.perceptionSlot = null; // Clear suggestion
    await workspaceApi.save(space);

    delete drafts[draftId];
    saveDraftsToStore(drafts);

    return {
      project_id: space.projectId,
      scenario_count: addedScenarios.length,
      acceptance_criterion_count: totalCriteria,
      message: 'scenarios_created'
    };
  },

  // -------------------------------------------------------------
  // Acceptance Criteria Generation Drafts
  // -------------------------------------------------------------
  createAcceptanceCriteriaGenerationDraft: async (projectId: number, scenarioIds?: number[]) => {
    const draftId = generateStringId('draft_ac');

    const scenario_acceptance_criteria = [
      {
        scenario_id: scenarioIds && scenarioIds.length > 0 ? scenarioIds[0] : 201,
        scenario_name: '新购固定资产一键扫码入库',
        acceptance_criteria: [
          '支持识别标准 Code 128 条形码以及二维码',
          '若条形码磨损无法读取，系统应自动转入手动序列号登记页面并提示报错'
        ]
      }
    ];

    const draft = {
      draft_id: draftId,
      project_id: projectId,
      scenario_acceptance_criteria
    };

    const drafts = loadDraftsFromStore();
    drafts[draftId] = draft;
    saveDraftsToStore(drafts);

    return draft;
  },

  confirmAcceptanceCriteriaGenerationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    const draft = drafts[draftId];
    if (!draft) throw new Error('draft_not_found');

    const space = await workspaceApi.getById(draft.project_id);
    let acCount = 0;

    space.features = space.features.map(feat => {
      const updatedScenarios = feat.scenarios.map(sc => {
        const matchDraft = draft.scenario_acceptance_criteria.find((item: any) => item.scenario_id === sc.scenarioId);
        if (matchDraft) {
          const addedAc = matchDraft.acceptance_criteria.map((c: string) => {
            acCount++;
            return {
              kind: 'acceptance_criterion',
              criterionId: generateIntId(),
              criterionContent: c
            };
          });
          return {
            ...sc,
            acceptanceCriteria: [...sc.acceptanceCriteria, ...addedAc]
          };
        }
        return sc;
      });
      return {
        ...feat,
        scenarios: updatedScenarios
      };
    });

    space.perceptionSlot = null; // Clear suggestion
    await workspaceApi.save(space);

    delete drafts[draftId];
    saveDraftsToStore(drafts);

    return {
      project_id: space.projectId,
      acceptance_criterion_count: acCount,
      message: 'acceptance_criteria_created'
    };
  },

  // -------------------------------------------------------------
  // Scope Generation Drafts (Kano positive/negative/reasoning)
  // -------------------------------------------------------------
  createScopeGenerationDraft: async (projectId: number) => {
    const draftId = generateStringId('draft_scope');

    const scopes = [
      {
        feature_id: 11,
        feature_name: '全维度数据大屏展示',
        scope_status: '本期',
        reason: '数据可视化模块有利于管理决策，首要落地交付。',
        positive_summary: '决策层实时盘点账面盈亏与利用率。',
        negative_summary: '需要保证底层多源数据采集的即时有效。'
      },
      {
        feature_id: 22,
        feature_name: '双倍余额智能折旧计算器',
        scope_status: '暂缓',
        reason: '计提折旧需要精算对接财务系统，规则相对滞后，可在二期配合系统成熟后推广运行。',
        positive_summary: '极大缓解月末手工结账烦琐负担。',
        negative_summary: '金蝶与用友等财务凭证第三方接口对接存在技术延阻风险。'
      }
    ];

    const draft = {
      draft_id: draftId,
      project_id: projectId,
      scopes
    };

    const drafts = loadDraftsFromStore();
    drafts[draftId] = draft;
    saveDraftsToStore(drafts);

    return draft;
  },

  confirmScopeGenerationDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    const draft = drafts[draftId];
    if (!draft) throw new Error('draft_not_found');

    const space = await workspaceApi.getById(draft.project_id);

    space.features = space.features.map(feat => {
      const matchScope = draft.scopes.find((s: any) => s.feature_id === feat.featureId);
      if (matchScope) {
        return {
          ...feat,
          scope: {
            kind: 'scope',
            scopeId: generateIntId(),
            scopeStatus: matchScope.scope_status as ScopeStatus,
            reason: matchScope.reason,
            positiveSummary: matchScope.positive_summary,
            negativeSummary: matchScope.negative_summary,
            positivePictureBase64: null,
            negativePictureBase64: null
          }
        };
      }
      return feat;
    });

    space.perceptionSlot = null; // Clear suggestion
    await workspaceApi.save(space);

    delete drafts[draftId];
    saveDraftsToStore(drafts);

    return {
      project_id: space.projectId,
      scope_count: draft.scopes.length,
      message: 'scopes_created'
    };
  },

  discardDraft: async (draftId: string) => {
    const drafts = loadDraftsFromStore();
    delete drafts[draftId];
    saveDraftsToStore(drafts);
    return { draft_id: draftId, message: 'draft_discarded' };
  },

  exportMarkdown: async (projectId: string | number): Promise<string> => {
    const space = await workspaceApi.getById(projectId);
    return `# ${space.projectName}\n\n${space.projectDescription}\n\n## 核心角色\n${space.actors.map(a => `- **${a.actorName}**: ${a.actorDescription}`).join('\n')}\n\n## 功能模块\n${space.features.map(f => `- **${f.featureName}**: ${f.featureDescription}`).join('\n')}`;
  },

  exportJson: async (projectId: string | number): Promise<any> => {
    return workspaceApi.getById(projectId);
  },

  impactPreview: async (projectId: string | number): Promise<any> => {
    const space = await workspaceApi.getById(projectId);
    return {
      affected_scenarios_count: space.features.reduce((acc, curr) => acc + curr.scenarios.length, 0),
      affected_flows_count: space.flows.length,
      affected_objects_count: space.businessObjects.length,
      message: 'Scope change impact analyzed successfully.'
    };
  }
};
