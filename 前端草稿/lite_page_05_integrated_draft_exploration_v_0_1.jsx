import React, { useMemo, useState } from 'react'

type PillTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
type DraftMaturity = 'initial' | 'structure' | 'flow' | 'delivery'
type InfoStatus = 'confirmed' | 'ai_assumption' | 'needs_confirmation' | 'conflict' | 'deferred' | 'excluded'
type MainView = 'checkpoint' | 'systemFlow' | 'prototype' | 'issues'
type PreviewStage = 'initial' | 'structure' | 'flow' | 'delivery'

type PreviewIssue = {
  id: string
  title: string
  desc: string
  status: InfoStatus
  severity: 'high' | 'medium' | 'low'
  source: string
  impact: string[]
  fixAction: string
  route: string
}

type FlowNode = {
  id: string
  lane: '员工' | '系统' | '直属经理' | 'HR'
  title: string
  desc: string
  status: InfoStatus
  source: string
  issueId?: string
}

type PrototypeScreen = {
  id: string
  role: '员工' | '直属经理' | 'HR'
  title: string
  status: InfoStatus
  blocks: string[]
  note: string
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
  needs_confirmation: { label: '待确认', tone: 'warning', desc: '会影响预览、交付或后续修复' },
  conflict: { label: '有冲突', tone: 'danger', desc: '当前信息之间存在不一致' },
  deferred: { label: '暂不确定', tone: 'neutral', desc: '可以保留为导出时待确认项' },
  excluded: { label: '已排除', tone: 'neutral', desc: '已明确不纳入当前方案' },
}

const maturityMeta: Record<DraftMaturity, { label: string; tone: PillTone; desc: string; progress: number }> = {
  initial: { label: '初始草稿', tone: 'warning', desc: '基于一句话和少量上下文，适合看草图式流程和关键假设。', progress: 22 },
  structure: { label: '结构草稿', tone: 'info', desc: '角色和任务基本明确，适合看角色关系和任务地图。', progress: 46 },
  flow: { label: '流程草稿', tone: 'info', desc: '流程和规则基本明确，适合做系统级流程 checkpoint。', progress: 68 },
  delivery: { label: '交付草稿', tone: 'success', desc: '范围、依赖和预览基本确认，可做原型预览和导出前检查。', progress: 84 },
}

const previewStages: Record<PreviewStage, { title: string; desc: string; tone: PillTone; checks: string[] }> = {
  initial: {
    title: '初始草稿 checkpoint',
    desc: '看 AI 当前理解、关键假设和高风险不确定项，不做最终验收。',
    tone: 'warning',
    checks: ['草图式流程', '关键假设', '高风险不确定项'],
  },
  structure: {
    title: '结构草稿 checkpoint',
    desc: '检查角色关系、任务地图和角色缺口。',
    tone: 'info',
    checks: ['角色关系图', '任务地图', '角色缺口'],
  },
  flow: {
    title: '流程草稿 checkpoint',
    desc: '检查系统级流程、流程断点和规则缺口。',
    tone: 'info',
    checks: ['系统级流程图', '流程断点', '规则缺口'],
  },
  delivery: {
    title: '交付草稿 checkpoint',
    desc: '检查低保真原型、问题诊断和导出前准备度。',
    tone: 'success',
    checks: ['低保真原型', '问题诊断', '导出前检查'],
  },
}

