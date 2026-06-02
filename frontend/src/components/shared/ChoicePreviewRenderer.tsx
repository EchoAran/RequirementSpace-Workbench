import React from 'react';
import { GherkinVisualRenderer } from './GherkinVisualizer';

function asArray(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

function parseParentFeatureNumber(num?: string | null) {
  if (!num) return null;
  const delimiter = num.includes('.') ? '.' : num.includes('-') ? '-' : null;
  if (!delimiter) return null;
  return num.split(delimiter).slice(0, -1).join(delimiter);
}

function getFeatureDepth(num?: string | null) {
  if (!num) return 0;
  const delimiter = num.includes('.') ? '.' : num.includes('-') ? '-' : null;
  if (!delimiter) return 0;
  return num.split(delimiter).length - 1;
}

function buildNestedFeatureTree(features: any[]) {
  const byNumber = new Map<string, any>();
  const roots: any[] = [];

  features.forEach((f, idx) => {
    const num = f.feature_number || f.featureNumber || `draft-${idx}`;
    byNumber.set(num, { ...f, feature_number: num, children: [] });
  });

  Array.from(byNumber.values()).forEach((f) => {
    const parentNum = parseParentFeatureNumber(f.feature_number);
    const parent = parentNum ? byNumber.get(parentNum) : null;
    if (parent) {
      parent.children.push(f);
    } else {
      roots.push(f);
    }
  });

  const sortByNum = (items: any[]) => {
    items.sort((a, b) => String(a.feature_number).localeCompare(String(b.feature_number), undefined, { numeric: true }));
    items.forEach((item) => sortByNum(item.children));
    return items;
  };

  return sortByNum(roots);
}

export function ExpandableFeatureTreeNode({ node, depth = 0 }: { node: any; depth?: number }) {
  const [isExpanded, setIsExpanded] = React.useState(true); // Default fully expanded as requested!
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="space-y-1">
      <div 
        className={`flex items-start gap-1.5 p-2 rounded-xl border transition-all ${
          depth === 0 
            ? 'bg-slate-50/70 border-slate-200/80 shadow-sm' 
            : 'bg-white border-slate-100 hover:border-indigo-200 shadow-inner bg-slate-50/10'
        }`}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="mt-0.5 p-0.5 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 transition-colors shrink-0 flex items-center justify-center focus:outline-none"
          >
            {isExpanded ? (
              <span className="block text-[8px] leading-none font-bold select-none transform scale-90">▼</span>
            ) : (
              <span className="block text-[8px] leading-none font-bold select-none transform scale-90">▶</span>
            )}
          </button>
        ) : (
          <span className="w-4 h-4 shrink-0 block" />
        )}
        
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {node.feature_number && (
              <span className="rounded bg-slate-100 border border-slate-200/50 px-1 py-0.2 text-[8px] font-bold text-slate-500 font-mono tracking-tighter leading-none select-none">
                {node.feature_number}
              </span>
            )}
            <span className="text-[11px] font-extrabold text-slate-800 leading-normal truncate">
              {node.feature_name || node.name || node.featureName || node.title}
            </span>
          </div>
          {(node.feature_description || node.description || node.featureDescription) && (
            <p className="mt-1 text-[10px] text-slate-500 leading-relaxed font-medium">
              {node.feature_description || node.description || node.featureDescription}
            </p>
          )}
          {asArray(node.actor_names || node.actorNames).length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5 select-none">
              {asArray(node.actor_names || node.actorNames).map((an: string, j: number) => (
                <span key={j} className="inline-flex rounded-full border border-indigo-150 bg-indigo-50/50 px-1.5 py-0.2 text-[8px] font-bold text-indigo-755 leading-none">{an}</span>
              ))}
            </div>
          )}
        </div>
      </div>
      {hasChildren && isExpanded && (
        <div className="pl-3.5 border-l border-slate-200 ml-3.5 space-y-1.5 mt-1 animate-in fade-in duration-200">
          {node.children.map((child: any) => (
            <ExpandableFeatureTreeNode key={child.feature_number || child.feature_name} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ExpandableFeatureTree({ features }: { features: any[] }) {
  const nestedTree = buildNestedFeatureTree(features);
  return (
    <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1 select-text">
      {nestedTree.length > 0 ? (
        nestedTree.map((root) => (
          <ExpandableFeatureTreeNode key={root.feature_number || root.feature_name} node={root} />
        ))
      ) : (
        <div className="text-[10px] text-slate-400 italic bg-slate-50 border border-slate-100 rounded-xl p-3 text-center">
          暂无功能节点
        </div>
      )}
    </div>
  );
}

export function DetailedActorList({ actors }: { actors: any[] }) {
  return (
    <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1 select-text">
      {actors.length > 0 ? (
        actors.map((actor: any, i: number) => (
          <div key={i} className="p-2.5 rounded-xl bg-slate-50/50 border border-slate-200/60 shadow-sm space-y-1.5 hover:border-indigo-200 transition-colors">
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] bg-amber-50 border border-amber-100 text-amber-700 font-extrabold px-1.5 py-0.5 rounded-md leading-none select-none">角色</span>
              <span className="text-[11px] font-extrabold text-slate-800 leading-none">{actor.actor_name || actor.name}</span>
            </div>
            {(actor.actor_description || actor.description) && (
              <p className="text-[10px] text-slate-500 leading-relaxed font-medium">
                {actor.actor_description || actor.description}
              </p>
            )}
          </div>
        ))
      ) : (
        <div className="text-[10px] text-slate-400 italic bg-slate-50 border border-slate-100 rounded-xl p-3 text-center">
          暂无参与者角色
        </div>
      )}
    </div>
  );
}

interface ChoicePreviewRendererProps {
  draftType?: string;
  preview?: any;
  payload?: any;
  comparisonSummary?: string;
}

export function ChoicePreviewRenderer({
  draftType,
  preview,
  payload,
  comparisonSummary,
}: ChoicePreviewRendererProps) {
  switch (draftType) {
    case 'project_creation':
      return <ProjectCreationPreview preview={preview} payload={payload} comparisonSummary={comparisonSummary} />;
    case 'actor':
      return <ActorPreview preview={preview} payload={payload} comparisonSummary={comparisonSummary} />;
    case 'scenario':
      return <ScenarioPreview preview={preview} payload={payload} comparisonSummary={comparisonSummary} />;
    case 'acceptance_criteria':
      return <ACPreview preview={preview} payload={payload} comparisonSummary={comparisonSummary} />;
    case 'feature':
      return <FeaturePreview preview={preview} payload={payload} comparisonSummary={comparisonSummary} />;
    case 'flow':
      return <FlowPreview preview={preview} payload={payload} comparisonSummary={comparisonSummary} />;
    case 'scope':
      return <ScopePreview preview={preview} payload={payload} comparisonSummary={comparisonSummary} />;
    default:
      return <GenericPreview preview={preview} comparisonSummary={comparisonSummary} />;
  }
}

/* ── Project Creation Preview ─────────────────────────────── */

function ProjectCreationPreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const project = preview || payload || {};
  const actors = asArray(payload?.actors || preview?.actors || []);
  const features = asArray(payload?.features || preview?.features || []);

  const normalizedActors = actors.map(act => typeof act === 'string' ? { name: act } : act);

  return (
    <div className="space-y-6">
      <div>
        <h4 className="text-xl font-bold text-slate-900 mb-1">
          {project.project_name || '未命名项目'}
        </h4>
        {project.project_description && (
          <p className="text-sm text-slate-500 leading-relaxed">
            {project.project_description}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h5 className="text-xs font-black uppercase tracking-wide text-slate-500">涉众角色定义</h5>
          <span className="text-xs font-bold text-slate-400">（{normalizedActors.length} 个角色）</span>
        </div>
        <DetailedActorList actors={normalizedActors} />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h5 className="text-xs font-black uppercase tracking-wide text-slate-500">核心功能模块树</h5>
          <span className="text-xs font-bold text-slate-400">（{features.length} 个节点）</span>
        </div>
        <ExpandableFeatureTree features={features} />
      </div>

    </div>
  );
}

/* ── Actor Preview ─────────────────────────────────────────── */

function ActorPreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const actors = preview?.actors || payload?.actors || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-black uppercase tracking-wide text-slate-500">参与者列表</span>
        <span className="text-xs font-bold text-slate-400">（{actors.length} 个）</span>
      </div>

      <DetailedActorList actors={actors} />

    </div>
  );
}

/* ── Scenario Preview ──────────────────────────────────────── */

function ScenarioPreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const scenarios = preview?.scenarios || payload?.scenarios || [];
  const featureName = preview?.feature_name || (scenarios[0]?.feature_name) || '';
  const actorName = preview?.actor_name || (scenarios[0]?.actor_name) || '';

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Chip className="bg-indigo-50 text-indigo-700 border-indigo-100">{featureName}</Chip>
        <span className="text-slate-300">×</span>
        <Chip className="bg-amber-50 text-amber-700 border-amber-100">{actorName}</Chip>
        <span className="text-xs text-slate-400 ml-auto">{scenarios.length} 个场景</span>
      </div>

      <div className="divide-y divide-slate-100">
        {scenarios.map((s: any, i: number) => (
          <div key={i} className="py-2.5 first:pt-0 last:pb-0">
            <p className="text-sm font-bold text-slate-800">
              {s.scenario_name}
            </p>
            <p className="text-xs text-slate-500 mt-0.5 leading-relaxed line-clamp-2">
              {s.scenario_content}
            </p>
          </div>
        ))}
      </div>

    </div>
  );
}

/* ── Acceptance Criteria Preview ──────────────────────────── */

function ACPreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const criteria = preview?.criteria || payload?.acceptance_criteria || [];
  return (
    <div className="space-y-4">
      {criteria.length > 0 ? (
        <div className="space-y-4">
          {criteria.map((ac: any, i: number) => {
            const text = ac.content || ac.criterion_content || '';
            return (
              <GherkinVisualRenderer
                key={ac.id || ac.criterion_id || i}
                text={text}
                title={`验收标准 #${i + 1}`}
                badge="验收标准"
              />
            );
          })}
        </div>
      ) : (
        <div className="text-xs text-slate-400 italic bg-slate-50 border border-slate-100 rounded-xl p-4 text-center">
          暂无验收标准数据
        </div>
      )}
    </div>
  );
}

