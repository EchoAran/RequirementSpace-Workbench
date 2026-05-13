import React, { useMemo, useState } from 'react'

type PillTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
type DraftMaturity = 'initial' | 'structure' | 'flow' | 'delivery'
type InfoStatus = 'confirmed' | 'ai_assumption' | 'needs_confirmation' | 'conflict' | 'deferred' | 'excluded'
type MainView = 'scopeDraft' | 'assumptions' | 'conflicts' | 'delivery'
type ScopeBucket = 'in_scope' | 'out_scope' | 'external_dependency'

type ScopeItem = {
  id: string
  title: string
  desc: string
  bucket: ScopeBucket
  status: InfoStatus
  source: string
  impact: string
  dependsOn?: string
}

type ScopeAssumption = {
  id: string
  title: string
  status: InfoStatus
  source: string
  impact: string[]
  recommendedAction: string
  route: string
}

type DeliveryCheck = {
  id: string
  title: string
  status: InfoStatus
  desc: string
}

function Pill({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: PillTone }) {
  const map: Record<PillTone, string> = {
    neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
    info: 'bg-sky-100 text-sky-700 ring-sky-200',
    success: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
    warning: 'bg-amber-100 text-amber-700 ring-amber-200',
    danger: 'bg-rose-100 text-rose-700 ring-rose-200',
  }
  return <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ${map[tone]}`}>{children}</span>
}

const statusMeta: Record<InfoStatus, { label: string; tone: PillTone; desc: string }> = {
  confirmed: { label: '已确认', tone: 'success', desc: '来自用户输入或用户明确确认' },
  ai_assumption: { label: 'AI 假设', tone: 'info', desc: 'AI 基于当前上下文推测，尚未确认' },
  needs_confirmation: { label: '待确认', tone: 'warning', desc: '会影响后续范围、交付或预览' },
  conflict: { label: '有冲突', tone: 'danger', desc: '当前范围分组之间存在不一致' },
  deferred: { label: '暂不确定', tone: 'neutral', desc: '可以保留为导出时待确认项' },
  excluded: { label: '已排除', tone: 'neutral', desc: '已明确不纳入当前方案' },
}

const maturityMeta: Record<DraftMaturity, { label: string; tone: PillTone; desc: string; progress: number }> = {
  initial: { label: '初始草稿', tone: 'warning', desc: '基于一句话和少量上下文，假设较多。', progress: 22 },
  structure: { label: '结构草稿', tone: 'info', desc: '角色和任务基本明确，流程仍待确认。', progress: 46 },
  flow: { label: '流程草稿', tone: 'info', desc: '流程和规则基本明确，范围仍待收敛。', progress: 68 },
  delivery: { label: '交付草稿', tone: 'success', desc: '第一版边界正在成型，可进入预览与导出检查。', progress: 78 },
}

const scopeItems: ScopeItem[] = [
  {
    id: 'submit-request',
    title: '员工提交请假申请',
    desc: '填写请假时间、类型和原因，并提交给直属经理。',
    bucket: 'in_scope',
    status: 'confirmed',
    source: '来自页面 02 已确认核心任务',
    impact: '没有这一项，申请与审批闭环无法开始。',
  },
  {
    id: 'manager-approval',
    title: '直属经理审批',
    desc: '经理查看申请详情，选择通过或退回。',
    bucket: 'in_scope',
    status: 'confirmed',
    source: '来自页面 02 已确认核心任务',
    impact: '这是审批类应用的核心处理动作。',
  },
  {
    id: 'notify-employee',
    title: '审批结果通知员工',
    desc: '审批完成后通知员工结果，并显示基础状态。',
    bucket: 'in_scope',
    status: 'ai_assumption',
    source: '来自页面 03 流程草稿中的体验闭环建议',
    impact: '能减少员工线下询问，提升最小闭环完整性。',
    dependsOn: '员工是否需要查看状态',
  },
  {
    id: 'basic-status',
    title: '基础状态查看',
    desc: '显示待审批、已通过、已退回等基础状态。',
    bucket: 'in_scope',
    status: 'ai_assumption',
    source: '来自页面 02 辅助能力：基础状态跟踪',
    impact: '做得越清楚，员工越容易知道下一步。',
    dependsOn: '是否保留状态能力',
  },
  {
    id: 'multi-level-approval',
    title: '多级审批',
    desc: '经理审批后再由 HR 或更高层审批。',
    bucket: 'out_scope',
    status: 'ai_assumption',
    source: '来自页面 02 HR 分岔的后置建议',
    impact: '会显著增加流程、规则和原型复杂度。',
  },
  {
    id: 'leave-balance',
    title: '年假余额自动计算',
    desc: '自动读取年假余额并校验申请天数。',
    bucket: 'out_scope',
    status: 'deferred',
    source: '来自页面 04 范围收敛建议',
    impact: '需要外部考勤或 HR 系统数据，第一版可后置。',
  },
  {
    id: 'advanced-report',
    title: '高级统计报表',
    desc: '按部门、时间、请假类型统计分析。',
    bucket: 'out_scope',
    status: 'deferred',
    source: '来自页面 02 辅助能力后置建议',
    impact: '第一版对核心闭环帮助有限，容易让 Lite 应用变重。',
  },
  {
    id: 'hr-sync',
    title: 'HR 手动同步结果到考勤系统',
    desc: '审批结果由 HR 在线下或外部系统中记录。',
    bucket: 'external_dependency',
    status: 'needs_confirmation',
    source: '来自 HR 角色与系统边界待确认项',
    impact: '会影响 HR 记录是否属于系统内功能，需在交付说明中明确。',
    dependsOn: 'HR 记录是否纳入系统内功能',
  },
]

const scopeAssumptions: ScopeAssumption[] = [
  {
    id: 'single-level',
    title: '第一版只做单级审批',
    status: 'ai_assumption',
    source: '来自 Lite 最小闭环策略和页面 02 HR 角色建议。',
    impact: ['保持流程短', '减少审批规则', '页面 05 原型更容易闭环'],
    recommendedAction: '如果确实需要 HR 审批，再把多级审批从暂不做移入本期范围。',
    route: '页面 02 / 页面 03',
  },
  {
    id: 'hr-external-record',
    title: 'HR 记录先作为外部依赖',
    status: 'needs_confirmation',
    source: '来自页面 02 HR 责任边界和页面 03 通知 HR 分岔。',
    impact: ['决定是否需要 HR 记录页面', '影响交付说明', '影响页面 05 是否展示 HR 原型视角'],
    recommendedAction: '先确认 HR 是否必须在本系统内记录结果。',
    route: '页面 04：范围与交付',
  },
  {
    id: 'notification-in-scope',
    title: '审批结果通知员工属于本期范围',
    status: 'ai_assumption',
    source: '来自页面 03 流程草稿中的体验闭环。',
    impact: ['让员工知道结果', '减少线下沟通', '让系统预览更完整'],
    recommendedAction: '若通知能力暂不做，需要明确员工如何知道审批结果。',
    route: '页面 03 / 页面 05',
  },
]

const deliveryChecks: DeliveryCheck[] = [
  { id: 'goal', title: '应用目标已明确', status: 'confirmed', desc: '让员工提交请假申请，由直属经理审批，并通知相关人员。' },
  { id: 'tasks', title: '核心任务已形成', status: 'confirmed', desc: '提交申请、经理审批、查看结果已经形成最小闭环。' },
  { id: 'flow', title: '主流程已形成', status: 'confirmed', desc: '从填写、提交、审批到通知结果的流程已成型。' },
  { id: 'rules', title: '关键规则仍有待确认', status: 'needs_confirmation', desc: '退回后处理、HR 是否系统内记录仍需确认。' },
  { id: 'scope', title: '第一版范围正在收敛', status: 'ai_assumption', desc: '本期范围、暂不做和外部依赖已经初步分组。' },
]

function bucketMeta(bucket: ScopeBucket): { label: string; tone: PillTone; desc: string } {
  if (bucket === 'in_scope') return { label: '本期要做', tone: 'success', desc: '形成第一版最小闭环所需内容' }
  if (bucket === 'out_scope') return { label: '暂不做', tone: 'neutral', desc: '降低第一版复杂度，后续再评估' }
  return { label: '外部依赖', tone: 'warning', desc: '需要人或其他系统配合，不完全由本系统承担' }
}

function TopBar() {
  return (
    <div className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">页面 04：范围与交付 · 草稿审查 × 协作探索合一</div>
          <div className="text-xs text-slate-500">基于当前流程生成范围草稿，收住第一版边界并准备进入预览与验证</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700">查看范围依据</button>
          <button className="rounded-2xl bg-sky-600 px-4 py-2 text-sm font-medium text-white">生成范围草稿</button>
        </div>
      </div>
    </div>
  )
}

function TopAnchor({ maturity }: { maturity: DraftMaturity }) {
  const meta = maturityMeta[maturity]
  return (
    <section className="mb-6 rounded-3xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <Pill tone={meta.tone}>{meta.label}</Pill>
            <Pill tone="warning">2 个范围假设待确认</Pill>
            <Pill tone="success">最小闭环已成型</Pill>
            <div className="text-xs font-medium tracking-wide text-slate-500">范围收敛共创</div>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">员工请假申请</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            本页不让用户从零整理范围，而是基于已确认任务和流程生成范围草稿。你可以移动条目、查看影响、标记外部依赖，把第一版做小做清楚。
          </p>
        </div>
        <div className="w-[320px] shrink-0 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
          <div className="mb-2 flex items-center justify-between text-xs font-medium text-slate-500">
            <span>草稿成熟度</span>
            <span>{meta.progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-slate-200">
            <div className="h-2 rounded-full bg-sky-500" style={{ width: `${meta.progress}%` }} />
          </div>
          <div className="mt-3 text-xs leading-5 text-slate-600">{meta.desc}</div>
        </div>
      </div>
    </section>
  )
}

function LeftNav() {
  const nav = [
    { label: '概览', maturity: '初始草稿', tone: 'warning' as PillTone },
    { label: '要做什么', maturity: '结构草稿', tone: 'info' as PillTone },
    { label: '怎么运作', maturity: '流程草稿', tone: 'info' as PillTone },
    { label: '范围与交付', active: true, maturity: '交付草稿', tone: 'success' as PillTone },
    { label: '预览与验证', maturity: '可做预览', tone: 'info' as PillTone },
  ]
  return (
    <aside className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 px-2 text-xs font-semibold tracking-wide text-slate-500">工作台视角</div>
      <nav className="space-y-2">
        {nav.map((item) => (
          <button key={item.label} className={`w-full rounded-2xl px-3 py-3 text-left ${item.active ? 'bg-sky-50 ring-1 ring-sky-200' : 'bg-slate-50 hover:bg-slate-100'}`}>
            <div className="flex items-center justify-between gap-3">
              <div className={`text-sm font-medium ${item.active ? 'text-sky-800' : 'text-slate-800'}`}>{item.label}</div>
              <Pill tone={item.tone}>{item.maturity}</Pill>
            </div>
          </button>
        ))}
      </nav>
      <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-xs leading-5 text-slate-500 ring-1 ring-slate-200">
        页面 04 负责收敛第一版边界。范围越清楚，页面 05 的预览和诊断越可靠。
      </div>
    </aside>
  )
}

function ModeTabs({ view, setView }: { view: MainView; setView: (view: MainView) => void }) {
  const tabs = [
    { key: 'scopeDraft', label: '范围草稿', note: '本期 / 暂不做 / 依赖' },
    { key: 'assumptions', label: '范围假设', note: '影响第一版边界' },
    { key: 'conflicts', label: '冲突与影响', note: '移动条目看后果' },
    { key: 'delivery', label: '交付检查', note: '进入预览前确认' },
  ] as const
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="grid grid-cols-4 gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setView(tab.key)}
            className={`rounded-2xl px-4 py-3 text-left transition ${view === tab.key ? 'bg-sky-50 ring-1 ring-sky-200' : 'bg-slate-50 hover:bg-slate-100'}`}
          >
            <div className={`text-sm font-semibold ${view === tab.key ? 'text-sky-800' : 'text-slate-800'}`}>{tab.label}</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">{tab.note}</div>
          </button>
        ))}
      </div>
    </section>
  )
}

function ScopeCard({ item }: { item: ScopeItem }) {
  const meta = statusMeta[item.status]
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">{item.title}</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">{item.source}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="text-sm leading-6 text-slate-700">{item.desc}</div>
      <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200">{item.impact}</div>
      {item.dependsOn ? <div className="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800 ring-1 ring-amber-200">依赖：{item.dependsOn}</div> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="rounded-xl bg-sky-600 px-3 py-2 text-xs font-medium text-white">采纳</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700">移动</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700">解释</button>
      </div>
    </div>
  )
}

function ScopeColumn({ bucket }: { bucket: ScopeBucket }) {
  const meta = bucketMeta(bucket)
  const items = scopeItems.filter((item) => item.bucket === bucket)
  return (
    <section className="rounded-3xl bg-slate-50 p-5 ring-1 ring-slate-200">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">{meta.label}</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">{meta.desc}</div>
        </div>
        <Pill tone={meta.tone}>{items.length} 项</Pill>
      </div>
      <div className="space-y-3">
        {items.map((item) => <ScopeCard key={item.id} item={item} />)}
      </div>
    </section>
  )
}

function ScopeDraftView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">基于当前流程的范围草稿</h2>
            <p className="mt-1 text-sm text-slate-500">范围草稿从已确认任务和流程推导，不从一句话直接生成完整边界。</p>
          </div>
          <div className="flex gap-2"><Pill tone="success">4 项本期</Pill><Pill tone="neutral">3 项后置</Pill><Pill tone="warning">1 项依赖</Pill></div>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          建议第一版优先保留提交、审批、结果通知和基础状态；把多级审批、年假余额和高级报表后置；HR 同步先标为外部依赖。
        </div>
      </section>

      <section className="grid grid-cols-3 gap-5">
        <ScopeColumn bucket="in_scope" />
        <ScopeColumn bucket="out_scope" />
        <ScopeColumn bucket="external_dependency" />
      </section>
    </main>
  )
}

function AssumptionCard({ item }: { item: ScopeAssumption }) {
  const meta = statusMeta[item.status]
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="text-base font-semibold text-slate-900">{item.title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-500">{item.source}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
        <div className="mb-2 text-xs font-semibold tracking-wide text-slate-400">影响范围</div>
        <div className="grid gap-2">
          {item.impact.map((impact) => (
            <div key={impact} className="rounded-xl bg-white px-3 py-2 text-sm leading-5 text-slate-700 ring-1 ring-slate-200">{impact}</div>
          ))}
        </div>
      </div>
      <div className="mt-3 rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">{item.recommendedAction}</div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">去确认</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">修改假设</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">保留待确认</button>
      </div>
    </div>
  )
}

function AssumptionsView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">范围假设</h2>
            <p className="mt-1 text-sm text-slate-500">这些假设决定第一版做多大。确认或修改它们，可以避免第一版范围过重。</p>
          </div>
          <Pill tone="warning">1 个关键待确认</Pill>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          当前最值得确认的是“HR 记录是否属于系统内功能”。如果本期做系统内记录，就需要 HR 视角、记录页面和更多规则。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {scopeAssumptions.map((item) => <AssumptionCard key={item.id} item={item} />)}
      </section>
    </main>
  )
}

function ConflictImpactView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-slate-900">冲突与影响</h2>
          <p className="mt-1 text-sm text-slate-500">移动范围项时，先看它会影响流程、原型和交付说明。</p>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          当前没有硬冲突，但“HR 记录结果”仍存在边界不清：它可以是外部依赖，也可以成为本期系统内功能。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <div className="text-base font-semibold text-slate-900">如果把“HR 记录结果”移入本期</div>
              <div className="mt-1 text-sm leading-6 text-slate-500">系统会承担更多 HR 操作，而不是只通知或导出。</div>
            </div>
            <Pill tone="warning">复杂度上升</Pill>
          </div>
          <div className="space-y-2">
            {['流程：增加 HR 记录步骤', '原型：需要 HR 记录页面或入口', '规则：需要定义谁记录、何时记录、是否可修改', '范围：第一版从轻闭环变成更完整管理流程'].map((item) => (
              <div key={item} className="rounded-xl bg-slate-50 px-3 py-2 text-sm leading-5 text-slate-700 ring-1 ring-slate-200">{item}</div>
            ))}
          </div>
          <button className="mt-4 rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">移入本期并生成影响</button>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <div className="text-base font-semibold text-slate-900">如果继续标为外部依赖</div>
              <div className="mt-1 text-sm leading-6 text-slate-500">第一版保持轻，但交付说明必须讲清楚边界。</div>
            </div>
            <Pill tone="success">保持轻量</Pill>
          </div>
          <div className="space-y-2">
            {['流程：审批后通知 HR 或导出结果即可', '原型：HR 视角可以只做说明，不必做完整页面', '规则：说明 HR 在外部系统中记录', '范围：第一版聚焦提交、审批和通知闭环'].map((item) => (
              <div key={item} className="rounded-xl bg-slate-50 px-3 py-2 text-sm leading-5 text-slate-700 ring-1 ring-slate-200">{item}</div>
            ))}
          </div>
          <button className="mt-4 rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">保持外部依赖</button>
        </div>
      </section>

      <section className="rounded-3xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
        <div className="text-sm font-semibold text-slate-900">范围收敛原则</div>
        <div className="mt-2 text-sm leading-6 text-amber-800">第一版不是功能越多越好，而是越小、越清楚、越容易跑通越好。后续增强可以保留为暂不做项。</div>
      </section>
    </main>
  )
}

function DeliveryCheckCard({ item }: { item: DeliveryCheck }) {
  const meta = statusMeta[item.status]
  return (
    <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="text-sm font-semibold text-slate-900">{item.title}</div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="text-sm leading-6 text-slate-600">{item.desc}</div>
    </div>
  )
}

function DeliveryView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">交付检查</h2>
            <p className="mt-1 text-sm text-slate-500">确认当前草稿是否可以进入预览与验证，或导出为带待确认项版本。</p>
          </div>
          <Pill tone="warning">可预览，导出需带待确认项</Pill>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          当前方案可以进入页面 05 做系统级预览，但仍建议保留“HR 记录是否系统内完成”和“退回后处理”两个待确认项。
        </div>
      </section>

      <section className="grid grid-cols-[minmax(0,1fr)_360px] gap-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 text-lg font-semibold text-slate-900">准备度检查</div>
          <div className="space-y-3">
            {deliveryChecks.map((item) => <DeliveryCheckCard key={item.id} item={item} />)}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 text-sm font-semibold text-slate-900">交付动作</div>
          <div className="space-y-3">
            <button className="w-full rounded-2xl bg-sky-600 px-4 py-3 text-left text-sm font-medium text-white">进入预览与验证</button>
            <button className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-medium text-slate-700">导出带待确认项方案</button>
            <button className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-medium text-slate-700">生成交付草稿摘要</button>
          </div>
          <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-200">
            交付草稿不是可运行应用，而是给同事、开发或低代码实施人员讨论的结构化方案。
          </div>
        </div>
      </section>
    </main>
  )
}

function RightRail({ setView }: { setView: (view: MainView) => void }) {
  return (
    <aside className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">当前关键边界</div>
        <div className="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-200">
          <div className="text-sm font-semibold text-slate-900">HR 记录结果是否属于系统内功能？</div>
          <div className="mt-2 text-sm leading-6 text-amber-800">这个判断会影响 HR 视角、记录页面、交付说明和页面 05 原型。</div>
          <button onClick={() => setView('conflicts')} className="mt-3 rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">查看影响</button>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">范围假设账本</div>
        <div className="space-y-3">
          {scopeAssumptions.map((item) => {
            const meta = statusMeta[item.status]
            return (
              <button key={item.id} onClick={() => setView('assumptions')} className="w-full rounded-2xl bg-slate-50 p-4 text-left ring-1 ring-slate-200 hover:bg-slate-100">
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold leading-5 text-slate-900">{item.title}</div>
                  <Pill tone={meta.tone}>{meta.label}</Pill>
                </div>
                <div className="text-xs leading-5 text-slate-500">{item.route}</div>
              </button>
            )
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">AI 可以帮你</div>
        <div className="space-y-2">
          {[
            ['解释 HR 记录边界影响', 'info'],
            ['把范围草稿收得更轻', 'neutral'],
            ['生成带待确认项交付摘要', 'neutral'],
          ].map(([label, tone]) => (
            <button key={label} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50">
              <span className="mr-2"><Pill tone={tone as PillTone}>{tone === 'info' ? '推荐' : '可选'}</Pill></span>{label}
            </button>
          ))}
        </div>
      </section>
    </aside>
  )
}

function FloatingAI({ view }: { view: MainView }) {
  const placeholder =
    view === 'scopeDraft'
      ? '例如：帮我把第一版范围再收紧一点'
      : view === 'assumptions'
        ? '例如：解释为什么 HR 记录建议先作为外部依赖'
        : view === 'conflicts'
          ? '例如：如果把 HR 记录移入本期，会影响什么？'
          : '例如：生成一个带待确认项的交付草稿摘要'

  return (
    <div className="fixed bottom-5 left-1/2 z-10 w-[780px] -translate-x-1/2 rounded-3xl border border-slate-200 bg-white/95 px-5 py-4 shadow-xl backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 ring-1 ring-sky-200">页面 04：范围与交付</div>
        <input className="h-11 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none" placeholder={placeholder} />
        <button className="rounded-2xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white">AI 帮我推进</button>
      </div>
    </div>
  )
}

export default function LitePage04IntegratedDraftExploration() {
  const [view, setView] = useState<MainView>('scopeDraft')
  const maturity = useMemo<DraftMaturity>(() => 'delivery', [])

  return (
    <div className="min-h-screen bg-slate-100">
      <TopBar />
      <div className="min-h-screen bg-slate-50 pb-28 text-slate-900">
        <div className="mx-auto max-w-[1600px] px-6 py-6">
          <TopAnchor maturity={maturity} />
          <div className="grid grid-cols-[220px_minmax(0,1fr)_380px] gap-6">
            <LeftNav />
            <div className="space-y-6">
              <ModeTabs view={view} setView={setView} />
              {view === 'scopeDraft' ? <ScopeDraftView /> : view === 'assumptions' ? <AssumptionsView /> : view === 'conflicts' ? <ConflictImpactView /> : <DeliveryView />}
            </div>
            <RightRail setView={setView} />
          </div>
        </div>
        <FloatingAI view={view} />
      </div>
    </div>
  )
}
