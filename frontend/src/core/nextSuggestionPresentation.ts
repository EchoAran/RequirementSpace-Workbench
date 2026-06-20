import { Finding } from './schema';

export type SuggestionPresentation = {
  label: string;
  loadingLabel: string;
  icon: 'generate' | 'navigate' | 'open' | 'wait' | 'retry';
  disabled?: boolean;
};

export function getNextSuggestionPresentation(finding: Finding): SuggestionPresentation {
  const code = finding.code || '';
  const action = finding.metadata?.action || {};
  const kind = action.kind || '';
  const draftType = action.draft_type || action.draftType || '';

  // --- 1. Prioritize action.kind (Action-driven) ---
  if (kind) {
    if (kind === 'create_draft') {
      let name = '草稿';
      if (draftType.includes('actor')) name = '参与者草稿';
      else if (draftType.includes('feature')) name = '功能草稿';
      else if (draftType.includes('scenario')) name = '场景草稿';
      else if (draftType.includes('acceptance_criteria') || draftType.includes('ac')) name = '成功标准草稿';
      else if (draftType.includes('flow')) name = '流程与业务对象草稿';
      else if (draftType.includes('scope')) name = '范围草稿';

      return {
        label: `生成${name}`,
        loadingLabel: `正在生成${name}...`,
        icon: 'generate',
      };
    }

    if (kind === 'navigate') {
      const route = action.route || '';
      if (route.includes('/how') || route.includes('/flow')) {
        return {
          label: '进入 How 阶段',
          loadingLabel: '正在跳转至 How 阶段...',
          icon: 'navigate',
        };
      }
      if (route.includes('/scope')) {
        return {
          label: '进入 Scope 阶段',
          loadingLabel: '正在跳转至 Scope 阶段...',
          icon: 'navigate',
        };
      }
      if (route.includes('/preview')) {
        if (code === 'PREVIEW_READY') {
          return {
            label: '查看预览',
            loadingLabel: '正在打开预览...',
            icon: 'navigate',
          };
        }
        return {
          label: '进入预览阶段',
          loadingLabel: '正在跳转至预览阶段...',
          icon: 'navigate',
        };
      }
      if (code === 'STAGE_LOCKED') {
        return {
          label: '进入前一阶段',
          loadingLabel: '正在返回前一阶段...',
          icon: 'navigate',
        };
      }
      return {
        label: '进入 对应阶段',
        loadingLabel: '正在跳转...',
        icon: 'navigate',
      };
    }

    if (kind === 'open_panel') {
      const panel = action.panel || '';
      if (panel === 'feature' || code === 'BIND_ACTORS_TO_FEATURE') {
        return {
          label: '打开关联面板',
          loadingLabel: '正在打开参与者绑定面板...',
          icon: 'open',
        };
      }
      if (code === 'COMPLETE_FLOW_STEPS') {
        return {
          label: '完善流程步骤',
          loadingLabel: '正在定位至流程编辑器...',
          icon: 'open',
        };
      }
      if (panel === 'perception_slot' || code.endsWith('_SLOT')) {
        return {
          label: '查看建议',
          loadingLabel: '正在定位至缺失项建议...',
          icon: 'open',
        };
      }
      return {
        label: '打开面板',
        loadingLabel: '正在打开编辑面板...',
        icon: 'open',
      };
    }

    if (kind === 'wait') {
      return {
        label: '查看分析状态',
        loadingLabel: '正在查询分析状态...',
        icon: 'wait',
      };
    }

    if (kind === 'retry') {
      return {
        label: '重新诊断',
        loadingLabel: '正在重新发起感知诊断...',
        icon: 'retry',
      };
    }
  }

  // --- 2. Check draftType second (if kind is not matched or missing) ---
  if (draftType) {
    let name = '草稿';
    if (draftType.includes('actor')) name = '参与者草稿';
    else if (draftType.includes('feature')) name = '功能草稿';
    else if (draftType.includes('scenario')) name = '场景草稿';
    else if (draftType.includes('acceptance_criteria') || draftType.includes('ac')) name = '成功标准草稿';
    else if (draftType.includes('flow')) name = '流程与业务对象草稿';
    else if (draftType.includes('scope')) name = '范围草稿';

    return {
      label: `生成${name}`,
      loadingLabel: `正在生成${name}...`,
      icon: 'generate',
    };
  }

  // --- 3. Fallback to code (Code-driven) ---
  switch (code) {
    case 'GENERATE_ACTORS':
      return {
        label: '生成参与者草稿',
        loadingLabel: '正在生成参与者草稿...',
        icon: 'generate',
      };
    case 'GENERATE_FEATURES':
      return {
        label: '生成功能草稿',
        loadingLabel: '正在生成功能草稿...',
        icon: 'generate',
      };
    case 'GENERATE_SCENARIOS':
      return {
        label: '生成场景草稿',
        loadingLabel: '正在生成场景草稿...',
        icon: 'generate',
      };
    case 'GENERATE_ACCEPTANCE_CRITERIA':
      return {
        label: '生成成功标准草稿',
        loadingLabel: '正在生成成功标准草稿...',
        icon: 'generate',
      };
    case 'GENERATE_FLOWS_AND_BUSINESS_OBJECTS':
      return {
        label: '生成流程与业务对象草稿',
        loadingLabel: '正在生成流程与业务对象草稿...',
        icon: 'generate',
      };
    case 'GENERATE_SCOPE':
      return {
        label: '生成范围草稿',
        loadingLabel: '正在生成范围草稿...',
        icon: 'generate',
      };
    case 'ENTER_HOW':
      return {
        label: '进入 How 阶段',
        loadingLabel: '正在跳转至 How 阶段...',
        icon: 'navigate',
      };
    case 'ENTER_SCOPE':
      return {
        label: '进入 Scope 阶段',
        loadingLabel: '正在跳转至 Scope 阶段...',
        icon: 'navigate',
      };
    case 'ENTER_PREVIEW':
      return {
        label: '进入预览阶段',
        loadingLabel: '正在跳转至预览阶段...',
        icon: 'navigate',
      };
    case 'PREVIEW_READY':
      return {
        label: '查看预览',
        loadingLabel: '正在打开预览...',
        icon: 'navigate',
      };
    case 'STAGE_LOCKED':
      return {
        label: '进入前一阶段',
        loadingLabel: '正在返回前一阶段...',
        icon: 'navigate',
      };
    case 'BIND_ACTORS_TO_FEATURE':
      return {
        label: '打开关联面板',
        loadingLabel: '正在打开参与者绑定面板...',
        icon: 'open',
      };
    case 'COMPLETE_FLOW_STEPS':
      return {
        label: '完善流程步骤',
        loadingLabel: '正在定位至流程编辑器...',
        icon: 'open',
      };
  }

  if (code.endsWith('_PERCEPTION_RUNNING')) {
    return {
      label: '查看分析状态',
      loadingLabel: '正在查询分析状态...',
      icon: 'wait',
    };
  }

  if (code.endsWith('_PERCEPTION_FAILED')) {
    return {
      label: '重新诊断',
      loadingLabel: '正在重新发起感知诊断...',
      icon: 'retry',
    };
  }

  if (code.endsWith('_SLOT')) {
    return {
      label: '查看建议',
      loadingLabel: '正在定位至缺失项建议...',
      icon: 'open',
    };
  }

  // --- 4. Final Fallback ---
  return {
    label: '执行建议',
    loadingLabel: '正在处理...',
    icon: 'open',
  };
}
