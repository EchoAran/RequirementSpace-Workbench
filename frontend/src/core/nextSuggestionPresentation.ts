import { Finding } from './schema';
import i18n from '@/i18n';

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

  const getDraftName = (type: string) => {
    if (type.includes('actor')) return i18n.t('suggestion.actorDraft');
    if (type.includes('feature')) return i18n.t('suggestion.featureDraft');
    if (type.includes('scenario')) return i18n.t('suggestion.scenarioDraft');
    if (type.includes('acceptance_criteria') || type.includes('ac')) return i18n.t('suggestion.acDraft');
    if (type.includes('flow')) return i18n.t('suggestion.flowDraft');
    if (type.includes('scope')) return i18n.t('suggestion.scopeDraft');
    return i18n.t('suggestion.draft');
  };

  // --- 1. Prioritize action.kind (Action-driven) ---
  if (kind) {
    if (kind === 'create_draft') {
      const name = getDraftName(draftType);
      return {
        label: i18n.t('suggestion.generate', { name }),
        loadingLabel: i18n.t('suggestion.generating', { name }),
        icon: 'generate',
      };
    }

    if (kind === 'navigate') {
      const route = action.route || '';
      if (route.includes('/how') || route.includes('/flow')) {
        return {
          label: i18n.t('suggestion.enterHow'),
          loadingLabel: i18n.t('suggestion.enteringHow'),
          icon: 'navigate',
        };
      }
      if (route.includes('/scope')) {
        return {
          label: i18n.t('suggestion.enterScope'),
          loadingLabel: i18n.t('suggestion.enteringScope'),
          icon: 'navigate',
        };
      }
      if (route.includes('/preview')) {
        if (code === 'PREVIEW_READY') {
          return {
            label: i18n.t('suggestion.viewPreview'),
            loadingLabel: i18n.t('suggestion.viewingPreview'),
            icon: 'navigate',
          };
        }
        return {
          label: i18n.t('suggestion.enterPreview'),
          loadingLabel: i18n.t('suggestion.enteringPreview'),
          icon: 'navigate',
        };
      }
      if (code === 'STAGE_LOCKED') {
        return {
          label: i18n.t('suggestion.enterPrevStage'),
          loadingLabel: i18n.t('suggestion.enteringPrevStage'),
          icon: 'navigate',
        };
      }
      return {
        label: i18n.t('suggestion.enterStage'),
        loadingLabel: i18n.t('suggestion.enteringStage'),
        icon: 'navigate',
      };
    }

    if (kind === 'open_panel') {
      const panel = action.panel || '';
      if (panel === 'feature' || code === 'BIND_ACTORS_TO_FEATURE') {
        return {
          label: i18n.t('suggestion.openRelationPanel'),
          loadingLabel: i18n.t('suggestion.openingRelationPanel'),
          icon: 'open',
        };
      }
      if (code === 'COMPLETE_FLOW_STEPS') {
        return {
          label: i18n.t('suggestion.completeFlowSteps'),
          loadingLabel: i18n.t('suggestion.completingFlowSteps'),
          icon: 'open',
        };
      }
      if (panel === 'perception_slot' || code.endsWith('_SLOT')) {
        return {
          label: i18n.t('suggestion.viewSuggestion'),
          loadingLabel: i18n.t('suggestion.viewingSuggestion'),
          icon: 'open',
        };
      }
      return {
        label: i18n.t('suggestion.openPanel'),
        loadingLabel: i18n.t('suggestion.openingPanel'),
        icon: 'open',
      };
    }

    if (kind === 'wait') {
      return {
        label: i18n.t('suggestion.checkAnalysisStatus'),
        loadingLabel: i18n.t('suggestion.checkingAnalysisStatus'),
        icon: 'wait',
      };
    }

    if (kind === 'retry') {
      return {
        label: i18n.t('suggestion.retryDiagnosis'),
        loadingLabel: i18n.t('suggestion.retryingDiagnosis'),
        icon: 'retry',
      };
    }
  }

  // --- 2. Check draftType second (if kind is not matched or missing) ---
  if (draftType) {
    const name = getDraftName(draftType);
    return {
      label: i18n.t('suggestion.generate', { name }),
      loadingLabel: i18n.t('suggestion.generating', { name }),
      icon: 'generate',
    };
  }

  // --- 3. Fallback to code (Code-driven) ---
  switch (code) {
    case 'GENERATE_ACTORS':
      return {
        label: i18n.t('suggestion.generate', { name: i18n.t('suggestion.actorDraft') }),
        loadingLabel: i18n.t('suggestion.generating', { name: i18n.t('suggestion.actorDraft') }),
        icon: 'generate',
      };
    case 'GENERATE_FEATURES':
      return {
        label: i18n.t('suggestion.generate', { name: i18n.t('suggestion.featureDraft') }),
        loadingLabel: i18n.t('suggestion.generating', { name: i18n.t('suggestion.featureDraft') }),
        icon: 'generate',
      };
    case 'GENERATE_SCENARIOS':
      return {
        label: i18n.t('suggestion.generate', { name: i18n.t('suggestion.scenarioDraft') }),
        loadingLabel: i18n.t('suggestion.generating', { name: i18n.t('suggestion.scenarioDraft') }),
        icon: 'generate',
      };
    case 'GENERATE_ACCEPTANCE_CRITERIA':
      return {
        label: i18n.t('suggestion.generate', { name: i18n.t('suggestion.acDraft') }),
        loadingLabel: i18n.t('suggestion.generating', { name: i18n.t('suggestion.acDraft') }),
        icon: 'generate',
      };
    case 'GENERATE_FLOWS_AND_BUSINESS_OBJECTS':
      return {
        label: i18n.t('suggestion.generate', { name: i18n.t('suggestion.flowDraft') }),
        loadingLabel: i18n.t('suggestion.generating', { name: i18n.t('suggestion.flowDraft') }),
        icon: 'generate',
      };
    case 'GENERATE_SCOPE':
      return {
        label: i18n.t('suggestion.generate', { name: i18n.t('suggestion.scopeDraft') }),
        loadingLabel: i18n.t('suggestion.generating', { name: i18n.t('suggestion.scopeDraft') }),
        icon: 'generate',
      };
    case 'ENTER_HOW':
      return {
        label: i18n.t('suggestion.enterHow'),
        loadingLabel: i18n.t('suggestion.enteringHow'),
        icon: 'navigate',
      };
    case 'ENTER_SCOPE':
      return {
        label: i18n.t('suggestion.enterScope'),
        loadingLabel: i18n.t('suggestion.enteringScope'),
        icon: 'navigate',
      };
    case 'ENTER_PREVIEW':
      return {
        label: i18n.t('suggestion.enterPreview'),
        loadingLabel: i18n.t('suggestion.enteringPreview'),
        icon: 'navigate',
      };
    case 'PREVIEW_READY':
      return {
        label: i18n.t('suggestion.viewPreview'),
        loadingLabel: i18n.t('suggestion.viewingPreview'),
        icon: 'navigate',
      };
    case 'STAGE_LOCKED':
      return {
        label: i18n.t('suggestion.enterPrevStage'),
        loadingLabel: i18n.t('suggestion.enteringPrevStage'),
        icon: 'navigate',
      };
    case 'BIND_ACTORS_TO_FEATURE':
      return {
        label: i18n.t('suggestion.openRelationPanel'),
        loadingLabel: i18n.t('suggestion.openingRelationPanel'),
        icon: 'open',
      };
    case 'COMPLETE_FLOW_STEPS':
      return {
        label: i18n.t('suggestion.completeFlowSteps'),
        loadingLabel: i18n.t('suggestion.completingFlowSteps'),
        icon: 'open',
      };
  }

  if (code.endsWith('_PERCEPTION_RUNNING')) {
    return {
      label: i18n.t('suggestion.checkAnalysisStatus'),
      loadingLabel: i18n.t('suggestion.checkingAnalysisStatus'),
      icon: 'wait',
    };
  }

  if (code.endsWith('_PERCEPTION_FAILED')) {
    return {
      label: i18n.t('suggestion.retryDiagnosis'),
      loadingLabel: i18n.t('suggestion.retryingDiagnosis'),
      icon: 'retry',
    };
  }

  if (code.endsWith('_SLOT')) {
    return {
      label: i18n.t('suggestion.viewSuggestion'),
      loadingLabel: i18n.t('suggestion.viewingSuggestion'),
      icon: 'open',
    };
  }

  // --- 4. Final Fallback ---
  return {
    label: i18n.t('suggestion.executeSuggestion'),
    loadingLabel: i18n.t('suggestion.executing'),
    icon: 'open',
  };
}
