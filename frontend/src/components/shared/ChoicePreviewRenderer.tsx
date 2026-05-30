/**
 * ChoicePreviewRenderer — dispatches preview rendering by draft_type.
 *
 * Used inside ChoiceGroupPreviewModal to show type-appropriate content
 * for each candidate choice.
 */

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
  preview, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-xl font-bold text-slate-900 mb-1">
          {preview?.project_name || '未命名项目'}
        </h4>
        <p className="text-sm text-slate-500">
          {preview?.project_description || ''}
        </p>
      </div>

      <Section title={`参与者（${preview?.actor_count || 0}）`}>
        {(preview?.actors || []).map((name: string, i: number) => (
          <Chip key={i} className="bg-blue-50 text-blue-700 border-blue-100">
            {name}
          </Chip>
        ))}
      </Section>

      <Section title={`功能模块（${preview?.feature_count || 0}）`}>
        {(preview?.features || []).map((name: string, i: number) => (
          <Chip key={i} className="bg-emerald-50 text-emerald-700 border-emerald-100">
            {name}
          </Chip>
        ))}
      </Section>

      {comparisonSummary && (
        <SummaryBox text={comparisonSummary} />
      )}
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
        <span className="text-sm font-bold text-slate-700">参与者列表</span>
        <span className="text-xs text-slate-400">（{actors.length} 个）</span>
      </div>

      <Section title="">
        {actors.map((actor: any, i: number) => (
          <div key={i} className="p-3 rounded-xl bg-slate-50 border border-slate-100">
            <p className="text-sm font-bold text-slate-800">{actor.actor_name || actor.name}</p>
            <p className="text-xs text-slate-500 mt-0.5">{actor.actor_description || actor.description || ''}</p>
          </div>
        ))}
      </Section>

      {comparisonSummary && (
        <SummaryBox text={comparisonSummary} />
      )}
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

      {comparisonSummary && (
        <SummaryBox text={comparisonSummary} />
      )}
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
      <Section title={`验收标准 — ${preview?.scenario_name || ''}（${criteria.length} 条）`}>
        {criteria.map((ac: any, i: number) => (
          <div key={i} className="w-full p-3 rounded-xl bg-slate-50 border border-slate-100">
            <p className="text-xs text-slate-700 leading-relaxed">{ac.content || ac.criterion_content}</p>
          </div>
        ))}
      </Section>
      {comparisonSummary && <SummaryBox text={comparisonSummary} />}
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
      <Section title={`功能树（${features.length} 项）`}>
        {features.map((f: any, i: number) => (
          <div key={i} className="w-full p-3 rounded-xl bg-slate-50 border border-slate-100">
            <p className="text-sm font-bold text-slate-800">{f.feature_name}</p>
            <p className="text-xs text-slate-500 mt-0.5">{f.feature_description}</p>
            {f.actor_names && f.actor_names.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {f.actor_names.map((an: string, j: number) => (
                  <Chip key={j} className="bg-blue-50 text-blue-600 border-blue-100 text-[10px]">{an}</Chip>
                ))}
              </div>
            )}
          </div>
        ))}
      </Section>
      {comparisonSummary && <SummaryBox text={comparisonSummary} />}
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
    <div className="space-y-4">
      <p className="text-xs text-slate-500">{flows.length} 个流程，{boCount} 个业务对象</p>
      <div className="divide-y divide-slate-100">
        {flows.map((f: any, i: number) => (
          <div key={i} className="py-3 first:pt-0 last:pb-0">
            <p className="text-sm font-bold text-slate-800">{f.flow_name}</p>
            {f.feature_names && f.feature_names.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {f.feature_names.map((fn: string, j: number) => (
                  <Chip key={j} className="bg-emerald-50 text-emerald-600 border-emerald-100 text-[10px]">{fn}</Chip>
                ))}
              </div>
            )}
            <p className="text-xs text-slate-400 mt-1">{f.step_count} 个步骤</p>
            {(f.step_names || []).length > 0 && (
              <div className="mt-1.5 space-y-0.5">
                {(f.step_names as string[]).map((sn: string, j: number) => (
                  <p key={j} className="text-xs text-slate-500 pl-3 border-l-2 border-slate-200">{sn}</p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {comparisonSummary && <SummaryBox text={comparisonSummary} />}
    </div>
  );
}

/* ── Scope Preview ─────────────────────────────────────────── */

function ScopePreview({
  preview, payload, comparisonSummary,
}: { preview?: any; payload?: any; comparisonSummary?: string }) {
  const scopes = preview?.scopes || [];
  const current = scopes.filter((s: any) => s.scope_status === 'current').length;
  const postponed = scopes.filter((s: any) => s.scope_status === 'postponed').length;
  const excluded = scopes.filter((s: any) => s.scope_status === 'exclude').length;
  return (
    <div className="space-y-4">
      <div className="flex gap-3 text-xs">
        <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 font-medium rounded-full">当前 {current}</span>
        <span className="px-2.5 py-1 bg-amber-50 text-amber-700 font-medium rounded-full">推迟 {postponed}</span>
        <span className="px-2.5 py-1 bg-slate-100 text-slate-600 font-medium rounded-full">不纳入 {excluded}</span>
      </div>
      <div className="divide-y divide-slate-100">
        {scopes.map((s: any, i: number) => (
          <div key={i} className="py-2.5 first:pt-0 last:pb-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-bold text-slate-800">{s.feature_name || `功能 #${s.feature_id}`}</p>
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                s.scope_status === 'current' ? 'bg-emerald-50 text-emerald-700' :
                s.scope_status === 'postponed' ? 'bg-amber-50 text-amber-700' :
                'bg-slate-100 text-slate-500'
              }`}>
                {s.scope_status === 'current' ? '当前' : s.scope_status === 'postponed' ? '推迟' : '不纳入'}
              </span>
            </div>
            {s.kano_category && (
              <span className="text-[10px] text-indigo-500 font-medium">Kano: {s.kano_category}</span>
            )}
            {s.reason && <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{s.reason}</p>}
          </div>
        ))}
      </div>
      {comparisonSummary && <SummaryBox text={comparisonSummary} />}
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
      {comparisonSummary && <SummaryBox text={comparisonSummary} />}
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

function SummaryBox({ text }: { text: string }) {
  return (
    <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
      <p className="text-xs text-slate-600">{text}</p>
    </div>
  );
}
