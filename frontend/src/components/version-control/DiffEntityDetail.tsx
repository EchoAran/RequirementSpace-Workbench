import { useTranslation } from 'react-i18next';
import {
  Users,
  Layers,
  FileText,
  CheckSquare,
  Boxes,
  Tag,
  Workflow,
  ListOrdered,
  Target,
  FolderGit2,
  Network,
  FilePlus2,
  FileMinus2,
  FilePenLine,
  Link2,
  Link2Off,
  ArrowDownUp,
  ExternalLink,
  Sparkles,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';
import { DiffChangeType, DiffEntry, TextDiffBlock } from '@/core/versionControl';
import { jumpTargetForEntity } from '@/core/objectNavigation';
import { getScopeStatusText } from '@/core/presentationLabels';
import { cn } from '@/lib/utils';

// Ignored internal database keys
const IGNORED_SYSTEM_KEYS = new Set([
  'id',
  'project_id',
  'logical_uuid',
  'branch_id',
  'created_at',
  'updated_at',
  'deleted_at',
  'version',
  'node_id',
  'snapshot_id',
  'entity_uuid',
]);

const ENTITY_ICONS: Record<string, typeof Layers> = {
  actor: Users,
  feature: Layers,
  feature_relation: Network,
  scenario: FileText,
  acceptance_criterion: CheckSquare,
  business_object: Boxes,
  business_object_attribute: Tag,
  flow: Workflow,
  flow_step: ListOrdered,
  scope: Target,
  project_metadata: FolderGit2,
};

const CHANGE_TYPE_ICONS: Record<DiffChangeType, typeof FilePlus2> = {
  entity_added: FilePlus2,
  entity_removed: FileMinus2,
  entity_updated: FilePenLine,
  field_changed: FilePenLine,
  relation_added: Link2,
  relation_removed: Link2Off,
  ordered_item_moved: ArrowDownUp,
};

function changeColor(type: DiffChangeType): string {
  switch (type) {
    case 'entity_added':
    case 'relation_added':
      return 'text-emerald-600 bg-emerald-50 border-emerald-200';
    case 'entity_removed':
    case 'relation_removed':
      return 'text-rose-600 bg-rose-50 border-rose-200';
    case 'ordered_item_moved':
      return 'text-amber-600 bg-amber-50 border-amber-200';
    default:
      return 'text-indigo-600 bg-indigo-50 border-indigo-200';
  }
}

function changeBadgeColor(type: DiffChangeType): string {
  switch (type) {
    case 'entity_added':
    case 'relation_added':
      return 'text-emerald-700 bg-emerald-100/80 border-emerald-200';
    case 'entity_removed':
    case 'relation_removed':
      return 'text-rose-700 bg-rose-100/80 border-rose-200';
    case 'ordered_item_moved':
      return 'text-amber-700 bg-amber-100/80 border-amber-200';
    default:
      return 'text-indigo-700 bg-indigo-100/80 border-indigo-200';
  }
}

function jumpLabelKey(entityType: string): string {
  switch (jumpTargetForEntity(entityType)) {
    case '/what': return 'versionControl.diff.jumpToWhat';
    case '/flow': return 'versionControl.diff.jumpToFlow';
    case '/scope': return 'versionControl.diff.jumpToScope';
    default: return 'versionControl.diff.jumpToWhat';
  }
}

function changeLabelKey(type: DiffChangeType): string {
  switch (type) {
    case 'entity_added': return 'versionControl.diff.entityAdded';
    case 'entity_removed': return 'versionControl.diff.entityRemoved';
    case 'entity_updated': return 'versionControl.diff.entityUpdated';
    case 'field_changed': return 'versionControl.diff.fieldChanged';
    case 'relation_added': return 'versionControl.diff.relationAdded';
    case 'relation_removed': return 'versionControl.diff.relationRemoved';
    case 'ordered_item_moved': return 'versionControl.diff.orderedMoved';
    default: return 'versionControl.diff.entityUpdated';
  }
}

function typeLabelKey(entityType: string): string {
  return `versionControl.diff.entityType.${entityType}`;
}

export function formatFieldLabel(key: string, t: (k: string, opts?: any) => string): string {
  const custom = t(`versionControl.diff.fields.${key}`);
  if (custom && custom !== `versionControl.diff.fields.${key}`) {
    return custom;
  }
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Format scope status badge
 */
export function ScopeStatusBadge({ status }: { status: unknown }) {
  const str = String(status || '').toLowerCase();
  const label = getScopeStatusText(status) || String(status || '—');
  let color = 'bg-slate-100 text-slate-700 border-slate-200';
  if (str.includes('in_scope') || str === 'current' || str === 'included') {
    color = 'bg-emerald-100 text-emerald-800 border-emerald-200';
  } else if (str.includes('out_of_scope') || str === 'exclude' || str === 'excluded') {
    color = 'bg-rose-100 text-rose-800 border-rose-200';
  } else if (str.includes('deferred') || str.includes('postponed') || str.includes('determined')) {
    color = 'bg-amber-100 text-amber-800 border-amber-200';
  }
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-bold shadow-xs', color)}>
      {label}
    </span>
  );
}

/**
 * Kano category badge
 */
export function KanoBadge({ category }: { category: unknown }) {
  if (!category) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-purple-200 bg-purple-50 px-2 py-0.5 text-[11px] font-bold text-purple-700 shadow-xs">
      <Sparkles className="h-3 w-3" />
      <span>Kano: {String(category)}</span>
    </span>
  );
}