const issues: PreviewIssue[] = [
  {
    id: 'hr-boundary',
    title: 'HR 记录结果的系统边界仍不清楚',
    desc: '当前范围把 HR 记录先标为外部依赖，但原型中仍可能需要 HR 视角说明。',
    status: 'needs_confirmation',
    severity: 'high',
    source: '来自页面 04：HR 记录结果是否属于系统内功能',
    impact: ['影响 HR 是否需要系统页面', '影响交付说明', '影响导出时是否带待确认项'],
    fixAction: '确认 HR 记录是系统内功能还是外部依赖。',
    route: '页面 04：范围与交付',
  },
  {
    id: 'return-rule',
    title: '退回后员工下一步仍需确认',
    desc: '当前流程倾向允许修改后再提交，但该规则仍未明确采纳。',
    status: 'needs_confirmation',
    severity: 'medium',
    source: '来自页面 03：退回后如何处理',
    impact: ['影响流程是否回到填写步骤', '影响员工原型是否出现再提交入口', '影响规则候选是否进入正式方案'],
    fixAction: '确认退回后是否允许修改再提交。',
    route: '页面 03：怎么运作',
  },
  {
    id: 'status-view',
    title: '员工是否需要查看状态仍是 AI 假设',
    desc: '基础状态查看已进入本期范围草稿，但仍是 AI 对审批体验闭环的推测。',
    status: 'ai_assumption',
    severity: 'medium',
    source: '来自页面 02：基础状态跟踪能力',
    impact: ['影响员工列表页', '影响通知依赖', '影响第一版是否保持最小闭环'],
    fixAction: '确认员工是否需要基础状态查看。',
    route: '页面 02：要做什么',
  },
  {
    id: 'multi-level',
    title: '多级审批已后置，但需要在导出中说明',
    desc: '多级审批被标为暂不做。导出方案需要说明第一版只做单级审批。',
    status: 'deferred',
    severity: 'low',
    source: '来自页面 04：暂不做',
    impact: ['影响利益相关方预期', '避免误以为第一版支持复杂审批链'],
    fixAction: '导出时保留“暂不做：多级审批”。',
    route: '页面 04：范围与交付',
  },
]

const flowNodes: FlowNode[] = [
  { id: 'fill', lane: '员工', title: '填写请假信息', desc: '选择请假类型、时间和原因。', status: 'confirmed', source: '页面 03 已确认流程' },
  { id: 'submit', lane: '员工', title: '提交申请', desc: '提交后进入待审批。', status: 'confirmed', source: '页面 02 已确认任务' },
  { id: 'create', lane: '系统', title: '创建待审批记录', desc: '系统生成经理待办。', status: 'ai_assumption', source: '页面 03 AI 推导' },
  { id: 'approve', lane: '直属经理', title: '审批申请', desc: '经理通过或退回。', status: 'confirmed', source: '页面 02 已确认任务' },
  { id: 'return', lane: '系统', title: '退回后处理？', desc: '是否允许修改再提交仍待确认。', status: 'needs_confirmation', source: '页面 03 分岔', issueId: 'return-rule' },
  { id: 'notify', lane: '系统', title: '通知员工结果', desc: '审批完成后通知员工。', status: 'ai_assumption', source: '页面 03 体验闭环建议' },
  { id: 'hr', lane: 'HR', title: '记录或接收结果？', desc: '系统内记录还是外部依赖待确认。', status: 'needs_confirmation', source: '页面 04 范围边界', issueId: 'hr-boundary' },
]

const prototypeScreens: PrototypeScreen[] = [
  {
    id: 'employee-list',
    role: '员工',
    title: '我的请假申请',
    status: 'ai_assumption',
    blocks: ['新建请假申请', '待审批 / 已通过 / 已退回状态', '查看审批结果'],
    note: '基础状态查看仍是 AI 假设，建议在页面 02 确认。',
  },
  {
    id: 'employee-form',
    role: '员工',
    title: '提交请假申请',
    status: 'confirmed',
    blocks: ['请假类型', '开始与结束时间', '请假原因', '提交给直属经理'],
    note: '来自已确认核心任务。',
  },
  {
    id: 'manager-detail',
    role: '直属经理',
    title: '审批详情',
    status: 'confirmed',
    blocks: ['申请信息', '通过', '退回', '退回原因'],
    note: '退回原因与再提交规则仍待确认。',
  },
  {
    id: 'hr-record',
    role: 'HR',
    title: 'HR 结果记录',
    status: 'needs_confirmation',
    blocks: ['接收审批结果', '记录到考勤系统', '查看本月记录'],
    note: '如果 HR 记录保持外部依赖，此页面不进入第一版原型。',
  },
]

