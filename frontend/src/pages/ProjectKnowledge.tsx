import React, { useState, useEffect, useRef } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { useTranslation } from 'react-i18next';
import { DEFAULT_UI_LOCALE } from '@/i18n';
import { 
  UploadCloud, 
  File, 
  Trash2, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  XCircle, 
  Database,
  ArrowRight,
  Sparkles
} from 'lucide-react';

export function ProjectKnowledge() {
  const { t, i18n } = useTranslation();
  const {
    ir,
    projectDocuments,
    isUploadingDocument,
    error,
    loadProjectDocuments,
    uploadProjectDocument,
    deleteProjectDocument,
    retryProjectDocument,
    toggleDocumentAI,
  } = useWorkspaceStore();

  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Deletion modal state
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteTargetName, setDeleteTargetName] = useState<string | null>(null);

  // Load project documents on mount
  useEffect(() => {
    if (ir?.projectId) {
      void loadProjectDocuments();
    }
  }, [ir?.projectId, loadProjectDocuments]);

  // Document polling effect based on document statuses
  const docStatusesKey = projectDocuments.map((d) => `${d.public_id}:${d.status}`).join(',');
  useEffect(() => {
    if (!ir?.projectId) return;

    const hasProcessing = projectDocuments.some(
      (doc) => doc.status === 'uploaded' || doc.status === 'converting'
    );
    if (!hasProcessing) return;

    const timer = setInterval(() => {
      void loadProjectDocuments();
    }, 3000);

    return () => clearInterval(timer);
  }, [ir?.projectId, docStatusesKey, loadProjectDocuments]);

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
        await uploadProjectDocument(e.dataTransfer.files[i]);
      }
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      for (let i = 0; i < e.target.files.length; i++) {
        await uploadProjectDocument(e.target.files[i]);
      }
    }
  };

  const confirmDelete = (docId: string, filename: string) => {
    setDeleteTargetId(docId);
    setDeleteTargetName(filename);
  };

  const handleDelete = async () => {
    if (deleteTargetId) {
      await deleteProjectDocument(deleteTargetId);
      setDeleteTargetId(null);
      setDeleteTargetName(null);
    }
  };

  // Helper formats
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
    return d.toLocaleDateString(i18n.language || DEFAULT_UI_LOCALE, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  // Stats calculators
  const totalSize = projectDocuments.reduce((acc, doc) => acc + doc.file_size, 0);
  const sizePercentage = Math.min((totalSize / (100 * 1024 * 1024)) * 100, 100);
  const activeDocsCount = projectDocuments.filter(d => d.status === 'ready' && d.ai_enabled).length;

  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col font-sans p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto w-full space-y-6">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
              <Database className="w-5 h-5 text-indigo-500" />
              {t('projectKnowledge.pageTitle')}
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              {t('projectKnowledge.pageSubtitle')}
            </p>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Card 1: Documents count */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
            <span className="text-xs font-bold text-slate-500 tracking-wide">{t('projectKnowledge.docTotalCountLabel')}</span>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="text-3xl font-black text-slate-800">{projectDocuments.length}</span>
              <span className="text-xs text-slate-400">{t('projectKnowledge.uploadedCountLabel')}</span>
            </div>
            <div className="text-[10px] text-slate-400 mt-2">{t('projectKnowledge.unreadyFailedNotice')}</div>
          </div>

          {/* Card 2: Space occupied */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
            <span className="text-xs font-bold text-slate-500 tracking-wide">{t('projectKnowledge.storageUsed')}</span>
            <div className="mt-2">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-slate-800">{formatBytes(totalSize)}</span>
                <span className="text-xs text-slate-400">/ 100 MB</span>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full mt-2 overflow-hidden">
                <div 
                  className="bg-indigo-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${sizePercentage}%` }}
                />
              </div>
            </div>
            <div className="text-[10px] text-slate-400 mt-2">{t('projectKnowledge.maxFileSizeNotice')}</div>
          </div>

          {/* Card 3: AI reference status */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
            <span className="text-xs font-bold text-slate-500 tracking-wide">{t('projectKnowledge.aiSearchEnabledLabel')}</span>
            <div className="flex items-baseline gap-2 mt-2">
              <span className="text-3xl font-black text-emerald-600">{activeDocsCount}</span>
              <span className="text-xs text-slate-400">{t('projectKnowledge.readyDocsLabel')}</span>
            </div>
            <div className="text-[10px] text-slate-400 mt-2 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-indigo-500 shrink-0" />
              <span>{t('projectKnowledge.aiSearchNotice')}</span>
            </div>
          </div>
        </div>

        {/* Upload Container */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden p-6 space-y-4">
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-2.5 ${
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
              <RefreshCw className="w-10 h-10 text-indigo-500 animate-spin" />
            ) : (
              <UploadCloud className="w-10 h-10 text-slate-400" />
            )}
            <div className="space-y-1">
              <div className="text-sm font-bold text-slate-700">
                {isUploadingDocument ? t('projectKnowledge.uploadingText') : t('projectKnowledge.dragDropNotice')}
              </div>
              <div className="text-xs text-slate-400">
                {t('projectKnowledge.supportedFormats')}
              </div>
            </div>
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 text-xs font-semibold rounded-xl flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-500" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Documents Table */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
            <span className="text-xs font-bold text-slate-700 tracking-wide">{t('projectKnowledge.uploadedListTitle')}</span>
            <span className="text-[10px] text-slate-400">{t('projectKnowledge.totalDocsCount', { count: projectDocuments.length })}</span>
          </div>

          {projectDocuments.length === 0 ? (
            <div className="p-12 text-center text-slate-400 space-y-2">
              <File className="w-8 h-8 mx-auto text-slate-300" />
              <div className="text-xs font-bold">{t('projectKnowledge.status.unready')}</div>
              <div className="text-[10px] max-w-xs mx-auto leading-normal">
                {t('projectKnowledge.pageSubtitle')}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 font-bold uppercase tracking-wider text-[10px] bg-slate-50/20">
                    <th className="py-3 px-6">{t('projectKnowledge.tableHeader.file')}</th>
                    <th className="py-3 px-4">{t('projectKnowledge.tableHeader.status')}</th>
                    <th className="py-3 px-4">{t('projectKnowledge.tableHeader.size')}</th>
                    <th className="py-3 px-4">{t('projectKnowledge.tableHeader.uploadedTime')}</th>
                    <th className="py-3 px-4 text-center">{t('projectKnowledge.tableHeader.joinAI')}</th>
                    <th className="py-3 px-6 text-right">{t('projectKnowledge.tableHeader.actions')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {projectDocuments.map((doc) => {
                    const isReady = doc.status === 'ready';
                    const isProcessing = doc.status === 'uploaded' || doc.status === 'converting';
                    const isFailed = doc.status === 'failed';

                    return (
                      <tr key={doc.public_id} className="hover:bg-slate-50/80 transition-colors">
                        {/* Filename */}
                        <td className="py-4 px-6 flex items-center gap-3 overflow-hidden min-w-[200px]">
                          <File className="w-4 h-4 text-slate-400 shrink-0" />
                          <div className="overflow-hidden">
                            <div className="font-semibold text-slate-700 truncate" title={doc.original_filename}>
                              {doc.original_filename}
                            </div>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="py-4 px-4 whitespace-nowrap">
                          {isReady && (
                            <span className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 font-bold border border-emerald-100 px-2.5 py-0.5 rounded-lg text-[10px]">
                              <CheckCircle className="w-3 h-3 text-emerald-600" />
                              {t('projectKnowledge.status.ready')}
                            </span>
                          )}

                          {isProcessing && (
                            <span className="inline-flex items-center gap-1.5 bg-amber-50 text-amber-700 font-bold border border-amber-100 px-2.5 py-0.5 rounded-lg text-[10px] animate-pulse">
                              <Clock className="w-3 h-3 text-amber-500 animate-spin" />
                              {t('projectKnowledge.status.converting')}
                            </span>
                          )}

                          {isFailed && (
                            <span 
                              className="inline-flex items-center gap-1.5 bg-rose-50 text-rose-700 font-bold border border-rose-100 px-2.5 py-0.5 rounded-lg text-[10px] cursor-help"
                              title={doc.error_message || t('projectKnowledge.status.failedTooltip')}
                            >
                              <XCircle className="w-3 h-3 text-rose-500" />
                              {t('projectKnowledge.status.failed')}
                            </span>
                          )}
                        </td>

                        {/* Size */}
                        <td className="py-4 px-4 text-slate-500 font-medium whitespace-nowrap">
                          {formatBytes(doc.file_size)}
                        </td>

                        {/* Date */}
                        <td className="py-4 px-4 text-slate-400 font-medium whitespace-nowrap">
                          {formatDate(doc.created_at)}
                        </td>

                        {/* Toggle AI Retrieval */}
                        <td className="py-4 px-4 text-center">
                          {isReady ? (
                            <button
                              type="button"
                              onClick={() => void toggleDocumentAI(doc.public_id, !doc.ai_enabled)}
                              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none ${
                                doc.ai_enabled ? 'bg-indigo-600' : 'bg-slate-200'
                              }`}
                            >
                              <span
                                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                  doc.ai_enabled ? 'translate-x-4' : 'translate-x-0'
                                }`}
                              />
                            </button>
                          ) : (
                            <span className="text-[10px] text-slate-300">{t('projectKnowledge.status.unready')}</span>
                          )}
                        </td>

                        {/* Action buttons */}
                        <td className="py-4 px-6 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            {isFailed && (
                              <button
                                type="button"
                                onClick={() => void retryProjectDocument(doc.public_id)}
                                className="p-1.5 hover:bg-slate-100 text-slate-400 hover:text-indigo-600 rounded-lg transition-colors"
                                title={t('projectKnowledge.actionTooltip.retry')}
                              >
                                <RefreshCw className="w-4 h-4" />
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => confirmDelete(doc.public_id, doc.original_filename)}
                              className="p-1.5 hover:bg-slate-100 text-slate-400 hover:text-rose-600 rounded-lg transition-colors"
                              title={t('projectKnowledge.actionTooltip.delete')}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>

      {/* Delete Confirmation Modal */}
      {deleteTargetId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-2xl max-w-sm w-full space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex gap-3 items-start">
              <div className="p-2.5 bg-rose-50 rounded-2xl border border-rose-100 text-rose-600 shrink-0">
                <Trash2 className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-black text-slate-800">{t('projectKnowledge.deleteModal.title')}</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('projectKnowledge.deleteModal.confirmPrefix')} <span className="font-semibold text-slate-700">"{deleteTargetName}"</span> {t('projectKnowledge.deleteModal.confirmSuffix')}
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => {
                  setDeleteTargetId(null);
                  setDeleteTargetName(null);
                }}
                className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 hover:bg-slate-100 transition-colors"
              >
                {t('projectKnowledge.deleteModal.cancelBtn')}
              </button>
              <button
                type="button"
                onClick={handleDelete}
                className="px-4 py-2 bg-rose-650 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 shadow-md shadow-rose-100 transition-colors"
              >
                {t('projectKnowledge.deleteModal.confirmBtn')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
