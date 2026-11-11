import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import {
  CheckSquare,
  ChevronDown,
  ExternalLink,
  Eye,
  FileDown,
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
  PanelRightClose,
  PanelRightOpen,
  Maximize2,
  Smartphone,
  Tablet,
  Monitor,
  MoreHorizontal,
  X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import {
  buildProjectRouteWithBranch,
  buildRolePages,
} from '@/core/selectors';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { useLocalStorageState } from '@/lib/useLocalStorageState';
import { withAuditActionTypeLabel } from '@/core/auditActionLabels';
import { GlassSurface } from '@/components/ui/GlassSurface';

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
type DeviceViewport = 'desktop' | 'tablet' | 'mobile';

export function Preview() {
  const { t, i18n } = useTranslation();
  const {
    setSelectedObject,
  } = useWorkspaceStore();
  const navigate = useNavigate();

  const ir = useWorkspaceStore((state) => state.ir);
  const auditLogs = useWorkspaceStore((state) => state.auditLogs);

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
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const [prototype, setPrototype] = useState<PrototypePreview | null>(null);
  const [prototypeState, setPrototypeState] = useState<PrototypeState>('idle');
  const [prototypeError, setPrototypeError] = useState<string | null>(null);
  const [activePrototypePageId, setActivePrototypePageId] = useState<string>('');

  const [feedbackText, setFeedbackText] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isDraftInitializing, setIsDraftInitializing] = useState(true);
  const [hasRequestedShadowPreview, setHasRequestedShadowPreview] = useState(false);
  const [isPostCommitCompiling, setIsPostCommitCompiling] = useState(false);
  
  const [isRightPanelCollapsed, setIsRightPanelCollapsed] = useLocalStorageState('preview-right-panel-collapsed', false);
  const [isFullscreenPreview, setIsFullscreenPreview] = useState(false);
  const [isPreviewMenuOpen, setIsPreviewMenuOpen] = useState(false);
  const previewMenuRef = useRef<HTMLDivElement>(null);
  const [deviceViewport, setDeviceViewport] = useState<DeviceViewport>('desktop');

  // 菜单打开期间监听外部点击以关闭（fixed 捕获层会被玻璃容器的 backdrop-filter 困住，故改用文档监听）
  useEffect(() => {
    if (!isExportMenuOpen && !isPreviewMenuOpen) return;
    const handlePointerDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (isExportMenuOpen && exportMenuRef.current && !exportMenuRef.current.contains(target)) {
        setIsExportMenuOpen(false);
      }
      if (isPreviewMenuOpen && previewMenuRef.current && !previewMenuRef.current.contains(target)) {
        setIsPreviewMenuOpen(false);
      }
    };
    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, [isExportMenuOpen, isPreviewMenuOpen]);

  // Custom states for smart loading modal overlay and animated progress bar
  const [smoothProgress, setSmoothProgress] = useState(0);
  const [progressSubtitle, setProgressSubtitle] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  const activeShadowDraftRef = useRef(activeShadowDraft);
  activeShadowDraftRef.current = activeShadowDraft;

  const generationFailed = prototypeState === 'error' || activeShadowDraft?.status === 'failed';
  const generationError = prototypeError || activeShadowDraft?.errorMessage || t('preview.full.prototypeFailure');

  const stageProgress = useWorkspaceStore((s) => s.stageProgress);
  const branchRef = useWorkspaceStore((s) => s.branchRef);
  const branchRefCurrent = useRef(branchRef);
  branchRefCurrent.current = branchRef;

  const isWhatComplete = useMemo(() => {
    const whatStage = stageProgress?.stages?.find((s: any) => s.stage === 'what');
    if (stageProgress?.stages && whatStage) {
      return Boolean(whatStage.unlocked && (whatStage.statusCode === 'ready' || whatStage.statusCode === 'ready_to_advance' || whatStage.content_complete || ((ir?.actors || []).length > 0 && (ir?.features || []).length > 0)));
    }
    return (ir?.actors || []).length > 0 && (ir?.features || []).length > 0;
  }, [stageProgress, ir]);

  const isHowComplete = useMemo(() => {
    const howStage = stageProgress?.stages?.find((s: any) => s.stage === 'how');
    if (stageProgress?.stages && howStage) {
      return Boolean(howStage.unlocked && (howStage.statusCode === 'ready' || howStage.statusCode === 'ready_to_advance' || howStage.content_complete || ((ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0)));
    }
    return (ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0;
  }, [stageProgress, ir]);

  const isScopeComplete = useMemo(() => {
    const scopeStage = stageProgress?.stages?.find((s: any) => s.stage === 'scope');
    if (stageProgress?.stages && scopeStage) {
      return Boolean(scopeStage.unlocked && (scopeStage.statusCode === 'ready' || scopeStage.statusCode === 'ready_to_advance' || scopeStage.content_complete || (ir?.features || []).some((f: any) => f.scope !== null && f.scope !== undefined)));
    }
    return (ir?.features || []).some((feature: any) => feature.scope !== null && feature.scope !== undefined);
  }, [stageProgress, ir]);

  const isPreviewReady = isWhatComplete && isHowComplete && isScopeComplete;

  useEffect(() => {
    window.dispatchEvent(new CustomEvent('prototype-preview-updated', { detail: {
      projectId: ir?.projectId,
      branchRef,
      status: prototypeState === 'error' ? 'failed' : prototype?.status || 'idle',
      compiled: prototypeState === 'ready' && Boolean(prototype?.pages?.length
        ? prototype.pages.every(page => page.status === 'ready' && page.html.trim())
        : prototype?.html?.trim()),
    } }));
  }, [prototype, prototypeState, ir?.projectId, branchRef]);

  // Dynamic substitution of ir with virtual requirement space during shadow ready status
  // When isPreviewReady is true, the real project is complete, so never use shadow draft.
  const spaceToUse = useMemo(() => {
    if (!isPreviewReady && activeShadowDraft?.source === 'shadow_project' && activeShadowDraft.status === 'ready' && activeShadowDraft.shadowSnapshotJson) {
      const snap = activeShadowDraft.shadowSnapshotJson;
      return {
        projectId: ir?.projectId,
        projectName: snap.project_name,
        projectDescription: snap.project_description,
        userRequirements: snap.user_requirements,
        actors: snap.actors.map((a: any) => ({
          actorId: a.actor_id,
          actorName: a.actor_name,
          actorDescription: a.actor_description
        })),
        features: snap.features.map((f: any) => ({
          featureId: f.feature_id,
          featureName: f.feature_name,
          featureDescription: f.feature_description,
          actorIds: f.actor_ids,
          parentId: f.parent_id,
          childrenIds: f.children_ids,
          scenarios: f.scenarios.map((s: any) => ({
            scenarioId: s.scenario_id,
            scenarioName: s.scenario_name,
            scenarioContent: s.scenario_content,
            featureId: s.feature_id,
            actorId: s.actor_id,
            acceptanceCriteria: s.acceptance_criteria.map((ac: any) => ({
              criterionId: ac.criterion_id,
              criterionContent: ac.criterion_content,
              position: ac.position
            }))
          })),
          scope: f.scope ? {
            scopeId: f.scope.scope_id,
            scopeStatus: f.scope.scope_status,
            reason: f.scope.reason,
            kanoCategory: f.scope.kano_category,
            kanoCategoryName: f.scope.kano_category_name
          } : null
        })),
        flows: snap.flows.map((fl: any) => ({
          featureIds: fl.feature_ids,
          flowSteps: fl.flow_steps.map((step: any) => ({
            stepName: step.step_name,
            actorIds: step.actor_ids,
          }))
        })),
        findings: []
      };
    }
    return ir;
  }, [ir, activeShadowDraft, isPreviewReady]);

  // On page entry or branch switch, only load existing preview state. Do not auto-trigger shadow convergence.
  useEffect(() => {
    let cancelled = false;
    const projectId = ir?.projectId;
    if (!projectId) {
      setIsDraftInitializing(false);
      return;
    }

    setPrototype(null);
    setPrototypeState('idle');
    setPrototypeError(null);
    setHasRequestedShadowPreview(false);
    setSmoothProgress(0);
    if (isPreviewReady) {
      useWorkspaceStore.setState({ activeShadowDraft: null });
      setIsDraftInitializing(true);
      workspaceApi.getLatestPrototypePreview(projectId, branchRef)
        .then((res) => {
          if (!cancelled) {
            if (res && !('detail' in res) && (res as any).prototypeId && (res as any).message !== 'prototype_preview_not_found') {
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
  }, [ir?.projectId, branchRef, isPreviewReady]);

  // Resume a persisted prototype job after the POST returns or the page refreshes.
  useEffect(() => {
    if (prototype?.status !== 'generating' || !ir?.projectId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = () => {
      workspaceApi.getLatestPrototypePreview(ir.projectId, branchRef)
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
  }, [prototype?.prototypeId, prototype?.status, ir?.projectId, branchRef]);


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
      if (generationFailed && hasRequestedShadowPreview) {
        setProgressSubtitle(t('preview.full.progressFailed'));
        setIsModalOpen(true); // Keep modal open to show traceback!
        return;
      }
      if ((prototypeState === 'ready' || activeShadowDraftRef.current?.status === 'ready') && smoothProgress > 0 && smoothProgress < 100) {
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
  }, [activeShadowDraft?.status, activeShadowDraft?.unreadyGates, activeShadowDraft?.unready_gates, prototypeState, generationFailed, hasRequestedShadowPreview, t]);

  // Set prototype state and values based on activeShadowDraft in unconverged shadow mode
  useEffect(() => {
    if (isPreviewReady || isPostCommitCompiling) return;

    if (!activeShadowDraft) {
      setPrototype(null);
      setPrototypeState('idle');
      return;
    }

    if (activeShadowDraft.source === 'real_project') {
      if (activeShadowDraft.prototypePreview?.prototypeId) {
        setPrototype(activeShadowDraft.prototypePreview);
      } else {
        setPrototype(null);
      }
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
        if (activeShadowDraft.prototypePreview) {
          setPrototype(activeShadowDraft.prototypePreview);
          setPrototypeState('ready');
          setPrototypeError(null);
        } else {
          setPrototype(null);
          setPrototypeState('idle');
        }
      } else if (status === 'failed') {
        setPrototype(null);
        setPrototypeState('error');
        setPrototypeError(t('preview.full.shadowFailure'));
      } else {
        setPrototype(null);
        setPrototypeState('idle');
      }
    }
  }, [activeShadowDraft, isPreviewReady, isPostCommitCompiling]);

  // Polling driver for real prototype after committing shadow draft
  useEffect(() => {
    if (!isPostCommitCompiling || !ir?.projectId) return;

    let cancelled = false;
    let pollCount = 0;
    const maxPolls = 20; // Polling up to 60 seconds (20 * 3s)

    const poll = () => {
      if (cancelled) return;
      workspaceApi.getLatestPrototypePreview(ir.projectId, branchRef)
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
  }, [isPostCommitCompiling, ir?.projectId, branchRef]);



  const actors = useMemo(() => spaceToUse?.actors || [], [spaceToUse]);
  const issues = useMemo(() => spaceToUse?.findings || [], [spaceToUse]);
  const activeRole = actors[activeRoleIndex];

  const pages = useMemo(() => {
    if (!spaceToUse || !activeRole) return [];
    return buildRolePages(spaceToUse as any, String(activeRole.actorId));
  }, [activeRole, spaceToUse]);

  const unresolvedIssues = issues.filter((finding: any) => (finding.status || 'open') === 'open');

  const rolePrototypePages = useMemo(() => {
    if (!prototype?.pages?.length || !activeRole) return [];
    return prototype.pages.filter((page) => String(page.roleId) === String(activeRole.actorId));
  }, [activeRole, prototype]);

  const activePrototypePage = useMemo(() => {
    if (!prototype) return null;
    if (!activeRole) return prototype.pages?.[0] || null;
    return rolePrototypePages.find((page) => page.pageId === activePrototypePageId) || rolePrototypePages[0] || null;
  }, [activePrototypePageId, activeRole, prototype, rolePrototypePages]);

  const prototypeSrcDoc = useMemo(
    () => {
      if (!prototype) return '';
      if (activeRole && prototype.pages?.length && !activePrototypePage) return '';
      return composePrototypeSrcDoc(activePrototypePage || prototype);
    },
    [activePrototypePage, activeRole, prototype],
  );

  const hasCompiledPrototype = useMemo(() => {
    if (!prototype) return false;
    if (prototype.status === 'failed' || (prototype as any).message === 'prototype_preview_not_found') return false;
    if (prototype.status === 'generating') return true;
    const hasHtml = Boolean(prototype.html && prototype.html.trim().length > 0);
    const hasPages = Boolean(prototype.pages && prototype.pages.length > 0);
    return hasHtml || hasPages;
  }, [prototype]);

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
      const requestedBranch = branchRef;
      try {
        const result = await workspaceApi.generatePrototypePreview(spaceToUse.projectId, true, branchRef);
        if (branchRefCurrent.current !== requestedBranch) return;
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
        if (branchRefCurrent.current !== requestedBranch) return;
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
      navigate(buildProjectRouteWithBranch(spaceToUse?.projectId || ir?.projectId, '/overview', useWorkspaceStore.getState().branchRef));
    } catch (err) {
      showToast(t('preview.full.discardFailed', { error: err instanceof Error ? err.message : String(err) }));
    }
  };

  const handleCommit = async () => {
    if (!activeShadowDraft?.draftId) return;
    if (!window.confirm(t('preview.full.commitConfirm'))) return;
    try {
      setIsPostCommitCompiling(true);
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
              onClick={() => navigate(buildProjectRouteWithBranch(spaceToUse?.projectId || ir?.projectId, '/what', useWorkspaceStore.getState().branchRef))}
            />
            <ReadinessCard
              title="How"
              ready={isHowComplete}
              description={t('preview.full.howRequirement')}
              onClick={() => navigate(buildProjectRouteWithBranch(spaceToUse?.projectId || ir?.projectId, '/flow', useWorkspaceStore.getState().branchRef))}
            />
            <ReadinessCard
              title="Scope"
              ready={isScopeComplete}
              description={t('preview.full.scopeRequirement')}
              onClick={() => navigate(buildProjectRouteWithBranch(spaceToUse?.projectId || ir?.projectId, '/scope', useWorkspaceStore.getState().branchRef))}
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
        <div className="w-full max-w-7xl 2xl:max-w-[1720px] 3xl:max-w-[1920px] mx-auto space-y-8 animate-in fade-in flex flex-col min-h-full">
          {/* Export Toolbar (collapsed delivery banner: only the dropdown matters) */}
          <div className="flex justify-end relative z-30">
            <div className="relative flex items-center" ref={exportMenuRef}>
              <button
                type="button"
                onClick={() => setIsExportMenuOpen((prev) => !prev)}
                disabled={exportState === 'exporting'}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200/80 bg-white/90 backdrop-blur-xs px-4 py-2.5 text-xs font-bold text-slate-700 shadow-2xs transition-all hover:border-slate-300 hover:bg-white disabled:opacity-60 cursor-pointer"
              >
                <FileDown className="h-3.5 w-3.5 text-indigo-500" />
            {t('preview.exportSection')}
                <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform ${isExportMenuOpen ? 'rotate-180' : ''}`} />
              </button>
              {isExportMenuOpen && (
                <>
                  <div className="absolute right-0 top-[calc(100%+10px)] z-50 min-w-[280px] overflow-hidden rounded-2xl border border-slate-200/90 bg-white/95 backdrop-blur-xl p-2 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
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
                </>
              )}
            </div>
          </div>

          {/* Shadow Sandbox Banner */}
          {!isPreviewReady && activeShadowDraft?.source === 'shadow_project' && activeShadowDraft.status === 'ready' && (
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

          {/* Integrated Interactive Prototype Section */}
          {!hasCompiledPrototype ? (
            /* Full-width Onboarding & Prototype Generation Hero Card */
            <GlassSurface variant="elevated" className="flex-1 min-h-[420px] p-8 sm:p-12 text-center flex flex-col items-center justify-center space-y-8">
              <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-indigo-500/10 via-indigo-500/5 to-teal-500/10 border border-indigo-200/60 flex items-center justify-center text-indigo-600 shadow-inner">
                <MonitorPlay className="w-10 h-10 text-indigo-600" />
              </div>

              <div className="space-y-3 max-w-xl">
                <h3 className="text-2xl font-black text-slate-900 tracking-tight">
                  {isPreviewReady
                    ? t('preview.full.readyToCompileTitle', '前置规约已齐备，准备编译交互式原型')
                    : t('preview.full.noPrototypeTitle', '尚未生成交互式原型')}
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed max-w-lg mx-auto font-medium">
                  {isPreviewReady
                    ? t('preview.full.readyToCompileDesc', '系统已汇聚参与者角色、功能特征树、业务流程泳道及交付范围决策，点击下方按钮即可一键编译生成完整多角色运行态交互原型。')
                    : t('preview.full.incompleteCompileDesc', '当前项目前置阶段尚未全部收敛，可点击下方生成临时影子原型探索或前往补齐前置规约。')}
                </p>
              </div>

              {/* Summary Metric Badges */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-xl">
                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 flex flex-col items-center gap-1.5 shadow-2xs">
                  <User className="w-5 h-5 text-indigo-600" />
                  <span className="text-lg font-black text-slate-800">{(ir?.actors || []).length}</span>
                  <span className="text-[11px] font-bold text-slate-400">{t('nav.stageName.what')} / 角色</span>
                </div>
                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 flex flex-col items-center gap-1.5 shadow-2xs">
                  <Folder className="w-5 h-5 text-indigo-600" />
                  <span className="text-lg font-black text-slate-800">{(ir?.features || []).length}</span>
                  <span className="text-[11px] font-bold text-slate-400">{t('nav.stageName.what')} / 功能点</span>
                </div>
                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 flex flex-col items-center gap-1.5 shadow-2xs">
                  <Workflow className="w-5 h-5 text-indigo-600" />
                  <span className="text-lg font-black text-slate-800">{(ir?.flows || []).length}</span>
                  <span className="text-[11px] font-bold text-slate-400">{t('nav.stageName.how')} / 流程泳道</span>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
                <button
                  type="button"
                  onClick={() => void generatePrototype()}
                  disabled={prototypeState === 'loading'}
                  className="inline-flex items-center gap-2.5 rounded-2xl bg-indigo-600 hover:bg-indigo-700 px-8 py-3.5 text-sm font-black text-white shadow-lg shadow-indigo-600/20 transition-all hover:shadow-indigo-600/30 active:scale-[0.98] cursor-pointer disabled:opacity-60"
                >
                  <Sparkles className={`w-4 h-4 text-amber-300 ${prototypeState === 'loading' ? 'animate-spin' : 'animate-pulse'}`} />
                  <span>
                    {prototypeState === 'loading'
                      ? t('preview.full.generatingPrototype')
                      : t('preview.full.compilePrototypeBtn', '一键编译生成交互式原型')}
                  </span>
                </button>
              </div>
            </GlassSurface>
          ) : (
            /* Side-by-Side Interactive Prototype & Blueprints Panel when prototype is compiled */
            <GlassSurface className="relative overflow-visible p-0">
              <div className="border-b border-slate-200/60 px-6 py-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-slate-50/50">
                <div className="flex items-center gap-3">
                  <h3 className="text-base font-black text-slate-900 tracking-tight flex items-center gap-2">
                    <MonitorPlay className="w-5 h-5 text-teal-600" />
                    {t('preview.full.quickPrototype')}
                  </h3>

                </div>
                
                <div className="flex items-center gap-2 shrink-0">
                  {/* Fullscreen Mode Button */}
                  <button
                    type="button"
                    onClick={() => setIsFullscreenPreview(true)}
                    disabled={!prototypeSrcDoc || prototypeState === 'loading'}
                    className="px-3 py-2 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 transition-colors bg-white flex items-center gap-1.5 disabled:opacity-50 shadow-sm cursor-pointer"
                    title={t('preview.full.fullscreenPreview')}
                  >
                    <Maximize2 className="w-3.5 h-3.5 text-indigo-500" />
                    <span className="hidden md:inline">{t('preview.full.fullscreenPreview')}</span>
                  </button>

                  {/* Regenerate button */}
                  <button
                    type="button"
                    onClick={() => void generatePrototype()}
                    disabled={prototypeState === 'loading'}
                    className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-colors flex items-center gap-1.5 disabled:opacity-60 shadow-md cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${prototypeState === 'loading' ? 'animate-spin' : ''}`} />
                    {t('preview.full.regeneratePrototype')}
                  </button>

                  {/* Secondary Preview Actions */}
                  <div className="relative" ref={previewMenuRef}>
                    <button
                      type="button"
                      onClick={() => setIsPreviewMenuOpen((open) => !open)}
                      className="h-9 w-9 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors bg-white inline-flex items-center justify-center cursor-pointer"
                      aria-label={t('preview.full.morePreviewActions')}
                      aria-expanded={isPreviewMenuOpen}
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                    {isPreviewMenuOpen && (
                      <>
                        <div className="absolute right-0 top-[calc(100%+8px)] z-50 min-w-56 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg">
                          <button
                            type="button"
                            onClick={() => {
                              setIsPreviewMenuOpen(false);
                              openPrototypeInWindow();
                            }}
                            disabled={!prototypeSrcDoc || prototypeState === 'loading'}
                            className="w-full rounded-lg px-3 py-2.5 text-left text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                          >
                            <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
                            {t('preview.full.openPrototype')}
                          </button>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Collapse / Expand Specs Button */}
                  <button
                    type="button"
                    onClick={() => setIsRightPanelCollapsed((prev) => !prev)}
                    className={`px-3 py-2 rounded-xl border transition-all text-xs font-bold flex items-center gap-1.5 cursor-pointer ${
                      isRightPanelCollapsed
                        ? 'bg-indigo-50 border-indigo-200 text-indigo-700 hover:bg-indigo-100'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                    title={isRightPanelCollapsed ? t('preview.full.expandSpecs') : t('preview.full.collapseSpecs')}
                  >
                    {isRightPanelCollapsed ? (
                      <>
                        <PanelRightOpen className="w-3.5 h-3.5 text-indigo-600" />
                        <span>{t('preview.full.expandSpecs')}</span>
                      </>
                    ) : (
                      <>
                        <PanelRightClose className="w-3.5 h-3.5 text-slate-500" />
                        <span className="hidden sm:inline">{t('preview.full.collapseSpecs')}</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Viewport Split Screen */}
              <div className="grid grid-cols-1 lg:grid-cols-12 border-t border-slate-100 relative">
                
                {/* Prototype Simulator Column (Takes 12 columns when specs collapsed, 7 columns when expanded) */}
                <div className={`${isRightPanelCollapsed ? 'lg:col-span-12' : 'lg:col-span-7 border-r border-slate-200'} bg-slate-100/50 p-6 flex flex-col justify-center transition-all duration-300`}>
                  <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden flex flex-col h-[740px] w-full transition-all duration-300">
                    <div className="h-10 px-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
                      <div className="flex gap-1.5 items-center min-w-0">
                        <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block shrink-0" />
                        <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block shrink-0" />
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block shrink-0" />
                        <span className="ml-3 text-xs text-slate-400 font-mono select-none truncate">
                          /projects/{spaceToUse?.projectId || 'current'}/roles/{activeRole?.actorName || 'role'}/{activePrototypePage?.featureName || 'prototype'}
                        </span>
                      </div>
                      <span className="text-[10px] bg-slate-200 border border-slate-300 text-slate-500 px-2 py-0.5 rounded font-mono font-bold select-none shrink-0 ml-2">
                        1440px FIT
                      </span>
                    </div>
                    {rolePrototypePages.length > 0 && (
                      <div className="shrink-0 border-b border-slate-200 bg-white px-3 py-2 flex flex-wrap gap-2">
                        {rolePrototypePages.map((page) => (
                          <button
                            key={page.pageId}
                            type="button"
                            onClick={() => setActivePrototypePageId(page.pageId)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors cursor-pointer ${
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
                      ) : activeRole && prototype.pages?.length && rolePrototypePages.length === 0 ? (
                        <PrototypePlaceholder label={t('preview.full.noGeneratedRolePreview')} />
                      ) : (
                        <ScaledPrototypeFrame
                          frameKey={activePrototypePage?.pageId || prototype.shadowDraftId || prototype.prototypeId}
                          title={`${activeRole?.actorName || spaceToUse?.projectName || 'Project'} prototype`}
                          srcDoc={prototypeSrcDoc}
                          viewport="desktop"
                          showScale
                        />
                      )}
                    </div>
                  </div>
                </div>

                {/* Right Column: Dynamic Role Blueprint Specifications (shown when not collapsed) */}
                {!isRightPanelCollapsed && (
                  <div className="lg:col-span-5 p-6 overflow-y-auto max-h-[788px] space-y-6 flex flex-col animate-in fade-in slide-in-from-right-4 duration-300">
                    <div className="border-b border-slate-100 pb-3 flex items-center justify-between shrink-0">
                      <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1">
                        <span className="flex items-center gap-1.5"><BookOpen className="w-4 h-4 text-slate-500 shrink-0" /> {t('preview.full.roleSpecs')}</span>
                      </h4>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-2 py-0.5 rounded">
                          {t('preview.full.pageCount', { count: pages.length })}
                        </span>
                        <button
                          type="button"
                          onClick={() => setIsRightPanelCollapsed(true)}
                          className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 cursor-pointer"
                          title={t('preview.full.collapseSpecs')}
                        >
                          <PanelRightClose className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Role Tabs inside Specification container */}
                    <div className="flex flex-wrap items-center gap-1.5 shrink-0 bg-slate-50 p-1.5 rounded-xl border border-slate-200">
                      {actors.map((actor: any, idx: number) => (
                        <button
                          key={actor.actorId}
                          type="button"
                          onClick={() => {
                            setActiveRoleIndex(idx);
                            setActivePrototypePageId('');
                          }}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                            activeRoleIndex === idx
                              ? 'bg-white text-indigo-600 shadow-sm border border-indigo-100/50'
                              : 'text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          <span className="flex items-center gap-1"><User className="w-3.5 h-3.5 text-indigo-500 shrink-0" /> {actor.actorName}</span>
                        </button>
                      ))}
                    </div>

                    {/* Active Role Content */}
                    <div className="space-y-4 flex-1">
                      {pages.length === 0 ? (
                        <div className="p-8 text-center bg-slate-50/50 rounded-2xl border border-slate-100 space-y-3 my-auto">
                          <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 mx-auto">
                            <Eye className="w-5 h-5" />
                          </div>
                          <div className="space-y-1">
                            <h5 className="font-bold text-slate-700 text-xs">{t('preview.full.noRolePreview')}</h5>
                            <p className="text-[11px] text-slate-400 max-w-xs mx-auto leading-relaxed">
                              {t('preview.full.noRolePreviewDescription')}
                            </p>
                          </div>
                        </div>
                      ) : (
                        pages.map((page: any) => (
                          <div key={page.id} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
                            <div className="border-b border-slate-100 pb-3">
                              <h5 className="font-black text-slate-800 text-sm flex items-center gap-2">
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
                )}
              </div>
            </GlassSurface>
          )}

          {prototypeState === 'error' && (
            <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
              {prototypeError || t('preview.full.prototypeFailure')}
            </div>
          )}

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

        </div>
      </div>

      {/* Smart Loading Modal Overlay with Animated Progress Bar */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-300">
          <div className="w-[520px] max-w-full mx-4 bg-white/95 border border-slate-200/80 rounded-3xl p-8 shadow-2xl flex flex-col items-center select-none relative animate-in zoom-in-95 duration-300">
            
            {/* Header Glowing Sparkle */}
            <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-5 shadow-inner">
              {generationFailed ? (
                <XCircle className="w-8 h-8 text-rose-500 animate-bounce" />
              ) : smoothProgress === 100 ? (
                <CheckCircle2 className="w-8 h-8 text-emerald-500 scale-110 transition-transform duration-500" />
              ) : (
                <Sparkles className="w-8 h-8 text-indigo-600 animate-pulse" />
              )}
            </div>

            {/* Title */}
            <h3 className="text-sm font-black text-slate-800 tracking-wide text-center leading-none mb-2">
              {generationFailed ? (
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
              generationFailed ? 'text-rose-500' : 'text-slate-500'
            }`}>
              {progressSubtitle}
            </p>

            {/* Progress Bar Container */}
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden mb-8 mt-4 border border-slate-200/50">
              <div 
                className={`h-full transition-all duration-300 ease-out ${
                  generationFailed
                    ? 'bg-rose-500' 
                    : smoothProgress === 100 
                      ? 'bg-emerald-500' 
                      : 'bg-indigo-600'
                }`}
                style={{ width: `${smoothProgress}%` }}
              />
            </div>

            {/* Sub-steps Checklist */}
            <div className="w-full space-y-3 bg-slate-50/80 border border-slate-200/60 p-5 rounded-2xl mb-6">
              {(isShadowOverlay
                ? [
                    { label: t('preview.full.stepWhat'), checkKey: 'what', threshold: 35 },
                    { label: t('preview.full.stepHow'), checkKey: 'how', threshold: 70 },
                    { label: t('preview.full.stepScope'), checkKey: 'scope', threshold: 90 },
                    { label: t('preview.full.stepAssembly'), checkKey: 'all', threshold: 100 },
                  ]
                : [
                    { label: t('preview.full.stepInteractiveParse'), checkKey: 'what', threshold: 30 },
                    { label: t('preview.full.stepInteractiveFlow'), checkKey: 'how', threshold: 65 },
                    { label: t('preview.full.stepInteractiveUi'), checkKey: 'scope', threshold: 90 },
                    { label: t('preview.full.stepInteractiveAssembly'), checkKey: 'all', threshold: 100 },
                  ]
              ).map((step, idx, arr) => {
                const isFailed = generationFailed;
                const isStepFinished = isShadowOverlay
                  ? (step.checkKey === 'all'
                      ? smoothProgress === 100
                      : !(activeShadowDraft?.unreadyGates || activeShadowDraft?.unready_gates || []).includes(step.checkKey) || smoothProgress >= step.threshold)
                  : smoothProgress >= step.threshold;

                const prevThreshold = idx === 0 ? 0 : arr[idx - 1].threshold;
                const isStepActive =
                  !isFailed && !isStepFinished && smoothProgress >= prevThreshold && smoothProgress < step.threshold;

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

            {/* Error message collapsible container (collapsible terminal box) */}
            {generationFailed && (
              <div className="w-full flex flex-col mb-6 bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-md">
                <div className="bg-slate-950 px-4 py-2 border-b border-slate-800 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" /> {t('preview.full.tracebackTitle')}
                  </span>
                  <button 
                    onClick={() => {
                      navigator.clipboard.writeText(generationError);
                      showToast(t('preview.copyLogsSuccess'));
                    }}
                    className="text-[9px] bg-slate-800 border border-slate-700 text-slate-300 font-bold px-2 py-0.5 rounded hover:bg-slate-700 hover:text-white transition-colors"
                  >
                    {t('preview.copyLogsBtn')}
                  </button>
                </div>
                <div className="p-4 max-h-[160px] overflow-y-auto font-mono text-[10px] text-rose-400/90 leading-relaxed scrollbar-thin select-text text-left">
                  {generationError}
                </div>
              </div>
            )}

            {/* Action Button (Dismiss on fail) */}
            {generationFailed && (
              <button
                onClick={() => {
                  setHasRequestedShadowPreview(false);
                  if (!activeShadowDraft?.draftId) {
                    setIsModalOpen(false);
                    setSmoothProgress(0);
                    return;
                  }
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

      {/* Fullscreen Interactive Prototype Modal */}
      {isFullscreenPreview && typeof document !== 'undefined' && createPortal(
        <div className="fixed inset-0 z-[100] bg-slate-950/95 backdrop-blur-md flex flex-col animate-in fade-in duration-200">
          {/* Fullscreen Top Control Bar */}
          <div className="h-14 px-6 bg-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <MonitorPlay className="w-5 h-5 text-teal-400" />
                <span className="text-sm font-black text-white tracking-tight">
                  {t('preview.full.fullscreenPreview')}
                </span>
              </div>

              {/* Role Page Selectors in Fullscreen */}
              {rolePrototypePages.length > 0 && (
                <div className="hidden md:flex items-center gap-1.5 overflow-x-auto max-w-xl">
                  {rolePrototypePages.map((page) => (
                    <button
                      key={page.pageId}
                      type="button"
                      onClick={() => setActivePrototypePageId(page.pageId)}
                      className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                        activePrototypePage?.pageId === page.pageId
                          ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40'
                          : 'bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700/50'
                      }`}
                    >
                      {page.featureName}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              {/* Device Viewport Switcher */}
              <div className="flex items-center bg-slate-800 p-0.5 rounded-xl border border-slate-700" role="group" aria-label={t('preview.full.viewportPresets')}>
                <button
                  type="button"
                  onClick={() => setDeviceViewport('desktop')}
                  aria-pressed={deviceViewport === 'desktop'}
                  className={`h-9 px-2.5 rounded-lg text-xs font-bold transition-colors cursor-pointer inline-flex items-center gap-1.5 ${
                    deviceViewport === 'desktop'
                      ? 'bg-slate-700 text-white shadow-2xs'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title={t('preview.full.desktopView')}
                >
                  <Monitor className="w-4 h-4" />
                  <span className="hidden lg:inline">1440</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDeviceViewport('tablet')}
                  aria-pressed={deviceViewport === 'tablet'}
                  className={`h-9 px-2.5 rounded-lg text-xs font-bold transition-colors cursor-pointer inline-flex items-center gap-1.5 ${
                    deviceViewport === 'tablet'
                      ? 'bg-slate-700 text-white shadow-2xs'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title={t('preview.full.tabletView')}
                >
                  <Tablet className="w-4 h-4" />
                  <span className="hidden lg:inline">768</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDeviceViewport('mobile')}
                  aria-pressed={deviceViewport === 'mobile'}
                  className={`h-9 px-2.5 rounded-lg text-xs font-bold transition-colors cursor-pointer inline-flex items-center gap-1.5 ${
                    deviceViewport === 'mobile'
                      ? 'bg-slate-700 text-white shadow-2xs'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title={t('preview.full.mobileView')}
                >
                  <Smartphone className="w-4 h-4" />
                  <span className="hidden lg:inline">375</span>
                </button>
              </div>

              {/* Close Fullscreen Button */}
              <button
                type="button"
                onClick={() => setIsFullscreenPreview(false)}
                className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 border border-slate-700 cursor-pointer"
              >
                <X className="w-4 h-4" />
                <span>{t('preview.full.exitFullscreen')}</span>
              </button>
            </div>
          </div>

          {/* Fullscreen Iframe Viewport */}
          <div className="flex-1 min-h-0 bg-slate-900/60 p-4 sm:p-6 flex items-center justify-center overflow-hidden">
            {activeRole && prototype?.pages?.length && rolePrototypePages.length === 0 ? (
              <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-8 text-center text-sm font-bold text-slate-300">
                {t('preview.full.noGeneratedRolePreview')}
              </div>
            ) : (
              <ScaledPrototypeFrame
                frameKey={`fullscreen-${activePrototypePage?.pageId || prototype?.shadowDraftId || prototype?.prototypeId}`}
                title={`${activeRole?.actorName || spaceToUse?.projectName || 'Project'} full prototype`}
                srcDoc={prototypeSrcDoc}
                viewport={deviceViewport}
                showScale
              />
            )}
          </div>
        </div>,
        document.body
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

const PROTOTYPE_VIEWPORT_WIDTHS: Record<DeviceViewport, number> = {
  desktop: 1440,
  tablet: 768,
  mobile: 375,
};

function ScaledPrototypeFrame({
  frameKey,
  title,
  srcDoc,
  viewport,
  showScale = false,
}: {
  frameKey: string | number;
  title: string;
  srcDoc: string;
  viewport: DeviceViewport;
  showScale?: boolean;
}) {
  const { t } = useTranslation();
  const stageRef = useRef<HTMLDivElement>(null);
  const [stageWidth, setStageWidth] = useState(0);
  const logicalWidth = PROTOTYPE_VIEWPORT_WIDTHS[viewport];
  const scale = stageWidth > 0 ? Math.min(1, stageWidth / logicalWidth) : 1;

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;

    const updateWidth = () => setStageWidth(stage.clientWidth);
    updateWidth();

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateWidth);
      return () => window.removeEventListener('resize', updateWidth);
    }

    const observer = new ResizeObserver(updateWidth);
    observer.observe(stage);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={stageRef} className="relative h-full w-full min-h-0 min-w-0 overflow-hidden bg-slate-200/70 flex justify-center">
      <div
        className="h-full overflow-hidden bg-white transition-[width] duration-200 motion-reduce:transition-none"
        style={{ width: logicalWidth * scale }}
      >
        <iframe
          key={frameKey}
          title={title}
          srcDoc={srcDoc}
          className="border-0 bg-white origin-top-left transition-transform duration-200 motion-reduce:transition-none"
          style={{
            width: logicalWidth,
            height: `${100 / scale}%`,
            transform: `scale(${scale})`,
          }}
        />
      </div>
      {showScale && (
        <span className="pointer-events-none absolute bottom-2 right-2 rounded-md bg-slate-950/75 px-2 py-1 text-[10px] font-bold text-slate-200">
          {t('preview.full.fitScale', { scale: Math.round(scale * 100) })}
        </span>
      )}
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
      ? html.replace('</head>', () => `${css}</head>`)
      : `${css}${html}`;
  }

  if (javascript) {
    html = html.includes('</body>')
      ? html.replace('</body>', () => `${javascript}</body>`)
      : `${html}${javascript}`;
  }

  return html;
}

function sanitizePrototypeHtml(html: string) {
  return html
    .replace(/<script[^>]+src=["'](?:\.\/)?script\.js["'][^>]*>\s*<\/script>/gi, '')
    .replace(/<link\b(?=[^>]*\brel=["'](?:stylesheet|preconnect|dns-prefetch)["'])[^>]*>/gi, '');
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