function severityTone(severity: PreviewIssue['severity']): PillTone {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'neutral'
}

function TopBar() {
  return (
    <div className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">页面 05：预览与验证 · 草稿审查 × 协作探索合一</div>
          <div className="text-xs text-slate-500">不是最终验收页，而是贯穿探索过程的阶段性 checkpoint</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700">查看预览依据</button>
          <button className="rounded-2xl bg-sky-600 px-4 py-2 text-sm font-medium text-white">运行当前 checkpoint</button>
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
            <Pill tone="warning">3 个问题待处理</Pill>
            <Pill tone="success">可做系统级预览</Pill>
            <div className="text-xs font-medium tracking-wide text-slate-500">持续预览与验证 checkpoint</div>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">员工请假申请</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            在真正开发前，先让当前草稿跑一遍，看看流程是否闭环、用户是否知道下一步、第一版范围是否清楚。每个问题都能回到对应页面继续探索和修复。
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
    { label: '范围与交付', maturity: '交付草稿', tone: 'success' as PillTone },
    { label: '预览与验证', active: true, maturity: 'checkpoint', tone: 'info' as PillTone },
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
        页面 05 可在任意阶段使用。它不是终点，而是帮你发现下一步该修哪里。
      </div>
    </aside>
  )
}

function ModeTabs({ view, setView }: { view: MainView; setView: (view: MainView) => void }) {
  const tabs = [
    { key: 'checkpoint', label: '阶段 checkpoint', note: '按成熟度选择预览' },
    { key: 'systemFlow', label: '系统流程', note: '跨角色跑一遍' },
    { key: 'prototype', label: '原型体验', note: '看用户是否知道下一步' },
    { key: 'issues', label: '问题与修复', note: '回跳继续探索' },
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

function StageCard({ stage, selected, onClick }: { stage: PreviewStage; selected: boolean; onClick: () => void }) {
  const item = previewStages[stage]
  return (
    <button onClick={onClick} className={`rounded-3xl p-5 text-left shadow-sm transition hover:-translate-y-0.5 ${selected ? 'bg-sky-50 ring-2 ring-sky-300' : 'bg-white ring-1 ring-slate-200'}`}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-900">{item.title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">{item.desc}</div>
        </div>
        <Pill tone={selected ? 'info' : item.tone}>{selected ? '当前' : '可选'}</Pill>
      </div>
      <div className="grid gap-2">
        {item.checks.map((check) => <div key={check} className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200">{check}</div>)}
      </div>
    </button>
  )
}

function CheckpointView({ stage, setStage }: { stage: PreviewStage; setStage: (stage: PreviewStage) => void }) {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">阶段性 checkpoint</h2>
            <p className="mt-1 text-sm text-slate-500">根据草稿成熟度选择预览深度。越早期越关注假设，越后期越关注原型和交付。</p>
          </div>
          <Pill tone="info">当前：交付草稿 checkpoint</Pill>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          当前已可做系统级流程和低保真原型预览，但仍有 HR 记录边界、退回规则和状态查看 3 个问题需要处理。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {(['initial', 'structure', 'flow', 'delivery'] as PreviewStage[]).map((item) => <StageCard key={item} stage={item} selected={stage === item} onClick={() => setStage(item)} />)}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 text-lg font-semibold text-slate-900">当前 checkpoint 输出</div>
        <div className="grid grid-cols-3 gap-4">
          {previewStages[stage].checks.map((check) => (
            <div key={check} className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <div className="text-sm font-semibold text-slate-900">{check}</div>
              <div className="mt-2 text-sm leading-6 text-slate-600">用于发现当前草稿还缺什么，并回到对应页面继续探索。</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}

function SystemFlowView() {
  const lanes: FlowNode['lane'][] = ['员工', '系统', '直属经理', 'HR']
  const byLane = (lane: FlowNode['lane']) => flowNodes.filter((node) => node.lane === lane)
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">系统级流程图</h2>
            <p className="mt-1 text-sm text-slate-500">把员工、系统、经理和 HR 放在同一张图里，检查当前草稿能不能跑起来。</p>
          </div>
          <div className="flex gap-2"><Pill tone="success">主闭环可跑</Pill><Pill tone="warning">2 个断点</Pill></div>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          当前流程最大风险在 HR 记录边界和退回后处理。点击有标记的节点，可以查看来源和修复入口。
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-4">
          {lanes.map((lane) => (
            <React.Fragment key={lane}>
              <div className="flex items-center justify-center rounded-2xl bg-slate-50 px-3 py-4 text-sm font-semibold text-slate-700 ring-1 ring-slate-200">{lane}</div>
              <div className="grid grid-cols-4 gap-3 rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                {byLane(lane).length > 0 ? byLane(lane).map((node) => {
                  const meta = statusMeta[node.status]
                  return (
                    <div key={node.id} className={`rounded-2xl bg-white p-4 ring-1 ${node.status === 'needs_confirmation' ? 'ring-amber-300' : 'ring-slate-200'}`}>
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <div className="text-sm font-semibold leading-5 text-slate-900">{node.title}</div>
                        <Pill tone={meta.tone}>{meta.label}</Pill>
                      </div>
                      <div className="text-xs leading-5 text-slate-500">{node.desc}</div>
                      <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200">来源：{node.source}</div>
                      {node.issueId ? <button className="mt-3 rounded-xl bg-sky-600 px-3 py-2 text-xs font-medium text-white">查看问题</button> : null}
                    </div>
                  )
                }) : <div className="rounded-2xl border border-dashed border-slate-200 bg-white/60 p-4 text-sm text-slate-400">当前草稿暂无该角色步骤</div>}
              </div>
            </React.Fragment>
          ))}
        </div>
      </section>
    </main>
  )
}

function PrototypeScreenCard({ item }: { item: PrototypeScreen }) {
  const meta = statusMeta[item.status]
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="text-base font-semibold text-slate-900">{item.title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-500">角色：{item.role}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="rounded-3xl bg-slate-50 p-4 ring-1 ring-slate-200">
        <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
          <div className="mb-3 h-3 w-24 rounded-full bg-slate-200" />
          <div className="space-y-2">
            {item.blocks.map((block) => <div key={block} className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200">{block}</div>)}
          </div>
        </div>
      </div>
      <div className="mt-3 rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">{item.note}</div>
    </div>
  )
}

function PrototypeView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">低保真原型体验</h2>
            <p className="mt-1 text-sm text-slate-500">不是高保真 UI，而是检查每个角色是否知道下一步，以及第一版边界是否清楚。</p>
          </div>
          <Pill tone="warning">HR 视角待确认</Pill>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          原型中的待确认页面不会自动进入正式方案。只有确认 HR 记录属于系统内功能，HR 记录页才会进入第一版。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {prototypeScreens.map((item) => <PrototypeScreenCard key={item.id} item={item} />)}
      </section>
    </main>
  )
}

function IssueCard({ item }: { item: PreviewIssue }) {
  const meta = statusMeta[item.status]
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="text-base font-semibold text-slate-900">{item.title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-500">{item.source}</div>
        </div>
        <div className="flex flex-wrap justify-end gap-2"><Pill tone={severityTone(item.severity)}>{item.severity === 'high' ? '高影响' : item.severity === 'medium' ? '中影响' : '低影响'}</Pill><Pill tone={meta.tone}>{meta.label}</Pill></div>
      </div>
      <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">{item.desc}</div>
      <div className="mt-3 grid gap-2">
        {item.impact.map((impact) => <div key={impact} className="rounded-xl bg-white px-3 py-2 text-sm leading-5 text-slate-700 ring-1 ring-slate-200">{impact}</div>)}
      </div>
      <div className="mt-3 rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">建议：{item.fixAction}</div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">去{item.route}</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">直接采纳修复</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">保留待确认</button>
      </div>
    </div>
  )
}

function IssuesView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">问题与修复</h2>
            <p className="mt-1 text-sm text-slate-500">问题不是终点，而是回到页面 02 / 03 / 04 继续探索的入口。</p>
          </div>
          <div className="flex gap-2"><Pill tone="danger">1 个高影响</Pill><Pill tone="warning">2 个中影响</Pill></div>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          当前方案可以导出为带待确认项版本，但建议先处理 HR 记录边界和退回后处理，再进入正式交付。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {issues.map((item) => <IssueCard key={item.id} item={item} />)}
      </section>
    </main>
  )
}

function RightRail({ setView }: { setView: (view: MainView) => void }) {
  return (
    <aside className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">当前诊断摘要</div>
        <div className="grid gap-3">
          <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200"><div className="text-sm font-semibold text-slate-900">主流程</div><div className="mt-1 text-sm text-slate-600">可形成最小闭环</div></div>
          <div className="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-200"><div className="text-sm font-semibold text-slate-900">关键风险</div><div className="mt-1 text-sm leading-6 text-amber-800">HR 记录边界和退回规则仍待确认</div></div>
          <div className="rounded-2xl bg-sky-50 p-4 ring-1 ring-sky-200"><div className="text-sm font-semibold text-slate-900">建议下一步</div><div className="mt-1 text-sm leading-6 text-sky-800">先处理高影响问题，再导出方案</div></div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">高影响问题</div>
        <button onClick={() => setView('issues')} className="w-full rounded-2xl bg-amber-50 p-4 text-left ring-1 ring-amber-200 hover:bg-amber-100">
          <div className="text-sm font-semibold text-slate-900">HR 记录结果的系统边界仍不清楚</div>
          <div className="mt-2 text-sm leading-6 text-amber-800">影响 HR 视角、记录页面和交付说明。</div>
          <div className="mt-3"><Pill tone="danger">高影响</Pill></div>
        </button>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">AI 可以帮你</div>
        <div className="space-y-2">
          {[
            ['解释当前预览问题', 'info'],
            ['生成更轻的 HR 处理方案', 'neutral'],
            ['导出带待确认项方案', 'neutral'],
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
    view === 'checkpoint'
      ? '例如：帮我判断现在适合做哪种 checkpoint'
      : view === 'systemFlow'
        ? '例如：从当前系统流程里找断点'
        : view === 'prototype'
          ? '例如：员工在这个原型里是否知道下一步？'
          : '例如：先帮我修复最高影响问题'

  return (
    <div className="fixed bottom-5 left-1/2 z-10 w-[780px] -translate-x-1/2 rounded-3xl border border-slate-200 bg-white/95 px-5 py-4 shadow-xl backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 ring-1 ring-sky-200">页面 05：预览与验证</div>
        <input className="h-11 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none" placeholder={placeholder} />
        <button className="rounded-2xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white">AI 帮我推进</button>
      </div>
    </div>
  )
}

export default function LitePage05IntegratedDraftExploration() {
  const [view, setView] = useState<MainView>('checkpoint')
  const [stage, setStage] = useState<PreviewStage>('delivery')
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
              {view === 'checkpoint' ? <CheckpointView stage={stage} setStage={setStage} /> : view === 'systemFlow' ? <SystemFlowView /> : view === 'prototype' ? <PrototypeView /> : <IssuesView />}
            </div>
            <RightRail setView={setView} />
          </div>
        </div>
        <FloatingAI view={view} />
      </div>
    </div>
  )
}
