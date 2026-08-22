import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitCommitHorizontal, X } from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import { CommitDetail } from '@/core/versionControl';
import { useModalDialog } from '@/lib/useModalDialog';

/**
 * 历史版本只读查看弹窗（Phase F）。
 *
 * 打开时通过 getCommitDetail 拉取该提交的完整规范化 state，按对象类型分区只读渲染。
 * 只读快照直接消费后端 state 结构（键为 logical_uuid），不接入当前 IR。
 */

interface CommitDetailDialogProps {
  projectId: string;
  commitRef: string | null;
  open: boolean;
  onClose: () => void;
}

const SECTIONS: { key: string; labelKey: string }[] = [
  { key: 'project_metadata', labelKey: 'versionControl.diff.entityType.project_metadata' },
  { key: 'actors', labelKey: 'versionControl.diff.entityType.actor' },
  { key: 'features', labelKey: 'versionControl.diff.entityType.feature' },
  { key: 'feature_relations', labelKey: 'versionControl.diff.entityType.feature_relation' },
  { key: 'scenarios', labelKey: 'versionControl.diff.entityType.scenario' },
  { key: 'business_objects', labelKey: 'versionControl.diff.entityType.business_object' },
  { key: 'flows', labelKey: 'versionControl.diff.entityType.flow' },
  { key: 'scopes', labelKey: 'versionControl.diff.entityType.scope' },
];

const KNOWN_SPECIAL_KEYS = new Set([
  'name',
  'title',
  'description',
  'content',
  'logical_uuid',
  'acceptance_criteria',
  'steps',
  'attributes',
  'parent_feature_logical_uuid',
  'child_feature_logical_uuid',
  'parent_logical_uuid',
  'child_logical_uuid',
  'position',
  'status',
  'scope_status',
  'confirmation_status',
  'reason',
  'positive_summary',
  'negative_summary',
  'user_requirements',
  'kano_status',
  'unlocked_stages',
  'actor_logical_uuids',
  'feature_logical_uuids',
  'feature_logical_uuid',
  'actor_logical_uuid',
  'kano_category',
  'kano_category_name',
  'input_business_object_logical_uuids',
  'output_business_object_logical_uuids',
  'next_step_logical_uuids',
]);

function itemMatchesQuery(item: Record<string, any>, query: string): boolean {
  if (!query.trim()) return true;
  const q = query.trim().toLowerCase();
  try {
    return JSON.stringify(item).toLowerCase().includes(q);
  } catch {
    return false;
  }
}

