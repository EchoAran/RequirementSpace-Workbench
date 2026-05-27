import { useState } from 'react';
import { Check, RefreshCw, Sparkles, X } from 'lucide-react';

type DraftType = 'project' | 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | 'scope' | null;

interface DraftPreviewModalProps {
  draft: any | null;
  draftType: DraftType;
  isWorking: boolean;
  onConfirm: () => void | Promise<void>;
  onDiscard: () => void | Promise<void>;
  onRegenerate?: (feedback?: string) => void | Promise<void>;
  confirmLabel?: string;
}

const titles: Record<Exclude<DraftType, null>, string> = {
  project: '项目建模草稿',
  actor: '角色草稿',
  feature: '核心能力树草稿',
  flow: '流程与业务对象草稿',
  scenario: '业务场景草稿',
  ac: '验收标准草稿',
  scope: '交付范围草稿',
};

function asArray(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

function getDraftItems(draft: any, draftType: DraftType) {
  if (!draft) return [];
  if (draftType === 'actor') return asArray(draft.actors);
  if (draftType === 'feature') return asArray(draft.features);
  if (draftType === 'flow') return [...asArray(draft.flows), ...asArray(draft.business_objects)];
  if (draftType === 'scenario') return asArray(draft.scenarios);
  if (draftType === 'ac') return asArray(draft.acceptance_criteria || draft.criteria || draft.scenario_acceptance_criteria);
  if (draftType === 'scope') return asArray(draft.scopes);
  if (draftType === 'project') return [draft.project_preview || draft].filter(Boolean);
  return [];
}

function itemTitle(item: any, index: number) {
  return (
    item.name ||
    item.title ||
    item.actor_name ||
    item.feature_name ||
    item.flow_name ||
    item.business_object_name ||
    item.scenario_name ||
    item.criterion_name ||
    item.featureName ||
    item.actorName ||
    item.project_name ||
    `草稿项 ${index + 1}`
  );
}

function itemDescription(item: any) {
  return (
    item.description ||
    item.reason ||
    item.actor_description ||
    item.feature_description ||
    item.flow_description ||
    item.business_object_description ||
    item.scenario_content ||
    item.criterion_content ||
    item.content ||
    item.project_description ||
    ''
  );
}

export function DraftPreviewModal({
  draft,
  draftType,
  isWorking,
  onConfirm,
  onDiscard,
  onRegenerate,
  confirmLabel = '确认采纳',
}: DraftPreviewModalProps) {
  const [feedback, setFeedback] = useState('');

  if (!draft || !draftType) return null;

  const items = getDraftItems(draft, draftType);

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
      <div className="flex max-h-[86vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 bg-slate-50 px-6 py-5">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 rounded-xl bg-amber-100 p-2 text-amber-700">
              <Sparkles className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h3 className="text-base font-extrabold text-slate-900">{titles[draftType]}</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">
                请先预览 AI 生成结果，确认后再合并到当前工作空间。
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void onDiscard()}
            disabled={isWorking}
            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white hover:text-slate-700 disabled:opacity-50"
            title="关闭并舍弃草稿"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500">
              当前草稿没有可展示的条目。
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {items.map((item, index) => (
                <div key={item.id || item.draft_id || index} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-sm font-extrabold text-slate-900">{itemTitle(item, index)}</h4>
                    {(item.scope_status || item.scopeStatus) && (
                      <span className="shrink-0 rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700">
                        {item.scope_status || item.scopeStatus}
                      </span>
                    )}
                  </div>
                  {itemDescription(item) && (
                    <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-slate-600">{itemDescription(item)}</p>
                  )}
                  {(item.positive_summary || item.negative_summary) && (
                    <div className="mt-3 grid gap-2 text-[11px] leading-relaxed text-slate-600 sm:grid-cols-2">
                      {item.positive_summary && (
                        <div className="rounded-lg border border-emerald-100 bg-emerald-50/60 p-2">
                          <div className="mb-1 font-bold text-emerald-700">正方依据</div>
                          {item.positive_summary}
                        </div>
                      )}
                      {item.negative_summary && (
                        <div className="rounded-lg border border-rose-100 bg-rose-50/60 p-2">
                          <div className="mb-1 font-bold text-rose-700">反方依据</div>
                          {item.negative_summary}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="border-t border-slate-100 bg-slate-50 px-6 py-4">
          {onRegenerate && (
            <div className="mb-3 flex flex-col gap-2 sm:flex-row">
              <input
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                disabled={isWorking}
                placeholder="补充调整意见后可重新生成"
                className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              />
              <button
                type="button"
                onClick={async () => {
                  await onRegenerate(feedback || undefined);
                  setFeedback('');
                }}
                disabled={isWorking}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 text-indigo-500 ${isWorking ? 'animate-spin' : ''}`} />
                重新生成
              </button>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => void onDiscard()}
              disabled={isWorking}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-100 disabled:opacity-50"
            >
              舍弃草稿
            </button>
            <button
              type="button"
              onClick={() => void onConfirm()}
              disabled={isWorking}
              className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" />
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
