import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CheckSquare,
  ChevronDown,
  ExternalLink,
  Eye,
  FileDown,
  LayoutDashboard,
  MonitorPlay,
  RefreshCw,
  Sparkles,
  User,
  Folder,
  Workflow,
  BookOpen,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { FlowStepCard } from '@/components/shared/FlowStepCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import {
  buildProjectRoute,
  buildRolePages,
  buildStepDetail,
  buildSystemProjection,
  projectionPath,
} from '@/core/selectors';
import { selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { withAuditActionTypeLabel } from '@/core/auditActionLabels';

type PrototypePreview = {
  prototypeId: number;
  projectId: string;
  html: string;
  javascript: string;
  css: string;
  pages?: PrototypePage[];
  source: string;
  status: string;
  errorMessage?: string | null;
  createdAt?: string;
  updatedAt?: string;
  shadowDraftId?: string;
};

type PrototypePage = {
  pageId: string;
  roleId: number;
  roleName: string;
  featureId: number;
  featureName: string;
  html: string;
  javascript: string;
  css: string;
  source: string;
  status: string;
};

type PrototypeState = 'idle' | 'loading' | 'ready' | 'error';

export function Preview() {
  const { t, i18n } = useTranslation();
  const {
    setSelectedObject,
    setHighlightTarget,
    highlightTarget,
  } = useWorkspaceStore();
  const navigate = useNavigate();

  const ir = useWorkspaceStore((state) => state.ir);
  const auditLogs = useWorkspaceStore((state) => state.auditLogs);
  const selectedObject = useWorkspaceStore(selectSelectedObject);

  const activeShadowDraft = useWorkspaceStore((state) => state.activeShadowDraft);
  const getActiveShadowDraft = useWorkspaceStore((state) => state.getActiveShadowDraft);
  const prepareShadowDraft = useWorkspaceStore((state) => state.prepareShadowDraft);
  const getShadowDraft = useWorkspaceStore((state) => state.getShadowDraft);
  const discardShadowDraft = useWorkspaceStore((state) => state.discardShadowDraft);
  const commitShadowDraft = useWorkspaceStore((state) => state.commitShadowDraft);
  const regenerateShadowDraft = useWorkspaceStore((state) => state.regenerateShadowDraft);
  const triggerGateCheck = useWorkspaceStore((state) => state.triggerGateCheck);

  const [activeRoleIndex, setActiveRoleIndex] = useState(0);
  const [exportState, setExportState] = useState<'idle' | 'exporting' | 'success'>('idle');
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false);
  const [prototype, setPrototype] = useState<PrototypePreview | null>(null);
  const [prototypeState, setPrototypeState] = useState<PrototypeState>('idle');
  const [prototypeError, setPrototypeError] = useState<string | null>(null);
  const [activePrototypePageId, setActivePrototypePageId] = useState<string>('');
  const [selectedFlowId, setSelectedFlowId] = useState<number | null>(null);

  const [feedbackText, setFeedbackText] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isDraftInitializing, setIsDraftInitializing] = useState(true);
  const [hasRequestedShadowPreview, setHasRequestedShadowPreview] = useState(false);
  const [isPostCommitCompiling, setIsPostCommitCompiling] = useState(false);
  
  // Custom states for smart loading modal overlay and animated progress bar
  const [smoothProgress, setSmoothProgress] = useState(0);
  const [progressSubtitle, setProgressSubtitle] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Keep a ref of activeShadowDraft to avoid stale closures in progress setInterval
  const activeShadowDraftRef = useRef(activeShadowDraft);
  useEffect(() => {
    activeShadowDraftRef.current = activeShadowDraft;
  }, [activeShadowDraft]);

  // On page entry, only load existing preview state. Do not auto-trigger shadow convergence.
  useEffect(() => {
    let cancelled = false;
    const projectId = ir?.projectId;
    if (!projectId) {
      setIsDraftInitializing(false);
      return;
    }

    const isRealWhatComplete = (ir?.actors || []).length > 0 && (ir?.features || []).length > 0;
    const isRealHowComplete = (ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0;
    const isRealScopeComplete = (ir?.features || []).some((feature) => feature.scope !== null);
    const isRealPreviewReady = isRealWhatComplete && isRealHowComplete && isRealScopeComplete;

    if (isRealPreviewReady) {
      useWorkspaceStore.setState({ activeShadowDraft: null });
      setIsDraftInitializing(true);
      workspaceApi.getLatestPrototypePreview(projectId)
        .then((res) => {
          if (!cancelled) {
            if (res && !('detail' in res)) {
              setPrototype(res);
              if (res.status === 'generating') {
                setPrototypeState('loading');
                setPrototypeError(null);
              } else if (res.status === 'failed') {
                setPrototypeState('error');
                setPrototypeError(res.errorMessage || t('preview.full.prototypeFailure'));
              } else {
                setPrototypeState('ready');
                setPrototypeError(null);
              }
            } else {
              setPrototype(null);
              setPrototypeState('idle');
            }
            setIsDraftInitializing(false);
          }
        })
        .catch((err) => {
          console.error('Failed to load latest prototype preview:', err);
          if (!cancelled) {
            setPrototype(null);
            setPrototypeState('idle');
            setIsDraftInitializing(false);
          }
        });
    } else {
      // Unconverged: only hydrate existing active shadow draft, do not auto spawn a new one
      setIsDraftInitializing(true);
      getActiveShadowDraft()
        .then((draft) => {
          if (!cancelled) {
            if (draft?.status === 'failed') {
              setHasRequestedShadowPreview(false);
            }
            setIsDraftInitializing(false);
          }
        })
        .catch((err) => {
          console.error('Failed to check active shadow draft:', err);
          if (!cancelled) {
            setIsDraftInitializing(false);
          }
        });
    }

    return () => {
      cancelled = true;
    };
  }, [ir?.projectId, ir?.actors?.length, ir?.features?.length, ir?.flows?.length, ir?.businessObjects?.length]);

  // Resume a persisted prototype job after the POST returns or the page refreshes.
  useEffect(() => {
    if (prototype?.status !== 'generating' || !ir?.projectId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = () => {
      workspaceApi.getLatestPrototypePreview(ir.projectId)
        .then((res) => {
          if (cancelled || !res || 'detail' in res) return;
          setPrototype(res);
          if (res.status === 'ready') {
            setPrototypeState('ready');
            setPrototypeError(null);
            return;
          }
          if (res.status === 'failed') {
            setPrototypeState('error');
            setPrototypeError(res.errorMessage || t('preview.full.prototypeFailure'));
            return;
          }
          timer = setTimeout(poll, 2000);
        })
        .catch(() => {
          if (!cancelled) timer = setTimeout(poll, 2000);
        });
    };

    timer = setTimeout(poll, 1000);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [prototype?.prototypeId, prototype?.status, ir?.projectId]);

  // Unified Polling Driver for activeShadowDraft when status is generating
  useEffect(() => {
    if (activeShadowDraft?.source !== 'shadow_project' || activeShadowDraft?.status !== 'generating' || !activeShadowDraft?.draftId) {
      return;
    }

    let cancelled = false;
    const draftId = activeShadowDraft.draftId;

    const timer = setInterval(() => {
      if (cancelled) return;
      getShadowDraft(draftId)
        .then((updated) => {
          if (cancelled) return;
          if (updated.status === 'ready' || updated.status === 'failed') {
            clearInterval(timer);
          }
        })
        .catch(() => {
          clearInterval(timer);
        });
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeShadowDraft?.status, activeShadowDraft?.draftId]);

  // Smooth animated progress bar simulation
  useEffect(() => {
    const isGenerating = activeShadowDraftRef.current?.status === 'generating';
    const isLoading = prototypeState === 'loading';
    if (!isGenerating && !isLoading) {
      if (activeShadowDraftRef.current?.status === 'failed' && hasRequestedShadowPreview) {
        setProgressSubtitle(t('preview.full.progressFailed'));
        setIsModalOpen(true); // Keep modal open to show traceback!
        return;
      }
      if (smoothProgress > 0 && smoothProgress < 100) {
        setSmoothProgress(100);
        setProgressSubtitle(t('preview.full.progressSucceeded'));
        const closeTimer = setTimeout(() => {
          setIsModalOpen(false);
          setSmoothProgress(0);
        }, 800);
        return () => clearTimeout(closeTimer);
      }
      setIsModalOpen(false);
      return;
    }

    if (!hasRequestedShadowPreview) {
      setIsModalOpen(false);
      return;
    }

    setIsModalOpen(true);
    
    // Determine unready gates to initialize start percentage
    const unreadyGates = activeShadowDraftRef.current?.unreadyGates || activeShadowDraftRef.current?.unready_gates || [];
    let startProgress = 0;
    if (unreadyGates.length > 0) {
      if (!unreadyGates.includes('what')) {
        startProgress = 35;
      }
      if (!unreadyGates.includes('what') && !unreadyGates.includes('how')) {
        startProgress = 70;
      }
    } else {
      startProgress = 90;
    }

    // Only set startProgress if we are starting fresh (smoothProgress is 0 or low)
    setSmoothProgress((prev) => (prev > 0 ? prev : startProgress));

    const interval = setInterval(() => {
      // Access the latest state from ref
      const currentDraft = activeShadowDraftRef.current;
      const currentUnreadyGates = currentDraft?.unreadyGates || currentDraft?.unready_gates || [];
      
      // Calculate target progress based on backend progress or fallback unready gates
      let fallbackTarget = 98;
      if (currentUnreadyGates.length > 0) {
        if (currentUnreadyGates.includes('what')) {
          fallbackTarget = 35;
        } else if (currentUnreadyGates.includes('how')) {
          fallbackTarget = 70;
        } else if (currentUnreadyGates.includes('scope')) {
          fallbackTarget = 90;
        }
      }

      const targetProgress = typeof currentDraft?.currentProgress === 'number'
        ? currentDraft.currentProgress
        : fallbackTarget;

      // Update progress and subtitle
      setSmoothProgress((prev) => {
        // If smoothProgress is behind the target, catch up smoothly
        if (prev < targetProgress) {
          const diff = targetProgress - prev;
          const step = Math.min(2.0, Math.max(0.1, diff * 0.15));
          const nextVal = prev + step;

          // Update subtitle according to step labels
          const currentLabel = currentDraft?.currentStepLabel;
          if (currentLabel) {
            setProgressSubtitle(t(currentLabel, { defaultValue: currentLabel }));
          } else {
            if (currentUnreadyGates.length === 0) {
              setProgressSubtitle(t('preview.full.progressGenerating'));
            } else if (nextVal < 35) {
              setProgressSubtitle(t('preview.full.progressWhat'));
            } else if (nextVal < 70) {
              setProgressSubtitle(t('preview.full.progressHow'));
            } else if (nextVal < 90) {
              setProgressSubtitle(t('preview.full.progressScope'));
            } else if (nextVal < 98) {
              setProgressSubtitle(t('preview.full.progressAssembly'));
            }
          }

          return Math.min(targetProgress, nextVal);
        } else {
          // If we have reached or exceeded targetProgress, slowly creep forward to show activity
          // but do not cross logical step ceilings to avoid outrunning future milestones
          let ceiling = 98;
          if (targetProgress < 15) ceiling = 14;
          else if (targetProgress < 25) ceiling = 24;
          else if (targetProgress < 35) ceiling = 34;
          else if (targetProgress < 50) ceiling = 49;
          else if (targetProgress < 75) ceiling = 74;
          else if (targetProgress < 85) ceiling = 84;
          else if (targetProgress < 90) ceiling = 89;
          else ceiling = 98;

          const currentLabel = currentDraft?.currentStepLabel;
          if (currentLabel) {
            setProgressSubtitle(t(currentLabel, { defaultValue: currentLabel }));
          } else {
            if (currentUnreadyGates.length === 0) {
              setProgressSubtitle(t('preview.full.progressGenerating'));
            } else if (prev < 35) {
              setProgressSubtitle(t('preview.full.progressWhat'));
            } else if (prev < 70) {
              setProgressSubtitle(t('preview.full.progressHow'));
            } else if (prev < 90) {
              setProgressSubtitle(t('preview.full.progressScope'));
            } else if (prev < 98) {
              setProgressSubtitle(t('preview.full.progressAssembly'));
            }
          }

          if (prev < ceiling) {
            return Math.min(ceiling, prev + 0.05);
          }
          return prev;
        }
      });
    }, 100);

    return () => clearInterval(interval);
  }, [activeShadowDraft?.status, activeShadowDraft?.unreadyGates, activeShadowDraft?.unready_gates, prototypeState, hasRequestedShadowPreview, t]);

  // Set prototype state and values based on activeShadowDraft
  useEffect(() => {
    if (isPostCommitCompiling) return;

    if (!activeShadowDraft) {
      setPrototype(null);
      setPrototypeState('idle');
      return;
    }

    if (activeShadowDraft.source === 'real_project') {
      setPrototype(activeShadowDraft.prototypePreview);
      if (activeShadowDraft.status === 'generating') {
        setPrototypeState('loading');
        setPrototypeError(null);
      } else if (activeShadowDraft.status === 'failed') {
        setPrototypeState('error');
        setPrototypeError(activeShadowDraft.prototypePreview?.errorMessage || t('preview.full.prototypeFailure'));
      } else {
        setPrototypeState('ready');
        setPrototypeError(null);
      }
    } else {
      const status = activeShadowDraft.status;
      if (status === 'generating') {
        setPrototype(null);
        setPrototypeState('loading');
        setPrototypeError(null);
      } else if (status === 'ready') {
        setPrototype(activeShadowDraft.prototypePreview);
        setPrototypeState('ready');
        setPrototypeError(null);
      } else if (status === 'failed') {
        setPrototype(null);
        setPrototypeState('error');
        setPrototypeError(t('preview.full.shadowFailure'));
      } else {
        setPrototype(null);
        setPrototypeState('idle');
      }
    }
  }, [activeShadowDraft, isPostCommitCompiling]);

  // Polling driver for real prototype after committing shadow draft
  useEffect(() => {
    if (!isPostCommitCompiling || !ir?.projectId) return;

    let cancelled = false;
    let pollCount = 0;
    const maxPolls = 20; // Polling up to 60 seconds (20 * 3s)

    const poll = () => {
      if (cancelled) return;
      workspaceApi.getLatestPrototypePreview(ir.projectId)
        .then((res) => {
          if (cancelled) return;
          if (res && !('detail' in res) && res.status === 'ready') {
            setPrototype(res);
            setPrototypeState('ready');
            setPrototypeError(null);
            setIsPostCommitCompiling(false);
          } else if (res && !('detail' in res) && res.status === 'failed') {
            setPrototype(res);
            setPrototypeState('error');
            setPrototypeError(res.errorMessage || t('preview.full.prototypeFailure'));
            setIsPostCommitCompiling(false);
          } else {
            pollCount++;
            if (pollCount >= maxPolls) {
              setIsPostCommitCompiling(false);
              setPrototypeState('idle');
            } else {
              setTimeout(poll, 3000);
            }
          }
        })
        .catch(() => {
          if (cancelled) return;
          pollCount++;
          if (pollCount >= maxPolls) {
            setIsPostCommitCompiling(false);
            setPrototypeState('idle');
          } else {
            setTimeout(poll, 3000);
          }
        });
    };

    setPrototypeState('loading');
    poll();

    return () => {
      cancelled = true;
    };
  }, [isPostCommitCompiling, ir?.projectId]);

  // Dynamic substitution of ir with virtual requirement space during shadow ready status
  const spaceToUse = useMemo(() => {
    if (activeShadowDraft?.source === 'shadow_project' && activeShadowDraft.status === 'ready' && activeShadowDraft.shadowSnapshotJson) {
      const snap = activeShadowDraft.shadowSnapshotJson;
      return {
        projectId: ir?.projectId,
        projectName: snap.project_name || snap.projectName || snap.name || ir?.projectName,
        projectDescription: snap.project_description || snap.projectDescription || snap.description || ir?.projectDescription,
        userRequirements: snap.user_requirements || snap.userRequirements || ir?.userRequirements,
        actors: snap.actors?.map((a: any) => ({
          actorId: a.actorId || a.id || a.actor_id,
          actorName: a.actorName || a.name || a.actor_name,
          actorDescription: a.actorDescription || a.description || a.actor_description
        })) || [],
        actorsCompatible: snap.actors?.map((a: any) => ({
          id: (a.actorId || a.id || a.actor_id)?.toString(),
          title: a.actorName || a.name || a.actor_name,
          desc: a.actorDescription || a.description || a.actor_description
        })) || [],
        features: snap.features?.map((f: any) => ({
          featureId: f.featureId || f.id || f.feature_id,
          featureName: f.featureName || f.name || f.feature_name,
          featureDescription: f.featureDescription || f.description || f.feature_description,
          actorIds: f.actorIds || f.actor_ids || [],
          parentId: f.parentId || f.parent_id,
          childrenIds: f.childrenIds || f.children_ids || [],
          scenarios: f.scenarios?.map((s: any) => ({
            scenarioId: s.scenarioId || s.id || s.scenario_id,
            scenarioName: s.scenarioName || s.name || s.scenario_name,
            scenarioContent: s.scenarioContent || s.content || s.scenario_content,
            featureId: s.featureId || s.feature_id,
            actorId: s.actorId || s.actor_id,
            acceptanceCriteria: (s.acceptance_criteria || s.acceptanceCriteria)?.map((ac: any) => ({
              criterionId: ac.criterionId || ac.id || ac.criterion_id,
              criterionContent: ac.criterionContent || ac.content || ac.criterion_content,
              position: ac.position
            })) || []
          })) || [],
          scope: f.scope ? {
            scopeId: f.scope.scopeId || f.scope.id || f.scope.scope_id,
            scopeStatus: f.scope.scopeStatus || f.scope.scope_status || f.scope.status,
            reason: f.scope.reason,
            kanoCategory: f.scope.kanoCategory || f.scope.kano_category,
            kanoCategoryName: f.scope.kanoCategoryName || f.scope.kano_category_name
          } : null
        })) || [],
        businessObjects: snap.business_objects?.map((bo: any) => ({
          businessObjectId: bo.businessObjectId || bo.id || bo.business_object_id,
          businessObjectName: bo.businessObjectName || bo.name || bo.business_object_name,
          businessObjectDescription: bo.businessObjectDescription || bo.description || bo.business_object_description,
          businessObjectAttributes: (bo.business_object_attributes || bo.businessObjectAttributes)?.map((attr: any) => ({
            businessObjectAttributeId: attr.businessObjectAttributeId || attr.id || attr.business_object_attribute_id,
            businessObjectAttributeName: attr.businessObjectAttributeName || attr.name || attr.business_object_attribute_name,
            businessObjectAttributeDescription: attr.businessObjectAttributeDescription || attr.description || attr.business_object_attribute_description,
            businessObjectAttributeType: attr.businessObjectAttributeType || attr.data_type || attr.business_object_attribute_type,
            businessObjectAttributeExample: attr.businessObjectAttributeExample || attr.example || attr.business_object_attribute_example
          })) || []
        })) || [],
        flows: snap.flows?.map((fl: any) => ({
          flowId: fl.flowId || fl.id || fl.flow_id,
          flowName: fl.flowName || fl.name || fl.flow_name,
          flowDescription: fl.flowDescription || fl.description || fl.flow_description,
          featureIds: fl.featureIds || fl.feature_ids || [],
          flowSteps: (fl.flow_steps || fl.flowSteps)?.map((step: any) => ({
            stepId: step.stepId || step.id || step.step_id,
            stepName: step.stepName || step.name || step.step_name,
            stepDescription: step.stepDescription || step.description || step.step_description,
            stepType: step.stepType || step.step_type || step.stepType,
            position: step.position,
            actorIds: step.actorIds || step.actor_ids || [],
            inputBusinessObjectIds: step.inputBusinessObjectIds || step.input_business_object_ids || [],
            outputBusinessObjectIds: step.outputBusinessObjectIds || step.output_business_object_ids || [],
            nextStepIds: step.nextStepIds || step.next_step_ids || []
          })) || []
        })) || [],
        findings: [],
        perceptionSlot: null
      };
    }
    return ir;
  }, [ir, activeShadowDraft]);

  const isWhatComplete = (spaceToUse?.actors || []).length > 0 && (spaceToUse?.features || []).length > 0;
  const isHowComplete = (spaceToUse?.flows || []).length > 0 && (spaceToUse?.businessObjects || []).length > 0;
  const isScopeComplete = (spaceToUse?.features || []).some((feature: any) => feature.scope !== null);
  const isPreviewReady = isWhatComplete && isHowComplete && isScopeComplete;

  const actors = useMemo(() => spaceToUse?.actorsCompatible || [], [spaceToUse]);
  const issues = useMemo(() => spaceToUse?.findings || [], [spaceToUse]);
  const activeRole = actors[activeRoleIndex];
  
  const pages = useMemo(() => {
    if (!spaceToUse || !activeRole) return [];
    return buildRolePages(spaceToUse as any, activeRole.id);
  }, [activeRole, spaceToUse]);

  const unresolvedIssues = issues.filter((finding: any) => (finding.status || 'open') === 'open');
  const system = useMemo(() => buildSystemProjection(spaceToUse as any), [spaceToUse]);
  
  const rolePrototypePages = useMemo(() => {
    if (!prototype?.pages?.length || !activeRole) return [];
    return prototype.pages.filter((page) => String(page.roleId) === String(activeRole.id));
  }, [activeRole, prototype]);

  const activePrototypePage = useMemo(() => {
    if (!prototype) return null;
    return (
      rolePrototypePages.find((page) => page.pageId === activePrototypePageId) ||
      rolePrototypePages[0] ||
      prototype.pages?.[0] ||
      null
    );
  }, [activePrototypePageId, prototype, rolePrototypePages]);

  const prototypeSrcDoc = useMemo(
    () => (prototype ? composePrototypeSrcDoc(activePrototypePage || prototype) : ''),
    [activePrototypePage, prototype],
  );

  const flows = useMemo(() => spaceToUse?.flows || [], [spaceToUse]);

  const activeFlow = useMemo(() => {
    return flows.find((f: any) => f.flowId === selectedFlowId) || flows[0] || null;
  }, [flows, selectedFlowId]);

  const activeFlowSteps = useMemo(() => {
    if (!activeFlow) return [];
    return activeFlow.flowSteps || [];
  }, [activeFlow]);

  // Initialize selected flow ID
  useEffect(() => {
    if (flows.length > 0 && selectedFlowId === null) {
      setSelectedFlowId(flows[0].flowId);
    }
  }, [flows, selectedFlowId]);

  useEffect(() => {
    if (rolePrototypePages.length === 0) {
      setActivePrototypePageId('');
      return;
    }
    if (!rolePrototypePages.some((page) => page.pageId === activePrototypePageId)) {
      setActivePrototypePageId(rolePrototypePages[0].pageId);
    }
  }, [activePrototypePageId, rolePrototypePages]);

  const cleanFilename = (name: string): string => {
    const cleaned = name.replace(/[\\/*?:"<>|]/g, '').trim();
    return cleaned || 'requirement-space';
  };

  const handleExport = (format: 'json' | 'markdown' | 'spl_syntax' | 'spl_semantic') => {
    triggerGateCheck('export', async () => {
      if (!spaceToUse?.projectId) return;
      const baseName = cleanFilename(spaceToUse.projectName || spaceToUse.projectId);
      setExportState('exporting');
      try {
        if (format === 'markdown') {
          const md = await workspaceApi.exportMarkdown(spaceToUse.projectId);
          downloadFile(`${baseName}.md`, md, 'text/markdown;charset=utf-8');
        } else if (format === 'json') {
          const data = await workspaceApi.exportJson(spaceToUse.projectId);
          const dataName = cleanFilename(data.projectName || data.projectId || spaceToUse.projectName || spaceToUse.projectId);
          downloadFile(`${dataName}.json`, JSON.stringify(data, null, 2), 'application/json;charset=utf-8');
        } else if (format === 'spl_syntax') {
          const spl = await workspaceApi.exportSplSyntax(spaceToUse.projectId);
          downloadFile(`${baseName}-spl-syntax.spl`, spl, 'text/plain;charset=utf-8');
        } else if (format === 'spl_semantic') {
          showToast(t('preview.full.splSemanticGenerating'));
          const spl = await workspaceApi.exportSplSemantic(spaceToUse.projectId);
          downloadFile(`${baseName}-spl-semantic.spl`, spl, 'text/plain;charset=utf-8');
        }
        setExportState('success');
        setTimeout(() => setExportState('idle'), 1500);
      } catch (err: any) {
        setExportState('idle');
        const errMsg = err?.message || '';
        if (errMsg.includes('spl_export_skill_unavailable')) {
          showToast(t('preview.full.splUnavailable'));
        } else if (errMsg.includes('spl_export_semantic_disabled')) {
          showToast(t('preview.full.splSemanticDisabled'));
        } else if (errMsg.includes('spl_export_timeout')) {
          showToast(t('preview.full.splSemanticTimeout'));
        } else if (errMsg.includes('spl_export_invalid_skill_output')) {
          if (format === 'spl_semantic') {
            showToast(t('preview.full.splSemanticFailed'));
          } else {
            showToast(t('preview.full.splSyntaxFailed'));
          }
        } else {
          showToast(t('preview.full.exportFailed', { error: errMsg || t('common.unknownError') }));
        }
      }
    });
  };

  const exportAuditLog = async () => {
    if (!spaceToUse) return;
    setExportState('exporting');
    try {
      downloadFile(
        `${spaceToUse.projectName || spaceToUse.projectId || 'requirement-space'}-audit.json`,
        JSON.stringify((auditLogs || []).map(log => withAuditActionTypeLabel(log, i18n.language)), null, 2),
        'application/json;charset=utf-8',
      );
      setExportState('success');
      setTimeout(() => setExportState('idle'), 1500);
    } catch {
      setExportState('idle');
    }
  };

  const generatePrototype = async () => {
    triggerGateCheck('generate_preview', async () => {
      if (!spaceToUse?.projectId) return;
      setHasRequestedShadowPreview(true);
      setSmoothProgress(90);
      setProgressSubtitle(t('preview.full.progressGenerating'));
      setIsModalOpen(true);
      setPrototypeState('loading');
      setPrototypeError(null);
      try {
        const result = await workspaceApi.generatePrototypePreview(spaceToUse.projectId, true);
        setPrototype(result);
        if (result.status === 'failed') {
          setPrototypeState('error');
          setPrototypeError(result.errorMessage || t('preview.full.prototypeFailure'));
        } else if (result.status === 'generating') {
          setPrototypeState('loading');
        } else {
          setPrototypeState('ready');
        }
      } catch (error) {
        setPrototypeState('error');
      setPrototypeError(error instanceof Error ? error.message : t('preview.full.prototypeFailure'));
      }
    });
  };

  const openPrototypeInWindow = () => {
    if (!prototypeSrcDoc) return;
    const blob = new Blob([prototypeSrcDoc], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener,noreferrer');
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
  };

  const handleRegenerate = async () => {
    if (!activeShadowDraft?.draftId) return;
    try {
      setHasRequestedShadowPreview(true);
      await regenerateShadowDraft(activeShadowDraft.draftId, feedbackText);
      setFeedbackText('');
      showToast(t('preview.full.shadowRegenerating'));
    } catch (err) {
      showToast(t('preview.full.regenerateFailed', { error: err instanceof Error ? err.message : String(err) }));
    }
  };

  const handleDiscard = async () => {
    if (!activeShadowDraft?.draftId) return;
    if (!window.confirm(t('preview.full.discardConfirm'))) return;
    try {
      await discardShadowDraft(activeShadowDraft.draftId);
      showToast(t('preview.full.shadowDiscarded'));
      navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/overview'));
    } catch (err) {
      showToast(t('preview.full.discardFailed', { error: err instanceof Error ? err.message : String(err) }));
    }
  };

  const handleCommit = async () => {
    if (!activeShadowDraft?.draftId) return;
    if (!window.confirm(t('preview.full.commitConfirm'))) return;
    try {
      setIsPostCommitCompiling(true); // Trigger compiling overlay in prototype pane
      await commitShadowDraft(activeShadowDraft.draftId);
      showToast(t('preview.full.shadowMerged'));
    } catch (err) {
      setIsPostCommitCompiling(false);
      if (err instanceof Error && err.message.includes('shadow_draft_conflict')) {
        showToast(t('preview.full.shadowConflict'));
      } else {
        showToast(t('preview.full.commitFailed', { error: err instanceof Error ? err.message : String(err) }));
      }
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const overlayUnreadyGates = activeShadowDraft?.unreadyGates || activeShadowDraft?.unready_gates || [];
  const isShadowOverlay = activeShadowDraft?.source === 'shadow_project' && overlayUnreadyGates.length > 0;

  const shouldShowReadinessGate =
    !isPreviewReady &&
    !hasRequestedShadowPreview &&
    (activeShadowDraft?.source !== 'shadow_project' || activeShadowDraft?.status === 'failed');

  if (isDraftInitializing) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[85vh] w-full">
        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-12 h-12 rounded-full border-4 border-slate-200 border-t-indigo-650 animate-spin" />
          <p className="text-xs font-bold text-slate-500">{t('preview.full.loadingShadow')}</p>
        </div>
      </div>
    );
  }

  if (shouldShowReadinessGate) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[85vh] w-full">
        <div className="max-w-2xl w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl space-y-8 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm mb-3">
              <Eye className="w-7 h-7 animate-pulse" />
            </div>
            <h3 className="text-xl font-black text-slate-900 tracking-tight">{t('preview.full.notReadyTitle')}</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              {t('preview.full.notReadyDescription')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ReadinessCard
              title="What"
              ready={isWhatComplete}
              description={t('preview.full.whatRequirement')}
              onClick={() => navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/what'))}
            />
            <ReadinessCard
              title="How"
              ready={isHowComplete}
              description={t('preview.full.howRequirement')}
              onClick={() => navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/flow'))}
            />
            <ReadinessCard
              title="Scope"
              ready={isScopeComplete}
              description={t('preview.full.scopeRequirement')}
              onClick={() => navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/scope'))}
            />
          </div>

          <div className="border-t border-slate-100 pt-6 flex flex-col items-center justify-center">
            <button
              onClick={() => {
                setHasRequestedShadowPreview(true);
                setIsDraftInitializing(true);
                prepareShadowDraft()
                  .then(() => {
                    setIsDraftInitializing(false);
                  })
                  .catch((err) => {
                    console.error('Failed to prepare shadow preview:', err);
                    setIsDraftInitializing(false);
                    showToast(t('preview.full.startFailure'));
                  });
              }}
              className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-2xl bg-slate-900 px-6 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-300 active:bg-slate-950"
            >
              <Sparkles className="h-4 w-4 shrink-0 text-white/85" />
              <span>{t('preview.full.generateShadow')}</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex w-full relative">
      {/* Toast Alert overlay */}
      {toastMessage && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-slate-900 text-white border border-slate-700 px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-2.5 text-xs font-bold animate-in fade-in slide-in-from-top-4 duration-300">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping inline-block" />
          <span>{toastMessage}</span>
        </div>
      )}

      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-[1240px] mx-auto space-y-8 animate-in fade-in flex flex-col">
          
          {/* Header Banner */}
          <section className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm flex flex-col lg:flex-row justify-between lg:items-center gap-6">
            <div className="space-y-1">
              <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-indigo-600 shrink-0" />
            {t('preview.full.deliveryTitle')}
              </h2>
              <p className="text-xs text-slate-400 leading-relaxed max-w-2xl font-medium">
            {t('preview.full.deliveryDescription')}
              </p>
            </div>
            <div className="relative flex items-center">
              <button
                type="button"
                onClick={() => setIsExportMenuOpen((prev) => !prev)}
                disabled={exportState === 'exporting'}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 shadow-sm transition-colors hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60"
              >
                <FileDown className="h-3.5 w-3.5 text-indigo-500" />
            {t('preview.exportSection')}
                <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform ${isExportMenuOpen ? 'rotate-180' : ''}`} />
              </button>
              {isExportMenuOpen && (
                <div className="absolute right-0 top-[calc(100%+10px)] z-20 min-w-[280px] overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                  <button
                    type="button"
                    onClick={() => {
                      setIsExportMenuOpen(false);
                      void handleExport('markdown');
                    }}
                    disabled={exportState === 'exporting'}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60"
                  >
                    <FileDown className="h-3.5 w-3.5 text-indigo-500" />
            {t('preview.exportMarkdown')}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsExportMenuOpen(false);
                      void handleExport('json');
                    }}
                    disabled={exportState === 'exporting'}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60"
                  >
                    <FileDown className="h-3.5 w-3.5 text-indigo-500" />
            {t('preview.exportJson')}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsExportMenuOpen(false);
                      void handleExport('spl_syntax');
                    }}
                    disabled={exportState === 'exporting'}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60"
                  >
                    <FileDown className="h-3.5 w-3.5 text-indigo-500" />
                    <div className="flex flex-col">
              <span>{t('preview.full.exportSplSyntax')}</span>
              <span className="text-[10px] font-normal text-slate-400">{t('preview.full.exportSplSyntaxTip')}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsExportMenuOpen(false);
                      void handleExport('spl_semantic');
                    }}
                    disabled={exportState === 'exporting'}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60"
                  >
                    <FileDown className="h-3.5 w-3.5 text-indigo-500" />
                    <div className="flex flex-col">
              <span>{t('preview.full.exportSplSemantic')}</span>
              <span className="text-[10px] font-normal text-slate-400">{t('preview.full.exportSplSemanticTip')}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsExportMenuOpen(false);
                      void exportAuditLog();
                    }}
                    disabled={exportState === 'exporting'}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60"
                  >
                    <CheckSquare className="h-3.5 w-3.5 text-sky-500" />
            {t('preview.full.exportAuditLogs')}
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* Shadow Sandbox Banner */}
          {activeShadowDraft?.source === 'shadow_project' && activeShadowDraft.status === 'ready' && (
            <div className="rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-slate-50 p-5 shadow-sm animate-in slide-in-from-top duration-300">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div className="space-y-3">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-white px-3 py-1 text-[10px] font-extrabold uppercase tracking-[0.18em] text-indigo-700 shadow-sm">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
            {t('preview.full.shadowTitle')}
                  </div>
                  <div className="space-y-1.5">
                    <h3 className="text-sm font-black tracking-tight text-slate-900">
            {t('preview.full.shadowSubtitle')}
                    </h3>
                    <p className="text-xs leading-relaxed text-slate-500">
            {t('preview.full.shadowDescription')}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-slate-600">
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm">
                      <User className="w-3 h-3 text-indigo-500 shrink-0" />
                      {t('preview.aiShadowActorsCount', { count: activeShadowDraft.shadowSummary?.actors || 0 })}
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm">
                      <Folder className="w-3 h-3 text-indigo-500 shrink-0" />
                      {t('preview.aiShadowFeaturesCount', { count: activeShadowDraft.shadowSummary?.features || 0 })}
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm">
                      <Workflow className="w-3 h-3 text-indigo-500 shrink-0" />
                      {t('preview.aiShadowFlowsCount', { count: activeShadowDraft.shadowSummary?.flows || 0 })}
                    </span>
                    <span className="inline-flex items-center rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-emerald-700 shadow-sm">
            {t('preview.full.kanoEvaluated')}
                    </span>
                  </div>
                </div>

                <div className="flex w-full flex-col gap-2.5 lg:w-auto lg:min-w-[380px]">
                  <div className="flex overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                    <input
                      type="text"
            placeholder={t('preview.full.feedbackPlaceholder')}
                      value={feedbackText}
                      onChange={(e) => setFeedbackText(e.target.value)}
                      className="flex-1 border-0 bg-transparent px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleRegenerate}
                      className="border-l border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-100"
                    >
            {t('preview.full.regenerate')}
                    </button>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2.5">
                    <button
                      type="button"
                      onClick={handleDiscard}
                      className="px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-slate-600 text-xs font-bold hover:bg-slate-50 transition-colors shadow-sm"
                    >
            {t('preview.full.discard')}
                    </button>
                    <button
                      type="button"
                      onClick={handleCommit}
                      className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-black hover:bg-indigo-700 transition-colors shadow-sm"
                    >
            {t('preview.full.commit')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Integrated Side-by-Side Interactive Prototype & Blueprints Panel */}
          <section className="bg-white rounded-3xl border border-slate-200 shadow-md overflow-hidden">
            <div className="border-b border-slate-200 px-6 py-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-slate-50/50">
              <div>
                <h3 className="text-base font-black text-slate-900 tracking-tight flex items-center gap-2">
                  <MonitorPlay className="w-5 h-5 text-teal-600" />
            {t('preview.full.quickPrototype')}
                </h3>
              </div>
              
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={openPrototypeInWindow}
                  disabled={!prototypeSrcDoc || prototypeState === 'loading'}
                  className="px-3.5 py-2 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 transition-colors bg-white flex items-center gap-1.5 disabled:opacity-50 shadow-sm"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
            {t('preview.full.openPrototype')}
                </button>
                <button
                  type="button"
                  onClick={() => void generatePrototype()}
                  disabled={prototypeState === 'loading'}
                  className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-colors flex items-center gap-1.5 disabled:opacity-60 shadow-md"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${prototypeState === 'loading' ? 'animate-spin' : ''}`} />
            {prototype ? t('preview.full.regeneratePrototype') : t('preview.full.generatePrototype')}
                </button>
              </div>
            </div>

            {/* Viewport Split Screen */}
            <div className="grid grid-cols-1 lg:grid-cols-12 border-t border-slate-100">
              
              {/* Left Column: Interactive Prototype Simulator */}
              <div className="lg:col-span-7 bg-slate-100/50 p-6 border-r border-slate-200 flex flex-col justify-center">
                <div className="bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden flex flex-col h-[740px]">
                  <div className="h-10 px-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
                    <div className="flex gap-1.5 items-center">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block" />
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
                      <span className="ml-3 text-xs text-slate-400 font-mono select-none truncate">
                        /projects/{spaceToUse?.projectId || 'current'}/roles/{activeRole?.title || 'role'}/{activePrototypePage?.featureName || 'prototype'}
                      </span>
                    </div>
                    <span className="text-[10px] bg-slate-200 border border-slate-300 text-slate-500 px-2 py-0.5 rounded font-mono font-bold select-none">
                      PROTOTYPE SIMULATION
                    </span>
                  </div>
                  {rolePrototypePages.length > 0 && (
                    <div className="shrink-0 border-b border-slate-200 bg-white px-3 py-2 flex flex-wrap gap-2">
                      {rolePrototypePages.map((page) => (
                        <button
                          key={page.pageId}
                          type="button"
                          onClick={() => setActivePrototypePageId(page.pageId)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
                            activePrototypePage?.pageId === page.pageId
                              ? 'bg-teal-50 text-teal-700 border-teal-200'
                              : 'bg-slate-50 text-slate-500 border-slate-200 hover:text-slate-700'
                          }`}
                        >
                          {page.featureName}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex-1 bg-white relative animate-in fade-in">
                    {prototypeState === 'loading' ? (
                      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-slate-50 space-y-4">
                        <div className="w-12 h-12 rounded-full border-4 border-slate-200 border-t-indigo-650 animate-spin" />
                        <h4 className="text-xs font-black text-slate-800 tracking-wide select-none">
                          <span className="flex items-center gap-1.5 justify-center">
                            <Sparkles className="w-4 h-4 text-indigo-500 animate-pulse shrink-0" />
              {isPostCommitCompiling ? t('preview.full.compilingCommitted') : t('preview.full.generatingPrototype')}
                          </span>
                        </h4>
                        <p className="text-xs text-slate-500 max-w-sm leading-relaxed font-medium">
                          {isPostCommitCompiling
                ? t('preview.full.compilingCommittedDescription')
                : t('preview.full.generatingPrototypeDescription')}
                        </p>
                      </div>
                    ) : prototypeState === 'error' ? (
              <PrototypePlaceholder label={prototypeError || t('preview.full.assemblyFailure')} tone="error" />
                    ) : prototype ? (
                       <iframe
                        key={prototype.shadowDraftId || prototype.prototypeId}
                        title={`${activeRole?.title || spaceToUse?.projectName || 'Project'} prototype`}
                        srcDoc={prototypeSrcDoc}
                        className="w-full h-full border-0 bg-white"
                      />
                    ) : (
              <PrototypePlaceholder label={t('preview.full.noPrototype')} />
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column: Dynamic Role Blueprint Specifications */}
              <div className="lg:col-span-5 p-6 overflow-y-auto max-h-[788px] space-y-6 flex flex-col">
                <div className="border-b border-slate-100 pb-3 flex items-center justify-between shrink-0">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1">
              <span className="flex items-center gap-1.5"><BookOpen className="w-4 h-4 text-slate-500 shrink-0" /> {t('preview.full.roleSpecs')}</span>
                  </h4>
                  <span className="text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-2 py-0.5 rounded">
              {t('preview.full.pageCount', { count: pages.length })}
                  </span>
                </div>

                {/* Role Tabs inside Specification container */}
                <div className="flex flex-wrap items-center gap-1.5 shrink-0 bg-slate-50 p-1.5 rounded-xl border border-slate-200">
                  {actors.map((actor: any, idx: number) => (
                    <button
                      key={actor.id}
                      type="button"
                      onClick={() => setActiveRoleIndex(idx)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        activeRoleIndex === idx 
                          ? 'bg-white text-indigo-600 shadow-sm border border-indigo-100/50' 
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      <span className="flex items-center gap-1"><User className="w-3.5 h-3.5 text-indigo-500 shrink-0" /> {actor.title}</span>
                    </button>
                  ))}
                </div>

                <div className="flex-1 space-y-6">
                  {pages.length === 0 ? (
                    <div className="text-center py-24 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50 space-y-3">
                      <div className="mx-auto w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400">
                        <Eye className="w-5 h-5" />
                      </div>
                  <div className="text-xs font-extrabold text-slate-700">{t('preview.full.noRolePreview')}</div>
                      <div className="text-xs text-slate-400 max-w-xs mx-auto leading-relaxed">
                    {t('preview.full.noRolePreviewDescription')}
                      </div>
                    </div>
                  ) : (
                    pages.map((page) => (
                      <div key={page.id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4 hover:border-slate-300 transition-colors">
                        <div className="border-b border-slate-100 pb-3">
                          <h5 className="font-extrabold text-slate-800 text-xs flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                            {page.name}
                          </h5>
                          <p className="text-xs text-slate-500 mt-1 leading-relaxed font-medium">{page.desc}</p>
                        </div>
                        
                        <div className="space-y-4">
                          <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">{t('preview.full.acceptanceScenarios')}</span>
                            {page.scenarios.length === 0 ? (
                    <span className="text-xs text-slate-400 italic block bg-slate-50 p-2.5 rounded-xl border border-slate-100">{t('preview.full.noAcceptanceScenarios')}</span>
                            ) : (
                              <div className="space-y-2.5">
                                {page.scenarios.map((scenario: any) => (
                                  <div
                                    key={scenario.scenarioId}
                                    onClick={() => setSelectedObject({ ...scenario, kind: 'scenario' })}
                                    className="w-full text-left bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2 hover:border-indigo-300 transition-all cursor-pointer"
                                  >
                                    <h6 className="font-bold text-slate-800 text-xs truncate">{scenario.scenarioName}</h6>
                                    <p className="text-[10px] text-slate-500 leading-relaxed bg-white border border-slate-100 p-2 rounded-lg italic">
                                      "{scenario.scenarioContent}"
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>

                          <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">{t('preview.full.executionSteps')}</span>
                            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2">
                              {page.relatedSteps.length === 0 ? (
                    <span className="text-xs text-slate-400 italic">{t('preview.full.noExecutionSteps')}</span>
                              ) : (
                                page.relatedSteps.map((stepName: string, idx: number) => (
                                  <div key={`${stepName}-${idx}`} className="bg-white rounded-lg p-2.5 border border-slate-200/50 shadow-sm flex items-center justify-between">
                                    <span className="text-[10px] font-bold text-slate-700 truncate">{stepName}</span>
                                    <span className="text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-extrabold shrink-0">
                  {t('preview.full.actorInitiated')}
                                    </span>
                                  </div>
                                ))
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Active Issues Alert */}
          {unresolvedIssues.length > 0 && (
            <section className="bg-amber-50 rounded-2xl border border-amber-200 p-5 shadow-sm">
              <h3 className="font-bold text-amber-900 mb-1.5 flex items-center gap-1.5 text-xs">
                <span>{t('preview.full.unresolvedIssues', { count: unresolvedIssues.length })}</span>
              </h3>
              <p className="text-xs text-amber-800 leading-relaxed font-medium">
                {t('preview.full.unresolvedIssuesDescription')}
              </p>
            </section>
          )}

          {/* End-to-End Business Flow Chronological Timelines */}
          {flows.length > 0 && (
            <section className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm relative w-full">
              <div className="mb-6 border-b border-slate-100 pb-4">
                <h3 className="text-base font-extrabold text-slate-900">{t('preview.stageGuidanceTitle')}</h3>
              </div>
              
              {/* Flow Switcher Tabs */}
              <div className="flex flex-wrap gap-2 mb-6 border-b border-slate-100 pb-4">
                {flows.map((flow: any) => (
                  <button
                    key={flow.flowId}
                    type="button"
                    onClick={() => setSelectedFlowId(flow.flowId)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-sm ${
                      selectedFlowId === flow.flowId 
                        ? 'bg-slate-900 text-white shadow-indigo-100' 
                        : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200/60'
                    }`}
                  >
          {flow.flowName}
                  </button>
                ))}
              </div>

              {/* Switchable flow chronological view */}
              <div className="w-full bg-slate-50 border border-slate-200 rounded-2xl flex flex-col min-h-[360px] p-6 shadow-inner">
                <div className="p-4 bg-white border border-slate-200 rounded-t-2xl flex items-center justify-between shrink-0 mb-6 shadow-sm">
                  <h4 className="text-xs font-extrabold text-slate-800 flex items-center gap-1.5 uppercase tracking-wider">
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse"></span>
                  {t('preview.full.reviewingFlow', { name: activeFlow?.flowName })}
                  </h4>
                </div>
                
                <div className="flex-1 w-full max-w-3xl mx-auto">
                  {activeFlowSteps.length === 0 ? (
                    <div className="text-center py-20 text-xs text-slate-400 italic">
                  {t('preview.stageGuidanceEmpty')}
                    </div>
                  ) : (
                    <div className="relative pl-8 border-l-2 border-indigo-200 space-y-8 py-2">
                      {activeFlowSteps.map((step: any, idx: number) => {
                        const stepDetail = buildStepDetail(spaceToUse as any, step.stepId);
                        const performerId = (step.actorIds || [])[0];
                        const performer = (spaceToUse?.actors || []).find((a: any) => a.actorId === performerId);
                        const actorName = performer ? performer.actorName : t('preview.flowRoleSystem');

                        const nextSteps = (step.nextStepIds || [])
                          .map((nid: string) => activeFlowSteps.find((s: any) => s.stepId === nid)?.stepName)
                          .filter(Boolean) as string[];

                        const stepSlots: any[] = [];
                        if (spaceToUse?.perceptionSlot && spaceToUse.perceptionSlot.perceptionJobId === step.stepId) {
                          stepSlots.push({
                            id: spaceToUse.perceptionSlot.id,
                            title: spaceToUse.perceptionSlot.perceptionKind,
                            choiceCount: 0,
                            status: 'empty'
                          });
                        }

                        const isActive = selectedObject?.id === step.stepId.toString() || (highlightTarget !== null && highlightTarget.toString() === step.stepId.toString());

                        return (
                          <div key={step.stepId} className="relative">
                            {/* Timeline dot */}
                            <div className={`absolute -left-[44px] top-4 w-7 h-7 rounded-full border-4 flex items-center justify-center text-[10px] font-black transition-all ${
                              isActive
                                ? 'bg-indigo-600 border-indigo-200 text-white shadow-md shadow-indigo-600/20'
                                : 'bg-white border-indigo-100 text-slate-400'
                            }`}>
                              {idx + 1}
                            </div>

                            <FlowStepCard
                              name={step.stepName}
                      type={step.stepType === 'actorAction' ? t('flowStepType.actorAction') : step.stepType === 'systemAction' ? t('flowStepType.systemAction') : t('flowStepType.judgment')}
                              actor={actorName}
                              status={step.status || 'confirmed'}
                              inputs={stepDetail.inputs}
                              outputs={stepDetail.outputs}
                              rules={stepDetail.rules}
                              stateChanges={stepDetail.stateChanges}
                              relatedPages={stepDetail.relatedPages}
                              relatedIssueCount={stepDetail.relatedIssueIds.length}
                              relatedChoiceCount={stepDetail.relatedChoiceIds.length}
                              nextSteps={nextSteps.length > 0 ? nextSteps : undefined}
                              exceptionSteps={undefined}
                              slots={stepSlots}
                              active={isActive}
                              onClick={() => {
                                setSelectedObject({
                                  ...step,
                                  id: step.stepId.toString(),
                                  title: step.stepName,
                                  description: step.stepDescription,
                                  status: step.status || 'confirmed',
                                  kind: 'flow_step'
                                });
                                setHighlightTarget(step.stepId.toString());
                              }}
                              onSlotClick={(slotId) => {
                                if (spaceToUse?.perceptionSlot && spaceToUse.perceptionSlot.id === slotId) {
                                  setSelectedObject(spaceToUse.perceptionSlot);
                                }
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}

        </div>
      </div>

      {/* Smart Loading Modal Overlay with Animated Progress Bar */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-300">
          <div className="w-[520px] max-w-full mx-4 bg-white/95 border border-slate-200/80 rounded-3xl p-8 shadow-2xl flex flex-col items-center select-none relative animate-in zoom-in-95 duration-300">
            
            {/* Header Glowing Sparkle */}
            <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-5 shadow-inner">
              {activeShadowDraft?.status === 'failed' ? (
                <XCircle className="w-8 h-8 text-rose-500 animate-bounce" />
              ) : smoothProgress === 100 ? (
                <CheckCircle2 className="w-8 h-8 text-emerald-500 scale-110 transition-transform duration-500" />
              ) : (
                <Sparkles className="w-8 h-8 text-indigo-600 animate-pulse" />
              )}
            </div>

            {/* Title */}
            <h3 className="text-sm font-black text-slate-800 tracking-wide text-center leading-none mb-2">
              {activeShadowDraft?.status === 'failed' ? (
                <span className="text-rose-600 font-extrabold flex items-center gap-1.5 justify-center"><AlertCircle className="w-5 h-5" /> {t('preview.full.overlayFailed')}</span>
              ) : smoothProgress === 100 ? (
          <span className="text-emerald-600 font-extrabold">{t('preview.full.overlaySucceeded')}</span>
              ) : isShadowOverlay ? (
                <span className="text-slate-800">{t('preview.full.overlayShadowGenerating')}</span>
              ) : (
                <span className="text-slate-800">{t('preview.full.generatingPrototype')}</span>
              )}
            </h3>

            {/* Subtitle */}
            <p className={`text-xs text-center max-w-sm px-4 leading-relaxed font-semibold transition-all duration-300 min-h-[36px] ${
              activeShadowDraft?.status === 'failed' ? 'text-rose-500' : 'text-slate-500'
            }`}>
              {progressSubtitle}
            </p>

            {/* Progress Bar Container */}
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden mb-8 mt-4 border border-slate-200/50">
              <div 
                className={`h-full transition-all duration-300 ease-out ${
                  activeShadowDraft?.status === 'failed' 
                    ? 'bg-rose-500' 
                    : smoothProgress === 100 
                      ? 'bg-emerald-500' 
                      : 'bg-indigo-600'
                }`}
                style={{ width: `${smoothProgress}%` }}
              />
            </div>

            {/* Sub-steps Checklist */}
            {isShadowOverlay ? (
            <div className="w-full space-y-3 bg-slate-50 border border-slate-200/60 p-5 rounded-2xl mb-6">
              {[
                { label: t('preview.full.stepWhat'), checkKey: 'what', threshold: 35 },
                { label: t('preview.full.stepHow'), checkKey: 'how', threshold: 70 },
                { label: t('preview.full.stepScope'), checkKey: 'scope', threshold: 90 },
                { label: t('preview.full.stepAssembly'), checkKey: 'all', threshold: 100 }
              ].map((step, idx) => {
                const isFailed = activeShadowDraft?.status === 'failed';
                const isStepFinished = 
                  step.checkKey === 'all' 
                    ? (smoothProgress === 100)
                    : (!(activeShadowDraft?.unreadyGates || activeShadowDraft?.unready_gates || []).includes(step.checkKey) || smoothProgress >= step.threshold);
                
                const isStepActive = 
                  !isFailed && !isStepFinished && (
                    idx === 0 
                      ? (smoothProgress < 35)
                      : idx === 1
                        ? (smoothProgress >= 35 && smoothProgress < 70)
                        : idx === 2
                          ? (smoothProgress >= 70 && smoothProgress < 90)
                          : (smoothProgress >= 90 && smoothProgress < 100)
                  );

                const isStepFailed = isFailed && isStepActive;

                return (
                  <div key={idx} className="flex items-center justify-between text-[11px] font-bold">
                    <span className={`transition-colors ${
                      isStepFinished ? 'text-slate-400 font-medium' : isStepActive ? 'text-indigo-600' : 'text-slate-500'
                    }`}>
                      {step.label}
                    </span>
                    <div className="flex items-center">
                      {isStepFailed ? (
                        <XCircle className="w-4 h-4 text-rose-500 animate-pulse" />
                      ) : isStepFinished ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 fill-emerald-50" />
                      ) : isStepActive ? (
                        <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border border-slate-300 bg-white" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            ) : (
            <div className="w-full bg-slate-50 border border-slate-200/60 p-5 rounded-2xl mb-6 text-center">
              <div className="text-xs font-bold text-slate-700">{t('preview.full.interactiveGenerating')}</div>
              <div className="mt-1 text-[11px] text-slate-500">{t('preview.full.interactiveGeneratingDescription')}</div>
            </div>
            )}

            {/* Error message collapsible container (collapsible terminal box) */}
            {activeShadowDraft?.status === 'failed' && (
              <div className="w-full flex flex-col mb-6 bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-md">
                <div className="bg-slate-950 px-4 py-2 border-b border-slate-800 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" /> {t('preview.full.tracebackTitle')}
                  </span>
                  <button 
                    onClick={() => {
                      navigator.clipboard.writeText(activeShadowDraft.errorMessage || '');
                      showToast(t('preview.copyLogsSuccess'));
                    }}
                    className="text-[9px] bg-slate-800 border border-slate-700 text-slate-300 font-bold px-2 py-0.5 rounded hover:bg-slate-700 hover:text-white transition-colors"
                  >
                    {t('preview.copyLogsBtn')}
                  </button>
                </div>
                <div className="p-4 max-h-[160px] overflow-y-auto font-mono text-[10px] text-rose-400/90 leading-relaxed scrollbar-thin select-text text-left">
                  {activeShadowDraft.errorMessage || t('preview.full.unknownPerceptionError')}
                </div>
              </div>
            )}

            {/* Action Button (Dismiss on fail) */}
            {activeShadowDraft?.status === 'failed' && (
              <button
                onClick={() => {
                  discardShadowDraft(activeShadowDraft.draftId)
                    .then(() => {
                      setIsModalOpen(false);
                      setSmoothProgress(0);
                    })
                    .catch(() => {
                      setIsModalOpen(false);
                      setSmoothProgress(0);
                    });
                }}
                className="w-full py-3 rounded-2xl bg-slate-800 hover:bg-slate-900 text-white text-xs font-black transition-all active:scale-[0.98] shadow-md flex items-center justify-center gap-1.5"
              >
                {t('preview.full.closeAndReset')}
              </button>
            )}

          </div>
        </div>
      )}

      <RightObjectPanel />
    </div>
  );
}

function PrototypePlaceholder({
  label,
  tone = 'neutral',
}: {
  label: string;
  tone?: 'neutral' | 'error';
}) {
  return (
    <div className={`h-full flex items-center justify-center text-xs font-bold leading-normal p-8 text-center ${tone === 'error' ? 'text-rose-600 bg-rose-50' : 'text-slate-400 bg-white'}`}>
      {label}
    </div>
  );
}

function ReadinessCard({
  title,
  ready,
  description,
  onClick,
}: {
  title: string;
  ready: boolean;
  description: string;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className={`rounded-2xl border p-5 flex flex-col gap-3.5 transition-colors shadow-sm ${ready ? 'border-emerald-200 bg-emerald-50/20' : 'border-amber-200 bg-amber-50/20'}`}>
      <div className="flex justify-between items-center leading-none">
        <span className="text-xs font-bold text-slate-800">{title === 'What' ? t('preview.stageWhatTitle') : title === 'How' ? t('preview.stageHowTitle') : t('preview.stageScopeTitle')}</span>
        <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded border uppercase tracking-wider ${ready ? 'bg-emerald-50 border-emerald-100 text-emerald-800' : 'bg-amber-50 border-amber-100 text-amber-800'}`}>
          {ready ? t('preview.stageReadyText') : t('preview.full.needsCompletion')}
        </span>
      </div>
      <p className="text-xs text-slate-500 leading-relaxed font-medium">{description}</p>
      {!ready && (
        <button onClick={onClick} className="mt-auto text-[10px] text-indigo-600 hover:text-indigo-800 font-bold text-left flex items-center gap-0.5 transition-colors">
          {t('preview.full.completeNow')} &rarr;
        </button>
      )}
    </div>
  );
}

function composePrototypeSrcDoc(prototype: PrototypePreview | PrototypePage) {
  const css = prototype.css ? `<style>${prototype.css}</style>` : '';
  const javascript = prototype.javascript
    ? `<script>${prototype.javascript.replace(/<\/script/gi, '<\\/script')}</script>`
    : '';
  let html = sanitizePrototypeHtml(prototype.html || '<!doctype html><html><head></head><body></body></html>');

  if (css) {
    html = html.includes('</head>')
      ? html.replace('</head>', `${css}</head>`)
      : `${css}${html}`;
  }

  if (javascript) {
    html = html.includes('</body>')
      ? html.replace('</body>', `${javascript}</body>`)
      : `${html}${javascript}`;
  }

  return html;
}

function sanitizePrototypeHtml(html: string) {
  return html
    .replace(/<script[^>]+src=["'](?:\.\/)?script\.js["'][^>]*>\s*<\/script>/gi, '')
    .replace(/<link[^>]+rel=["']stylesheet["'][^>]+href=["'](?:\.\/)?style\.css["'][^>]*>/gi, '');
}

function downloadFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