export function CommitDetailDialog({ projectId, commitRef, open, onClose }: CommitDetailDialogProps) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<CommitDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const currentDetailReqId = useRef(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalDialog(open, onClose, dialogRef);

  const load = useCallback(() => {
    if (!open || !commitRef) return;
    const reqId = ++currentDetailReqId.current;
    setLoading(true);
    setError(null);
    setDetail(null);
    workspaceApi.getCommitDetail(projectId, commitRef)
      .then((d) => {
        if (currentDetailReqId.current === reqId) {
          setDetail(d);
        }
      })
      .catch((e) => {
        if (currentDetailReqId.current === reqId) {
          setError(e instanceof Error ? e.message : 'versionControl.errors.loadCommitDetailFailed');
        }
      })
      .finally(() => {
        if (currentDetailReqId.current === reqId) {
          setLoading(false);
        }
      });
  }, [projectId, commitRef, open]);

  useEffect(() => { load(); }, [load]);

  if (!open) return null;

  const state = detail?.state as Record<string, unknown> | undefined;

  return (
    <div ref={dialogRef} className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true" aria-label={t('versionControl.commitDetail.title')}>
      <div className="flex h-[85vh] w-full max-w-3xl flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <GitCommitHorizontal className="h-5 w-5 text-indigo-600 shrink-0" />
          <h2 className="text-base font-bold text-slate-800">{t('versionControl.commitDetail.title')}</h2>
          {detail && (
            <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-500">{detail.short_id}</span>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label={t('versionControl.commitDetail.close')}
            className="ml-auto rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Commit Meta Banner */}
        {detail && (
          <div className="border-b border-slate-100 bg-slate-50/70 px-5 py-3 text-xs text-slate-600 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="font-semibold text-slate-800 text-sm">{detail.message}</p>
              <p className="text-slate-500 mt-0.5">
                {detail.author_email || detail.author_user_id || '-'} · {new Date(detail.created_at).toLocaleString()}
              </p>
            </div>
            {detail.branch_names.length > 0 && (
              <div className="flex items-center gap-1">
                {detail.branch_names.map((b) => (
                  <span key={b} className="rounded bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700 text-[11px]">{b}</span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Search Bar */}
        <div className="border-b border-slate-100 px-5 py-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('versionControl.commitDetail.searchPlaceholder', '在当前提交快照中搜索对象...')}
            className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:outline-hidden"
          />
        </div>

        {/* Content Body */}
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {loading && <p className="text-sm text-slate-400">{t('shell.loading')}</p>}
          {error && (
            <div className="p-6 text-center">
              <p className="text-sm text-rose-600">{error}</p>
              <button type="button" onClick={load} className="mt-2 text-xs font-semibold text-indigo-600 hover:underline cursor-pointer">
                {t('shell.retry', '重试')}
              </button>
            </div>
          )}
          {!loading && !error && (!state || Object.keys(state).length === 0) && (
            <p className="text-sm text-slate-400">{t('versionControl.commitDetail.empty')}</p>
          )}
          {!loading && !error && state && (
            <div className="space-y-6">
              {SECTIONS.map((section) => {
                const rawVal = state[section.key];
                const rawItems = Array.isArray(rawVal)
                  ? rawVal
                  : (rawVal && typeof rawVal === 'object'
                    ? (section.key === 'project_metadata' ? [rawVal] : Object.values(rawVal))
                    : []);
                const items = (rawItems as Array<Record<string, any>>).filter((item) => itemMatchesQuery(item, searchQuery));

                if (items.length === 0) return null;

                return (
                  <div key={section.key}>
                    <p className="mb-2 border-b border-slate-100 pb-1 text-xs font-bold text-slate-700 flex items-center justify-between">
                      <span>{t(section.labelKey)}</span>
                      <span className="text-[11px] font-normal text-slate-400">{items.length} {t('versionControl.commitDetail.items', '项')}</span>
                    </p>
                    <div className="grid grid-cols-1 gap-2">
                      {items.map((item, itemIdx) => {
                        const isProjectMeta = section.key === 'project_metadata';
                        const isFeatureRel = section.key === 'feature_relations';
                        const isScope = section.key === 'scopes';

                        const name = isProjectMeta
                          ? 'Project Metadata'
                          : isFeatureRel
                          ? `Relation: ${(item.parent_feature_logical_uuid || item.parent_logical_uuid || '').slice(0, 8)} → ${(item.child_feature_logical_uuid || item.child_logical_uuid || '').slice(0, 8)}`
                          : isScope
                          ? `Scope (${item.status || item.scope_status || 'current'})`
                          : String(item.name || item.title || item.logical_uuid || `Item #${itemIdx + 1}`);

                        const desc = String(item.description || item.content || item.reason || '');
                        const uuid = String(item.logical_uuid ?? itemIdx);

                        // Collect unspecialized extra properties
                        const extraEntries = Object.entries(item).filter(([k]) => !KNOWN_SPECIAL_KEYS.has(k));

                        return (
                          <div key={uuid} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-xs">
                            <div className="flex items-center justify-between">
                              <p className="font-semibold text-slate-800">{name}</p>
                              {item.confirmation_status && (
                                <span className="rounded bg-slate-200/60 px-1.5 py-0.5 text-[10px] text-slate-600">
                                  {String(item.confirmation_status)}
                                </span>
                              )}
                              {(item.status || item.scope_status) && isScope && (
                                <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700">
                                  {String(item.status || item.scope_status)}
                                </span>
                              )}
                            </div>

                            {/* Project Metadata Section */}
                            {isProjectMeta && (
                              <div className="mt-1.5 space-y-1 text-slate-600">
                                {item.user_requirements && (
                                  <p className="text-[11px] leading-relaxed">
                                    <span className="font-semibold text-slate-700">Requirements:</span> {String(item.user_requirements)}
                                  </p>
                                )}
                                {item.kano_status && (
                                  <p className="text-[10px] text-slate-500">
                                    <span className="font-semibold text-slate-700">Kano Status:</span> {String(item.kano_status)}
                                  </p>
                                )}
                                {item.unlocked_stages && (
                                  <p className="text-[10px] text-slate-500">
                                    <span className="font-semibold text-slate-700">Unlocked Stages:</span> {String(item.unlocked_stages)}
                                  </p>
                                )}
                              </div>
                            )}

                            {desc && <p className="mt-1 text-slate-600 leading-relaxed text-[11px]">{desc}</p>}

                            {/* Scope summary */}
                            {isScope && (item.positive_summary || item.negative_summary) && (
                              <div className="mt-1.5 space-y-0.5 border-t border-slate-100 pt-1 text-[10px] text-slate-500">
                                {item.positive_summary && <p className="text-emerald-700">+ {item.positive_summary}</p>}
                                {item.negative_summary && <p className="text-rose-700">- {item.negative_summary}</p>}
                              </div>
                            )}

                            {/* Feature Relation Detail */}
                            {isFeatureRel && (
                              <div className="mt-1.5 text-[10px] text-slate-500 font-mono">
                                <span>Parent: {item.parent_feature_logical_uuid || item.parent_logical_uuid || '-'}</span>
                                <span className="mx-2">→</span>
                                <span>Child: {item.child_feature_logical_uuid || item.child_logical_uuid || '-'}</span>
                                {item.position !== undefined && <span className="ml-2 font-sans font-semibold text-slate-600">(Position: {item.position})</span>}
                              </div>
                            )}

                            {/* Linked Actors on Features */}
                            {item.actor_logical_uuids && Array.isArray(item.actor_logical_uuids) && item.actor_logical_uuids.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1 text-[10px] text-slate-500">
                                <span className="font-semibold text-slate-600">Actors:</span>
                                {item.actor_logical_uuids.map((aid: string) => (
                                  <span key={aid} className="font-mono bg-white px-1 rounded border border-slate-200">{aid.slice(0, 8)}</span>
                                ))}
                              </div>
                            )}

                            {/* Linked Features on Flows */}
                            {item.feature_logical_uuids && Array.isArray(item.feature_logical_uuids) && item.feature_logical_uuids.length > 0 && (
                              <div className="mt-1.5 flex flex-wrap gap-1 text-[10px] text-slate-500">
                                <span className="font-semibold text-slate-600">Features:</span>
                                {item.feature_logical_uuids.map((fid: string) => (
                                  <span key={fid} className="font-mono bg-white px-1 rounded border border-slate-200">{fid.slice(0, 8)}</span>
                                ))}
                              </div>
                            )}

                            {/* Scenario Relations */}
                            {(item.feature_logical_uuid || item.actor_logical_uuid) && (
                              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                                {item.feature_logical_uuid && (
                                  <span>
                                    <span className="font-semibold text-slate-600">Feature:</span>{' '}
                                    <span className="font-mono bg-white px-1 rounded border border-slate-200">{String(item.feature_logical_uuid).slice(0, 8)}</span>
                                  </span>
                                )}
                                {item.actor_logical_uuid && (
                                  <span>
                                    <span className="font-semibold text-slate-600">Actor:</span>{' '}
                                    <span className="font-mono bg-white px-1 rounded border border-slate-200">{String(item.actor_logical_uuid).slice(0, 8)}</span>
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Scope Relations & Kano */}
                            {(item.feature_logical_uuid || item.kano_category || item.kano_category_name) && isScope && (
                              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                                {item.feature_logical_uuid && (
                                  <span>
                                    <span className="font-semibold text-slate-600">Feature:</span>{' '}
                                    <span className="font-mono bg-white px-1 rounded border border-slate-200">{String(item.feature_logical_uuid).slice(0, 8)}</span>
                                  </span>
                                )}
                                {(item.kano_category || item.kano_category_name) && (
                                  <span>
                                    <span className="font-semibold text-slate-600">Kano:</span> {item.kano_category_name || item.kano_category}
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Acceptance Criteria */}
                            {item.acceptance_criteria && Array.isArray(item.acceptance_criteria) && item.acceptance_criteria.length > 0 && (
                              <div className="mt-2 space-y-0.5 border-t border-slate-100 pt-1.5 text-[10px] text-slate-500">
                                <p className="font-semibold text-slate-600">{t('versionControl.diff.ac', '验收标准')}:</p>
                                {item.acceptance_criteria.map((ac: any, idx: number) => (
                                  <p key={idx}>• {typeof ac === 'string' ? ac : ac.content || ac.name}</p>
                                ))}
                              </div>
                            )}

                            {/* Steps with detailed actor and IO bo links */}
                            {item.steps && Array.isArray(item.steps) && item.steps.length > 0 && (
                              <div className="mt-2 space-y-1.5 border-t border-slate-100 pt-1.5 text-[10px] text-slate-500">
                                <p className="font-semibold text-slate-600">{t('versionControl.diff.steps', '步骤序列')}:</p>
                                {item.steps.map((st: any, idx: number) => {
                                  const stepActors = Array.isArray(st.actor_logical_uuids) ? st.actor_logical_uuids : [];
                                  const stepInputs = Array.isArray(st.input_business_object_logical_uuids) ? st.input_business_object_logical_uuids : [];
                                  const stepOutputs = Array.isArray(st.output_business_object_logical_uuids) ? st.output_business_object_logical_uuids : [];
                                  const nextSteps = Array.isArray(st.next_step_logical_uuids) ? st.next_step_logical_uuids : [];
                                  return (
                                    <div key={idx} className="rounded bg-white/70 p-1.5 border border-slate-100">
                                      <p className="font-medium text-slate-700">
                                        {st.position !== undefined ? st.position + 1 : idx + 1}. {typeof st === 'string' ? st : st.name || st.content || st.logical_uuid}
                                        {st.step_type ? <span className="ml-1 text-[9px] text-indigo-600 bg-indigo-50 px-1 rounded">[{st.step_type}]</span> : ''}
                                      </p>
                                      {st.description && <p className="text-[10px] text-slate-500 mt-0.5">{st.description}</p>}
                                      {(stepActors.length > 0 || stepInputs.length > 0 || stepOutputs.length > 0 || nextSteps.length > 0) && (
                                        <div className="mt-1 flex flex-wrap gap-2 text-[9px] text-slate-400">
                                          {stepActors.length > 0 && (
                                            <span>Actors: {stepActors.map((a: string) => a.slice(0, 8)).join(', ')}</span>
                                          )}
                                          {stepInputs.length > 0 && (
                                            <span>Inputs: {stepInputs.map((b: string) => b.slice(0, 8)).join(', ')}</span>
                                          )}
                                          {stepOutputs.length > 0 && (
                                            <span>Outputs: {stepOutputs.map((b: string) => b.slice(0, 8)).join(', ')}</span>
                                          )}
                                          {nextSteps.length > 0 && (
                                            <span>Next: {nextSteps.map((n: string) => n.slice(0, 8)).join(', ')}</span>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Attributes */}
                            {item.attributes && Array.isArray(item.attributes) && item.attributes.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1 border-t border-slate-100 pt-1.5 text-[10px]">
                                {item.attributes.map((attr: any, idx: number) => (
                                  <span key={idx} className="rounded bg-white px-1.5 py-0.5 text-slate-600 border border-slate-200/60" title={attr.description || attr.example || ''}>
                                    {typeof attr === 'string' ? attr : `${attr.name || attr.key}: ${attr.data_type || attr.type || ''}`}
                                    {attr.example ? <span className="text-slate-400 font-mono text-[9px]"> ({attr.example})</span> : ''}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Generic recursive display for unspecialized / extension keys */}
                            {extraEntries.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5 border-t border-slate-100 pt-1.5 text-[10px] text-slate-500">
                                {extraEntries.map(([k, v]) => (
                                  <span key={k} className="rounded bg-slate-100 px-1.5 py-0.5">
                                    <strong className="text-slate-600">{k}:</strong> {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                  </span>
                                ))}
                              </div>
                            )}

                            {item.logical_uuid && (
                              <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
                                <span className="font-mono">{String(item.logical_uuid).slice(0, 8)}</span>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
