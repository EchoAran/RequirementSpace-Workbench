import { useState, useEffect, useRef } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { 
  ArrowLeft, 
  MessageCircle, 
  UploadCloud, 
  File, 
  Trash2, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  XCircle 
} from 'lucide-react';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';
import { ProjectInterviewDialog } from '@/components/shared/ProjectInterviewDialog';
import { useNavigate } from 'react-router-dom';
import { buildProjectRoute } from '@/core/selectors';
import { useTranslation } from 'react-i18next';

export function ProjectOnboarding() {
  const { t } = useTranslation();
  const {
    startAIOnboarding,
    confirmAIOnboarding,
    regenerateAIOnboarding,
    discardAIOnboarding,
    createBlankWorkspace,
    activeDraft,
    activeDraftType,
    isLoading,
    isGenerating,
    error,
    activeChoiceGroup,
    choiceGroupGenerationProgress,
    isGeneratingChoices,
    createOnboardingChoiceGroup,
    acceptOnboardingChoice,
    discardOnboardingChoiceGroup,
    deferOnboardingChoiceGroup,

    // Knowledge Base states & actions
    creationWorkspaceId,
    creationDocuments,
    initCreationWorkspace,
    loadCreationDocuments,
    uploadCreationDocument,
    deleteCreationDocument,
    retryCreationDocument,
    isUploadingDocument,
    knowledgeBaseEnabled,
  } = useWorkspaceStore();

  const navigate = useNavigate();

  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isInterviewOpen, setIsInterviewOpen] = useState(false);
  
  // Drag & drop state
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Warning modal for converting files
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [pendingAction, setPendingAction] = useState<'createBlank' | 'generateChoice' | null>(null);

  const isWorking = isLoading || isGenerating || isGeneratingChoices || isUploadingDocument;

  // Initialize workspace
  useEffect(() => {
    void initCreationWorkspace();
  }, [initCreationWorkspace]);

  // Load and poll documents
  useEffect(() => {
    if (!creationWorkspaceId) return;
    void loadCreationDocuments();
  }, [creationWorkspaceId, loadCreationDocuments]);

  // Document polling effect based on document statuses
  const docStatusesKey = creationDocuments.map((d) => `${d.public_id}:${d.status}`).join(',');
  useEffect(() => {
    if (!creationWorkspaceId) return;
    
    const hasProcessing = creationDocuments.some(
      (doc) => doc.status === 'uploaded' || doc.status === 'converting'
    );
    if (!hasProcessing) return;

    const timer = setInterval(() => {
      void loadCreationDocuments();
    }, 3000);

    return () => clearInterval(timer);
  }, [creationWorkspaceId, docStatusesKey, loadCreationDocuments]);

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        await uploadCreationDocument(e.dataTransfer.files[i]);
      }
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      for (let i = 0; i < e.target.files.length; i++) {
        await uploadCreationDocument(e.target.files[i]);
      }
    }
  };

  const handleGenerateChoiceGroup = async () => {
    if (!prompt.trim()) return;
    await createOnboardingChoiceGroup(prompt.trim(), 2);
  };

  const handleCreateBlank = async () => {
    if (!prompt.trim()) return;
    const projectId = await createBlankWorkspace(name.trim(), description.trim(), prompt.trim());
    if (projectId) {
      navigate(buildProjectRoute(projectId, '/overview'));
    }
  };

  // Check before action execution
  const checkProcessingAndExecute = (action: 'createBlank' | 'generateChoice') => {
    const hasProcessing = creationDocuments.some(
      (doc) => doc.status === 'uploaded' || doc.status === 'converting'
    );
    if (hasProcessing) {
      setPendingAction(action);
      setShowWarningModal(true);
    } else {
      if (action === 'createBlank') {
        void handleCreateBlank();
      } else {
        void handleGenerateChoiceGroup();
      }
    }
  };

  const proceedWithWarning = () => {
    setShowWarningModal(false);
    if (pendingAction === 'createBlank') {
      void handleCreateBlank();
    } else if (pendingAction === 'generateChoice') {
      void handleGenerateChoiceGroup();
    }
    setPendingAction(null);
  };

  const handleConfirmDraft = async () => {
    const projectId = await confirmAIOnboarding();
    if (projectId) {
      navigate(buildProjectRoute(projectId, '/overview'));
    }
  };

  const handleAcceptChoice = async (choiceId: string) => {
    const projectId = await acceptOnboardingChoice(choiceId);
    if (projectId) {
      navigate(buildProjectRoute(projectId, '/overview'));
    }
  };

  const handleDiscardChoiceGroup = async () => {
    await discardOnboardingChoiceGroup();
  };

  const handleDeferChoiceGroup = async () => {
    const projectId = await deferOnboardingChoiceGroup();
    const state = useWorkspaceStore.getState();
    if (projectId && state.currentSystemView === 'workspace' && state.ir) {
      navigate(buildProjectRoute(state.ir.projectId, '/overview'));
    }
  };

  // File size formatter
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col pt-16 px-6 font-sans">
      <div className="max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-500 relative pb-20">
        <button
          type="button"
          onClick={() => navigate('/home')}
          className="absolute -top-10 left-0 flex items-center gap-1 text-slate-500 hover:text-slate-800 transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('onboarding.backToHome')}
        </button>

        <div className="text-center mb-10 mt-4">
          <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight mb-4">
            {t('onboarding.title')}
          </h1>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-slate-200/80 overflow-hidden relative">
          {isWorking && !isGeneratingChoices && !isUploadingDocument && (
            <div className="absolute inset-0 bg-white/85 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
              <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4" />
              <p className="font-bold text-slate-800 text-base">{t('onboarding.processingDraft')}</p>
              <p className="text-sm text-slate-500 mt-1">{t('onboarding.processingDraftDesc')}</p>
            </div>
          )}

          <div className="p-8 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700 tracking-wide">{t('onboarding.projectNameLabel')}</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-3 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-shadow text-sm"
                  placeholder={t('onboarding.projectNamePlaceholder')}
                  disabled={isWorking}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700 tracking-wide">{t('onboarding.projectDescLabel')}</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full p-3 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-shadow text-sm"
                  placeholder={t('onboarding.projectDescPlaceholder')}
                  disabled={isWorking}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 tracking-wide">{t('onboarding.promptLabel')}</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full h-36 p-4 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none transition-shadow text-sm"
                placeholder={t('onboarding.promptPlaceholder')}
                disabled={isWorking}
              />
            </div>

            {/* Knowledge Base Drag-and-Drop Upload Section */}
            {knowledgeBaseEnabled && (
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-700 tracking-wide flex items-center justify-between">
                  <span>{t('onboarding.kbTitle')}</span>
                  <span className="text-[10px] text-slate-400 font-normal">{t('onboarding.kbNotice')}</span>
                </label>

                <div
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-2xl p-5 text-center cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-2 ${
                    dragActive 
                      ? 'border-indigo-500 bg-indigo-50/50' 
                      : 'border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-300'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                    accept=".txt,.md,.pdf,.docx,.xlsx"
                  />
                  
                  {isUploadingDocument ? (
                    <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
                  ) : (
                    <UploadCloud className="w-8 h-8 text-slate-400" />
                  )}
                  
                  <div className="text-xs font-medium text-slate-600">
                    {isUploadingDocument ? t('onboarding.kbDragging') : t('onboarding.kbDragDrop')}
                  </div>
                </div>

                {/* Uploaded Documents List */}
                {creationDocuments.length > 0 && (
                  <div className="border border-slate-200 rounded-2xl overflow-hidden bg-white divide-y divide-slate-100 max-h-56 overflow-y-auto">
                    {creationDocuments.map((doc) => {
                      const isFailed = doc.status === 'failed';
                      const isProcessing = doc.status === 'uploaded' || doc.status === 'converting';
                      const isReady = doc.status === 'ready';

                      return (
                        <div key={doc.public_id} className="p-3.5 flex items-center justify-between text-xs transition-colors hover:bg-slate-50">
                          <div className="flex items-center gap-3 overflow-hidden mr-4">
                            <File className="w-4 h-4 text-slate-400 shrink-0" />
                            <div className="overflow-hidden">
                              <div className="font-semibold text-slate-700 truncate">{doc.original_filename}</div>
                              <div className="text-[10px] text-slate-400 mt-0.5">{formatBytes(doc.file_size)}</div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 shrink-0">
                            {isReady && (
                              <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 font-bold border border-emerald-100 px-2 py-0.5 rounded-lg text-[10px]">
                                <CheckCircle className="w-3 h-3 text-emerald-600" />
                                {t('onboarding.kbStatusReady')}
                              </span>
                            )}

                            {isProcessing && (
                              <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 font-bold border border-amber-100 px-2 py-0.5 rounded-lg text-[10px] animate-pulse">
                                <Clock className="w-3 h-3 text-amber-500 animate-spin" />
                                {t('onboarding.kbStatusProcessing')}
                              </span>
                            )}

                            {isFailed && (
                              <span className="inline-flex items-center gap-1 bg-rose-50 text-rose-700 font-bold border border-rose-100 px-2 py-0.5 rounded-lg text-[10px]" title={doc.error_message || undefined}>
                                <XCircle className="w-3 h-3 text-rose-500" />
                                {t('onboarding.kbStatusFailed')}
                              </span>
                            )}
                            <div className="flex items-center gap-1">
                              {isFailed && (
                                <button
                                  type="button"
                                  onClick={() => void retryCreationDocument(doc.public_id)}
                                  className="p-1 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-indigo-600 transition-colors"
                                  title={t('onboarding.kbRetryTitle')}
                                >
                                  <RefreshCw className="w-3.5 h-3.5" />
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => void deleteCreationDocument(doc.public_id)}
                                className="p-1 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-rose-600 transition-colors"
                                title={t('onboarding.kbDeleteTitle')}
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {error && (
              <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 text-xs font-medium rounded-xl">
                {error}
              </div>
            )}
        </div>

        <div className="p-6 bg-slate-50 border-t border-slate-100 flex flex-col sm:flex-row justify-end gap-3">
            <button
              type="button"
              onClick={() => setIsInterviewOpen(true)}
              className="inline-flex h-12 min-w-[168px] items-center justify-center rounded-xl border border-amber-200 bg-amber-50 px-6 text-sm font-bold text-amber-700 transition-colors hover:bg-amber-100 disabled:opacity-50"
            >
              <MessageCircle className="w-4 h-4 mr-1.5" />
              {t('onboarding.btnTalk')}
            </button>
            <button
              type="button"
              onClick={() => checkProcessingAndExecute('createBlank')}
              disabled={!prompt.trim() || isWorking}
              className="inline-flex h-12 min-w-[168px] items-center justify-center rounded-xl border border-slate-200 bg-white px-6 text-sm font-bold text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50"
            >
              {t('onboarding.btnCreateBlank')}
            </button>
            <div className="relative group">
              <div className="pointer-events-none absolute bottom-full right-0 mb-2 w-56 rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-xs font-medium leading-relaxed text-slate-600 shadow-lg opacity-0 translate-y-1 transition-all duration-200 group-hover:opacity-100 group-hover:translate-y-0 group-focus-within:opacity-100 group-focus-within:translate-y-0 z-30">
                {t('onboarding.btnGenerateAIChoiceTooltip')}
              </div>
              <button
                type="button"
                onClick={() => checkProcessingAndExecute('generateChoice')}
                disabled={!prompt.trim() || isWorking}
                className="inline-flex h-12 min-w-[168px] items-center justify-center rounded-xl bg-indigo-600 px-6 text-sm font-bold text-white shadow-lg shadow-indigo-100 transition-colors hover:bg-indigo-700 disabled:opacity-50"
              >
                {t('onboarding.btnGenerateAIChoice')}
              </button>
            </div>
        </div>

        <ProjectInterviewDialog
            isOpen={isInterviewOpen}
            onClose={() => setIsInterviewOpen(false)}
          />
        </div>
    </div>

    {/* Warning dialog for documents currently converting/uploading */}
      {showWarningModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-2xl max-w-md w-full space-y-4 animate-in zoom-in-95 duration-200">
            <div className="flex gap-3 items-start">
              <div className="p-2.5 bg-amber-50 rounded-2xl border border-amber-100 text-amber-600 shrink-0">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-black text-slate-800">{t('onboarding.warningModal.title')}</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('onboarding.warningModal.desc')}
                </p>
              </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowWarningModal(false)}
                className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 hover:bg-slate-100 transition-colors"
              >
                {t('onboarding.warningModal.wait')}
              </button>
              <button
                type="button"
                onClick={proceedWithWarning}
                className="px-4 py-2 bg-indigo-600 rounded-xl text-xs font-bold text-white hover:bg-indigo-700 shadow-md shadow-indigo-100 transition-colors"
              >
                {t('onboarding.warningModal.proceed')}
              </button>
            </div>
          </div>
        </div>
    )}

    {/* Choice Group Preview Modal (multi-candidate) */}
      <ChoiceGroupPreviewModal
        group={activeChoiceGroup}
        isWorking={isWorking}
        isGeneratingChoices={isGeneratingChoices}
        generationProgress={choiceGroupGenerationProgress}
        onAccept={handleAcceptChoice}
        onDiscard={handleDiscardChoiceGroup}
        onDefer={handleDeferChoiceGroup}
    />

    {/* Fallback: old single-draft modal (kept for compatibility) */}
      <DraftPreviewModal
        draft={activeDraftType === 'project' ? activeDraft : null}
        draftType={activeDraftType === 'project' ? activeDraftType : null}
        isWorking={isWorking}
        onDiscard={discardAIOnboarding}
        onRegenerate={(feedback) => regenerateAIOnboarding(feedback)}
        onConfirm={handleConfirmDraft}
        confirmLabel={t('onboarding.draftConfirmLabel')}
      />
    </div>
  );
}