/**
 * Clean value formatter for individual properties
 */
export function FormattedValue({ field, value, t }: { field?: string; value: unknown; t: (k: string, opts?: any) => string }) {
  if (value === null || value === undefined || value === '') {
    return <span className="italic text-slate-400">—</span>;
  }

  if (field === 'status' || field === 'scope_status') {
    return <ScopeStatusBadge status={value} />;
  }

  if (field === 'kano_category' || field === 'kano_category_name') {
    return <KanoBadge category={value} />;
  }

  if (field === 'confirmation_status') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
        <ShieldCheck className="h-3 w-3 text-slate-500" />
        {String(value)}
      </span>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="italic text-slate-400">{t('versionControl.diff.empty', '无')}</span>;
    }
    // Array of strings or IDs
    if (typeof value[0] === 'string' || typeof value[0] === 'number') {
      return (
        <div className="flex flex-wrap gap-1">
          {value.map((item, idx) => (
            <span
              key={idx}
              className="inline-block rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-700"
            >
              {String(item)}
            </span>
          ))}
        </div>
      );
    }
    // Array of objects (e.g. ACs, attributes, steps)
    return (
      <div className="space-y-1 text-xs">
        {value.map((item, idx) => (
          <div key={idx} className="rounded-lg border border-slate-100 bg-slate-50/70 p-2">
            {typeof item === 'object' && item !== null ? (
              <div className="space-y-0.5">
                {Object.entries(item)
                  .filter(([k]) => !IGNORED_SYSTEM_KEYS.has(k))
                  .map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <span className="text-[10px] font-bold text-slate-500">{formatFieldLabel(k, t)}:</span>
                      <span className="text-slate-800">{String(v ?? '—')}</span>
                    </div>
                  ))}
              </div>
            ) : (
              <span>{String(item)}</span>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).filter(([k]) => !IGNORED_SYSTEM_KEYS.has(k));
    if (entries.length === 0) {
      return <span className="italic text-slate-400">—</span>;
    }
    return (
      <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-2.5 space-y-1 text-xs">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-start gap-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide min-w-[80px] shrink-0 mt-0.5">
              {formatFieldLabel(k, t)}:
            </span>
            <span className="text-slate-700 leading-relaxed break-words">{String(v ?? '—')}</span>
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === 'boolean') {
    return (
      <span className={cn('rounded px-1.5 py-0.5 text-[11px] font-bold', value ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600')}>
        {value ? 'True' : 'False'}
      </span>
    );
  }

  return <span className="whitespace-pre-wrap leading-relaxed break-words text-xs text-slate-700">{String(value)}</span>;
}

/**
 * Structured Entity Card tailored to entity domain types
 */
export function StructuredEntityCard({
  entityType,
  data,
  theme = 'neutral',
}: {
  entityType: string;
  data: Record<string, any>;
  theme?: 'emerald' | 'rose' | 'neutral';
}) {
  const { t } = useTranslation();
  if (!data || typeof data !== 'object') return null;

  const cardBorder =
    theme === 'emerald'
      ? 'border-emerald-200 bg-emerald-50/20'
      : theme === 'rose'
      ? 'border-rose-200 bg-rose-50/20'
      : 'border-slate-200/80 bg-white';

  const title = data.name || data.title || data.content || t(typeLabelKey(entityType));
  const desc = data.description || (data.name ? data.content : '');

  return (
    <div className={cn('rounded-2xl border p-4 space-y-3.5 shadow-xs transition-all', cardBorder)}>
      {/* Title and Badges */}
      <div className="flex items-start justify-between gap-2 border-b border-slate-100/80 pb-3">
        <div>
          <span className="inline-flex items-center gap-1 rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700">
            {t(typeLabelKey(entityType))}
          </span>
          <h4 className="mt-1 text-sm font-black text-slate-900 leading-snug">{title}</h4>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 shrink-0">
          {(data.status || data.scope_status) && <ScopeStatusBadge status={data.status || data.scope_status} />}
          {(data.kano_category || data.kano_category_name) && <KanoBadge category={data.kano_category || data.kano_category_name} />}
          {data.confirmation_status && (
            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
              {String(data.confirmation_status)}
            </span>
          )}
        </div>
      </div>

      {/* Description / Content Body */}
      {desc && desc !== title && (
        <div className="space-y-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {t('versionControl.diff.fields.description', '描述说明')}
          </div>
          <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap rounded-xl bg-slate-50/70 p-3 border border-slate-100/80">
            {desc}
          </p>
        </div>
      )}

      {/* Actor specifics */}
      {entityType === 'actor' && data.duties && (
        <div className="space-y-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">职责范围</div>
          <p className="text-xs text-slate-700 leading-relaxed bg-slate-50/70 p-2.5 rounded-xl border border-slate-100">
            {String(data.duties)}
          </p>
        </div>
      )}

      {/* Feature specifics */}
      {entityType === 'feature' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          {data.parent_name && (
            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
              <span className="text-[10px] font-bold text-slate-400 block mb-0.5">上级功能</span>
              <span className="font-semibold text-slate-800">{data.parent_name}</span>
            </div>
          )}
          {data.actors && Array.isArray(data.actors) && data.actors.length > 0 && (
            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5 md:col-span-2">
              <span className="text-[10px] font-bold text-slate-400 block mb-1">关联参与者</span>
              <div className="flex flex-wrap gap-1.5">
                {data.actors.map((actor: any, i: number) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded-md border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                    <Users className="h-3 w-3" />
                    {typeof actor === 'string' ? actor : actor.name || actor.actor_name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Scenario specifics */}
      {entityType === 'scenario' && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {data.feature_name && (
              <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
                <span className="text-[10px] font-bold text-slate-400 block mb-0.5">所属功能</span>
                <span className="font-semibold text-slate-800">{data.feature_name}</span>
              </div>
            )}
            {data.actor_name && (
              <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
                <span className="text-[10px] font-bold text-slate-400 block mb-0.5">执行角色</span>
                <span className="font-semibold text-slate-800">{data.actor_name}</span>
              </div>
            )}
          </div>

          {Array.isArray(data.acceptance_criteria) && data.acceptance_criteria.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                {t('versionControl.diff.ac', '验收标准')} ({data.acceptance_criteria.length})
              </div>
              <div className="space-y-1.5">
                {data.acceptance_criteria.map((ac: any, i: number) => (
                  <div key={i} className="flex items-start gap-2 rounded-xl border border-slate-100 bg-slate-50/60 p-2.5 text-xs">
                    <CheckSquare className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
                    <span className="text-slate-700 leading-relaxed">
                      {typeof ac === 'string' ? ac : ac.content || ac.name || JSON.stringify(ac)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Acceptance Criterion specifics */}
      {entityType === 'acceptance_criterion' && data.scenario_name && (
        <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5 text-xs">
          <span className="text-[10px] font-bold text-slate-400 block mb-0.5">所属场景</span>
          <span className="font-semibold text-slate-800">{data.scenario_name}</span>
        </div>
      )}

      {/* Business Object specifics: Attributes Table */}
      {entityType === 'business_object' && Array.isArray(data.attributes) && (
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {t('versionControl.diff.fields.attributes', '属性清单')} ({data.attributes.length})
          </div>
          {data.attributes.length === 0 ? (
            <p className="text-xs italic text-slate-400">{t('versionControl.diff.noAttributes', '暂无属性定义')}</p>
          ) : (
            <div className="overflow-hidden rounded-xl border border-slate-150 shadow-2xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-50/90 border-b border-slate-150 text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  <tr>
                    <th className="px-3 py-2">属性名称</th>
                    <th className="px-3 py-2">数据类型</th>
                    <th className="px-3 py-2">业务说明</th>
                    <th className="px-3 py-2">示例值</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {data.attributes.map((attr: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-3 py-2 font-bold text-slate-800 whitespace-nowrap">{attr.name || '—'}</td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className="rounded-md border border-indigo-100 bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700">
                          {attr.data_type || 'String'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-600 max-w-[200px] leading-snug">{attr.description || '—'}</td>
                      <td className="px-3 py-2 text-slate-500 font-mono text-[11px]">{attr.example ? String(attr.example) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Business Object Attribute specifics */}
      {entityType === 'business_object_attribute' && (
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
            <span className="text-[10px] font-bold text-slate-400 block mb-0.5">数据类型</span>
            <span className="rounded-md border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-700 inline-block">
              {data.data_type || 'String'}
            </span>
          </div>
          <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
            <span className="text-[10px] font-bold text-slate-400 block mb-0.5">示例值</span>
            <span className="font-mono text-xs text-slate-700">{data.example ? String(data.example) : '—'}</span>
          </div>
        </div>
      )}

      {/* Flow specifics: Steps timeline */}
      {entityType === 'flow' && Array.isArray(data.steps) && (
        <div className="space-y-2">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {t('versionControl.diff.steps', '步骤序列')} ({data.steps.length})
          </div>
          {data.steps.length === 0 ? (
            <p className="text-xs italic text-slate-400">{t('versionControl.diff.noSteps', '暂无步骤定义')}</p>
          ) : (
            <div className="space-y-2">
              {data.steps.map((st: any, i: number) => (
                <div key={i} className="rounded-xl border border-slate-150 bg-white p-3 shadow-2xs space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-black text-white shrink-0">
                        {st.position ?? i + 1}
                      </span>
                      <span className="font-bold text-slate-800 text-xs">{st.name || `步骤 ${i + 1}`}</span>
                    </div>
                    {st.step_type && (
                      <span className="rounded-md border border-slate-200 bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
                        {st.step_type}
                      </span>
                    )}
                  </div>
                  {st.description && <p className="text-xs text-slate-600 leading-relaxed pl-7">{st.description}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Flow Step specifics */}
      {entityType === 'flow_step' && (
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
            <span className="text-[10px] font-bold text-slate-400 block mb-0.5">步骤顺序</span>
            <span className="font-bold text-indigo-600">第 {data.position ?? 1} 步</span>
          </div>
          <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
            <span className="text-[10px] font-bold text-slate-400 block mb-0.5">步骤类型</span>
            <span className="font-semibold text-slate-700">{data.step_type || '常规步骤'}</span>
          </div>
        </div>
      )}

      {/* Scope specifics */}
      {entityType === 'scope' && (
        <div className="space-y-2 text-xs">
          {data.positive_summary && (
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 block mb-0.5">
                {t('versionControl.diff.fields.positive_summary', '纳入理由')}
              </span>
              <p className="text-emerald-900 leading-relaxed">{data.positive_summary}</p>
            </div>
          )}
          {data.negative_summary && (
            <div className="rounded-xl border border-rose-100 bg-rose-50/60 p-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700 block mb-0.5">
                {t('versionControl.diff.fields.negative_summary', '排除影响')}
              </span>
              <p className="text-rose-900 leading-relaxed">{data.negative_summary}</p>
            </div>
          )}
          {data.reason && (
            <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-0.5">
                {t('versionControl.diff.fields.reason', '决策依据')}
              </span>
              <p className="text-slate-700 leading-relaxed">{data.reason}</p>
            </div>
          )}
        </div>
      )}

      {/* Project Metadata specifics */}
      {entityType === 'project_metadata' && data.user_requirements && (
        <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 text-xs">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
            {t('versionControl.diff.fields.user_requirements', '用户诉求')}
          </span>
          <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">{data.user_requirements}</p>
        </div>
      )}

      {/* Remaining custom extra properties */}
      {(() => {
        const standardKeys = new Set([
          'name', 'title', 'description', 'content', 'duties', 'status', 'scope_status',
          'kano_category', 'kano_category_name', 'confirmation_status', 'parent_name',
          'actors', 'actor_name', 'feature_name', 'scenario_name', 'acceptance_criteria',
          'attributes', 'steps', 'position', 'step_type', 'positive_summary', 'negative_summary',
          'reason', 'user_requirements', 'data_type', 'example', ...IGNORED_SYSTEM_KEYS,
        ]);
        const extras = Object.entries(data).filter(([k]) => !standardKeys.has(k));
        if (extras.length === 0) return null;
        return (
          <div className="pt-2 border-t border-slate-100 space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">其他属性</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              {extras.map(([k, v]) => (
                <div key={k} className="rounded-xl border border-slate-100 bg-slate-50/50 p-2.5">
                  <span className="text-[10px] font-bold text-slate-400 block mb-0.5">{formatFieldLabel(k, t)}</span>
                  <FormattedValue field={k} value={v} t={t} />
                </div>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

/**
 * Main DiffEntityDetail Component for Version Control Diff view
 */
export function DiffEntityDetail({
  entry,
  onJump,
}: {
  entry: DiffEntry;
  onJump?: (entry: DiffEntry) => void;
}) {
  const { t } = useTranslation();

  const EntityIcon = ENTITY_ICONS[entry.entity_type] || Layers;
  const ChangeIcon = CHANGE_TYPE_ICONS[entry.change_type] || FilePenLine;

  const before = entry.before;
  const after = entry.after;

  const isBeforeObject = before !== null && typeof before === 'object';
  const isAfterObject = after !== null && typeof after === 'object';

  // Compute changed keys when both before and after are objects in an entity_updated
  const changedKeyDiffs = (() => {
    if (!isBeforeObject || !isAfterObject) return [];
    const b = before as Record<string, any>;
    const a = after as Record<string, any>;
    const allKeys = Array.from(new Set([...Object.keys(b), ...Object.keys(a)])).filter(
      (k) => !IGNORED_SYSTEM_KEYS.has(k)
    );
    const diffs: { key: string; beforeVal: any; afterVal: any }[] = [];
    for (const key of allKeys) {
      const bv = b[key];
      const av = a[key];
      if (JSON.stringify(bv) !== JSON.stringify(av)) {
        diffs.push({ key, beforeVal: bv, afterVal: av });
      }
    }
    return diffs;
  })();

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div className="flex items-center gap-3">
          <div className={cn('flex h-10 w-10 items-center justify-center rounded-2xl border shadow-xs shrink-0', changeColor(entry.change_type))}>
            <ChangeIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={cn('rounded-full border px-2.5 py-0.5 text-xs font-bold shadow-2xs', changeBadgeColor(entry.change_type))}>
                {t(changeLabelKey(entry.change_type))}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-600 shadow-2xs">
                <EntityIcon className="h-3 w-3" />
                {t(typeLabelKey(entry.entity_type))}
              </span>
            </div>
            <h3 className="mt-1 text-base font-black text-slate-900 tracking-tight">
              {entry.entity_name || entry.entity_uuid}
            </h3>
          </div>
        </div>

        {onJump && jumpTargetForEntity(entry.entity_type) && (
          <button
            type="button"
            onClick={() => onJump(entry)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50/80 px-3.5 py-2 text-xs font-bold text-indigo-700 hover:bg-indigo-100 active:scale-95 transition-all shadow-xs cursor-pointer"
          >
            <span>{t(jumpLabelKey(entry.entity_type))}</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Relations Added/Removed Presentation */}
      {(entry.change_type === 'relation_added' || entry.change_type === 'relation_removed') && (
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs space-y-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {t('versionControl.diff.relation', '关联关系')}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <div className="rounded-xl border border-slate-150 bg-slate-50 px-3.5 py-2.5 font-bold text-slate-800 shadow-2xs">
              {entry.entity_name || entry.entity_uuid}
            </div>
            <div className="flex items-center gap-1 text-indigo-600 font-bold">
              <span className="rounded-full bg-indigo-50 border border-indigo-100 px-2.5 py-1 text-[11px]">
                {entry.relation_type || entry.path || '关联'}
              </span>
              <ArrowRight className="h-4 w-4" />
            </div>
            <div className="rounded-xl border border-slate-150 bg-slate-50 px-3.5 py-2.5 font-bold text-slate-800 shadow-2xs">
              {entry.related_entity_name || entry.related_entity_uuid || '—'}
            </div>
          </div>
        </div>
      )}

      {/* Ordered Item Moved Presentation */}
      {entry.change_type === 'ordered_item_moved' && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4 text-xs text-amber-900 shadow-xs space-y-2">
          <div className="text-[10px] font-bold uppercase tracking-wider text-amber-700">
            {t('versionControl.diff.orderedMoved', '顺序调整')}
          </div>
          {entry.before_position !== undefined && entry.after_position !== undefined ? (
            <div className="flex items-center gap-3">
              <span className="rounded-xl border border-amber-200 bg-white px-3 py-1.5 font-black text-amber-800 text-sm shadow-2xs">
                第 #{entry.before_position} 位
              </span>
              <ArrowRight className="h-4 w-4 text-amber-600" />
              <span className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-1.5 font-black text-emerald-700 text-sm shadow-2xs">
                第 #{entry.after_position} 位
              </span>
            </div>
          ) : (
            <p className="font-semibold">{t('versionControl.diff.orderedMoved')}</p>
          )}
        </div>
      )}

      {/* Specific Field Modification (field_changed) */}
      {entry.change_type === 'field_changed' && (
        <div className="space-y-3">
          {entry.field && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-500">{t('versionControl.diff.fieldName', '字段')}:</span>
              <span className="rounded-lg border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 shadow-2xs">
                {formatFieldLabel(entry.field, t)} ({entry.field})
              </span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {/* Before */}
            <div className="rounded-2xl border border-rose-200/80 bg-rose-50/40 p-4 shadow-xs space-y-2">
              <div className="flex items-center justify-between border-b border-rose-100 pb-2">
                <span className="text-[10px] font-black uppercase tracking-wider text-rose-600">
                  {t('versionControl.diff.fieldBefore', '修改前')}
                </span>
                <span className="h-2 w-2 rounded-full bg-rose-500" />
              </div>
              <div className="pt-1">
                <FormattedValue field={entry.field ?? undefined} value={before} t={t} />
              </div>
            </div>

            {/* After */}
            <div className="rounded-2xl border border-emerald-200/80 bg-emerald-50/40 p-4 shadow-xs space-y-2">
              <div className="flex items-center justify-between border-b border-emerald-100 pb-2">
                <span className="text-[10px] font-black uppercase tracking-wider text-emerald-600">
                  {t('versionControl.diff.fieldAfter', '修改后')}
                </span>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
              </div>
              <div className="pt-1">
                <FormattedValue field={entry.field ?? undefined} value={after} t={t} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Entity Added */}
      {entry.change_type === 'entity_added' && (
        <div className="space-y-3">
          <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700">
            <Sparkles className="h-4 w-4" />
            <span>新增完整对象详情</span>
          </div>
          {isAfterObject ? (
            <StructuredEntityCard entityType={entry.entity_type} data={after as Record<string, any>} theme="emerald" />
          ) : (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4 text-xs">
              <FormattedValue value={after} t={t} />
            </div>
          )}
        </div>
      )}

      {/* Entity Removed */}
      {entry.change_type === 'entity_removed' && (
        <div className="space-y-3">
          <div className="flex items-center gap-1.5 text-xs font-bold text-rose-700">
            <FileMinus2 className="h-4 w-4" />
            <span>已删除对象详情快照</span>
          </div>
          {isBeforeObject ? (
            <StructuredEntityCard entityType={entry.entity_type} data={before as Record<string, any>} theme="rose" />
          ) : (
            <div className="rounded-2xl border border-rose-200 bg-rose-50/40 p-4 text-xs">
              <FormattedValue value={before} t={t} />
            </div>
          )}
        </div>
      )}

      {/* Entity Updated with Changed Fields Breakdown */}
      {entry.change_type === 'entity_updated' && (
        <div className="space-y-4">
          {changedKeyDiffs.length > 0 && (
            <div className="space-y-2.5">
              <div className="text-xs font-bold text-slate-700 flex items-center justify-between">
                <span>{t('versionControl.diff.changedFieldsSummary', '变更字段对比')}</span>
                <span className="text-[11px] font-medium text-slate-400">{changedKeyDiffs.length} 项属性修改</span>
              </div>
              <div className="space-y-2">
                {changedKeyDiffs.map((cd) => (
                  <div key={cd.key} className="rounded-2xl border border-slate-200/80 bg-white p-3.5 shadow-2xs space-y-2">
                    <div className="flex items-center gap-2 border-b border-slate-100 pb-1.5">
                      <span className="text-xs font-black text-slate-800">{formatFieldLabel(cd.key, t)}</span>
                      <span className="text-[10px] font-mono text-slate-400">({cd.key})</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                      <div className="rounded-xl border border-rose-100 bg-rose-50/50 p-2.5">
                        <span className="text-[10px] font-bold uppercase text-rose-500 block mb-0.5">修改前</span>
                        <FormattedValue field={cd.key} value={cd.beforeVal} t={t} />
                      </div>
                      <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-2.5">
                        <span className="text-[10px] font-bold uppercase text-emerald-600 block mb-0.5">修改后</span>
                        <FormattedValue field={cd.key} value={cd.afterVal} t={t} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {isAfterObject && (
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <div className="text-xs font-bold text-slate-700">最新对象完整形态</div>
              <StructuredEntityCard entityType={entry.entity_type} data={after as Record<string, any>} theme="neutral" />
            </div>
          )}
        </div>
      )}

      {/* Text Blocks Diff Highlight */}
      {entry.text_blocks && entry.text_blocks.length > 0 && (
        <div className="space-y-2 rounded-2xl border border-slate-200/80 bg-slate-900 p-4 shadow-xs text-white">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">
              {t('versionControl.diff.textChanges', '文本行级差异')}
            </span>
          </div>
          <div className="space-y-1 font-mono text-xs overflow-x-auto pt-1">
            {entry.text_blocks.map((block: TextDiffBlock, i: number) => (
              <div key={i} className="space-y-0.5">
                {block.before_lines.map((line, j) => (
                  <div key={`b${j}`} className="flex items-start bg-rose-950/60 text-rose-300 px-2.5 py-0.5 rounded-sm">
                    <span className="select-none text-rose-500 font-bold mr-2">-</span>
                    <span className="whitespace-pre-wrap break-all">{line}</span>
                  </div>
                ))}
                {block.after_lines.map((line, j) => (
                  <div key={`a${j}`} className="flex items-start bg-emerald-950/60 text-emerald-300 px-2.5 py-0.5 rounded-sm">
                    <span className="select-none text-emerald-500 font-bold mr-2">+</span>
                    <span className="whitespace-pre-wrap break-all">{line}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