/* ── Feature Preview ───────────────────────────────────────── */

function FeaturePreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const features = preview?.features || payload?.features || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-black uppercase tracking-wide text-slate-500">核心功能分解</span>
        <span className="text-xs font-bold text-slate-400">（{features.length} 个节点）</span>
      </div>

      <ExpandableFeatureTree features={features} />
      
    </div>
  );
}

/* ── Flow Preview ──────────────────────────────────────────── */

function FlowPreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const flows = preview?.flows || [];
  const boCount = preview?.business_object_count || 0;
  return (
    <div className="space-y-5">
      <div className="flex justify-between items-center bg-slate-50 border border-slate-150 rounded-xl p-3">
        <span className="text-xs text-slate-600 font-semibold">包含 {flows.length} 个业务流程</span>
        <span className="rounded bg-indigo-50 border border-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-700">
          {boCount} 个业务对象数据
        </span>
      </div>
      
      <div className="space-y-5">
        {flows.map((f: any, i: number) => (
          <div key={i} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
            <div>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h5 className="text-sm font-extrabold text-slate-900">{f.flow_name}</h5>
                {f.feature_names && f.feature_names.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {f.feature_names.map((fn: string, j: number) => (
                      <Chip key={j} className="bg-emerald-50 text-emerald-700 border-emerald-100 text-[9px] font-bold tracking-tight py-0">{fn}</Chip>
                    ))}
                  </div>
                )}
              </div>
              <p className="text-[10px] text-slate-400 font-extrabold uppercase mt-1 tracking-wider">{f.step_count || 0} Steps</p>
            </div>

            {/* Visual step timeline trail */}
            {((f.flow_steps || f.flowSteps) && asArray(f.flow_steps || f.flowSteps).length > 0) ? (
              <div className="mt-4 pl-2 space-y-4 border-l-2 border-dashed border-slate-200/80 ml-2">
                {asArray(f.flow_steps || f.flowSteps).map((step: any, stepIndex: number) => {
                  const number = step.step_number || step.stepNumber || `S-${String(stepIndex + 1).padStart(3, '0')}`;
                  const type = step.step_type || step.stepType || 'actorAction';
                  const name = step.step_name || step.stepName || '';
                  const desc = step.step_description || step.stepDescription || '';
                  const actors = asArray(step.actor_names || step.actorNames);
                  const inputs = asArray(step.input_business_object_names || step.inputBusinessObjectNames);
                  const outputs = asArray(step.output_business_object_names || step.outputBusinessObjectNames);
                  
                  return (
                    <div key={stepIndex} className="relative pl-6">
                      {/* Timeline dot */}
                      <span className="absolute -left-[9px] top-1 flex h-4 w-4 items-center justify-center rounded-full bg-white border-2 border-indigo-500 shadow-sm text-[8px] font-bold text-indigo-600 font-mono">
                        {stepIndex + 1}
                      </span>
                      <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3 shadow-inner">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded bg-white border border-slate-200 px-1.5 py-0.5 text-[9px] font-extrabold text-slate-500 font-mono leading-none">
                            {number}
                          </span>
                          <span className="rounded bg-white border border-slate-200 px-1.5 py-0.5 text-[9px] font-bold text-slate-500 leading-none">
                            {type === 'actorAction' ? '👤 交互' : type === 'systemAction' ? '⚙️ 自动' : '🔀 分支'}
                          </span>
                          <h6 className="text-xs font-bold text-slate-800 leading-none">{name}</h6>
                        </div>
                        {desc && (
                          <p className="mt-2 text-xs text-slate-500 leading-relaxed font-medium">{desc}</p>
                        )}
                        <div className="mt-2.5 grid gap-2.5 text-[10px] leading-none sm:grid-cols-2">
                          {actors.length > 0 && (
                            <div>
                              <div className="mb-1 font-bold text-slate-400">执行角色</div>
                              <div className="flex flex-wrap gap-1">
                                {actors.map((act) => (
                                  <span key={act} className="rounded bg-amber-50 border border-amber-100 text-amber-700 px-1.5 py-0.5 font-bold">{act}</span>
                                ))}
                              </div>
                            </div>
                          )}
                          {(inputs.length > 0 || outputs.length > 0) && (
                            <div>
                              <div className="mb-1 font-bold text-slate-400">输入 / 输出业务数据</div>
                              <div className="flex flex-wrap gap-1">
                                {inputs.map((inp) => (
                                  <span key={inp} className="rounded bg-slate-100 border border-slate-200 text-slate-600 px-1.5 py-0.5 font-bold">In: {inp}</span>
                                ))}
                                {outputs.map((out) => (
                                  <span key={out} className="rounded bg-emerald-50 border border-emerald-100 text-emerald-700 px-1.5 py-0.5 font-bold">Out: {out}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (f.step_names || []).length > 0 ? (
              <div className="mt-3 pl-2 space-y-3 border-l-2 border-dashed border-slate-250 ml-2">
                {(f.step_names as string[]).map((sn: string, j: number) => (
                  <div key={j} className="relative pl-6">
                    <span className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full bg-indigo-500 shadow-sm" />
                    <p className="text-xs text-slate-700 font-semibold">{sn}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Scope Preview ─────────────────────────────────────────── */

function ScopePreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const scopes = preview?.scopes || [];

  const isCurrent = (status: string) => {
    const s = String(status || '').toLowerCase();
    return s === 'current' || s === '本期';
  };
  const isPostponed = (status: string) => {
    const s = String(status || '').toLowerCase();
    return s === 'postponed' || s === '暂缓';
  };

  const current = scopes.filter((s: any) => isCurrent(s.scope_status)).length;
  const postponed = scopes.filter((s: any) => isPostponed(s.scope_status)).length;
  const excluded = scopes.filter((s: any) => !isCurrent(s.scope_status) && !isPostponed(s.scope_status)).length;

  return (
    <div className="space-y-4">
      <div className="flex gap-3 text-xs">
        <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 font-bold rounded-full border border-emerald-100/50">本期 {current}</span>
        <span className="px-2.5 py-1 bg-sky-50 text-sky-700 font-bold rounded-full border border-sky-100/50">暂缓 {postponed}</span>
        <span className="px-2.5 py-1 bg-slate-100 text-slate-600 font-bold rounded-full border border-slate-200/50">不纳入 {excluded}</span>
      </div>
      <div className="divide-y divide-slate-100">
        {scopes.map((s: any, i: number) => (
          <div key={i} className="py-3 first:pt-0 last:pb-0 text-left">
            <div className="flex items-center gap-2">
              <p className="text-xs font-bold text-slate-800">{s.feature_name || `功能 #${s.feature_id}`}</p>
              <span className={`text-[9px] font-extrabold px-1.5 py-0.2 rounded-md ${
                isCurrent(s.scope_status) ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' :
                isPostponed(s.scope_status) ? 'bg-sky-50 text-sky-700 border border-sky-100' :
                'bg-rose-50 text-rose-700 border border-rose-100'
              }`}>
                {isCurrent(s.scope_status) ? '本期' : isPostponed(s.scope_status) ? '暂缓' : '不纳入'}
              </span>
            </div>
            {s.kano_category && (
              <div className="mt-1">
                <span className="text-[9px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-1.5 py-0.2 rounded-md">
                  Kano: {s.kano_category}
                </span>
              </div>
            )}
            {s.reason && <p className="text-[10px] text-slate-500 mt-1 leading-normal font-medium">{s.reason}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Generic JSON Fallback Preview ─────────────────────────── */

function GenericPreview({
  preview, comparisonSummary,
}: { preview?: any; comparisonSummary?: string }) {
  return (
    <div className="space-y-4">
      {preview && Object.keys(preview).length > 0 ? (
        <pre className="text-xs text-slate-600 bg-slate-50 p-4 rounded-xl overflow-auto max-h-64 whitespace-pre-wrap">
          {JSON.stringify(preview, null, 2)}
        </pre>
      ) : (
        <p className="text-sm text-slate-400 italic">暂无预览信息</p>
      )}
    </div>
  );
}

/* ── Shared mini components ────────────────────────────────── */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      {title && (
        <h5 className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-2">{title}</h5>
      )}
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function Chip({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <span className={`px-3 py-1 text-xs font-medium rounded-full border ${className || ''}`}>
      {children}
    </span>
  );
}
