import React, { useMemo, useState } from 'react'

type PillTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
type DraftMaturity = 'initial' | 'structure' | 'flow' | 'delivery'
type InfoStatus = 'confirmed' | 'ai_assumption' | 'needs_confirmation' | 'conflict' | 'deferred' | 'excluded'
type MainView = 'current' | 'assumptions' | 'draft' | 'next'

type Assumption = {
  id: string
  title: string
  status: InfoStatus
  source: string
  impact: string[]
  recommendedAction: string
  route: string
}

type KnownFact = {
  id: string
  label: string
  value: string
  status: InfoStatus
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
  needs_confirmation: { label: '待确认', tone: 'warning', desc: '会影响后续任务、流程或范围' },
  conflict: { label: '有冲突', tone: 'danger', desc: '当前信息之间存在不一致' },
  deferred: { label: '暂不确定', tone: 'neutral', desc: '可以先保留，不阻塞当前探索' },
  excluded: { label: '已排除', tone: 'neutral', desc: '已明确不纳入当前方案' },
}

const maturityMeta: Record<DraftMaturity, { label: string; tone: PillTone; desc: string; progress: number }> = {
  initial: {
    label: '初始草稿',
    tone: 'warning',
    desc: '基于一句话和少量上下文，假设较多，适合先找关键分岔。',
    progress: 22,
  },
  structure: {
    label: '结构草稿',
    tone: 'info',
    desc: '角色和任务基本明确，流程与规则仍待确认。',
    progress: 46,
  },
  flow: {
    label: '流程草稿',
    tone: 'info',
    desc: '流程和规则基本明确，范围仍待收敛。',
    progress: 68,
  },
  delivery: {
    label: '交付草稿',
    tone: 'success',
    desc: '范围、依赖和预览基本确认，可导出为带待确认项的方案。',
    progress: 84,
  },
}

const knownFacts: KnownFact[] = [
  { id: 'idea', label: '用户想法', value: '员工提交请假申请，经理审批后通知 HR。', status: 'confirmed' },
  { id: 'type', label: '应用类型', value: '申请与审批类轻应用', status: 'ai_assumption' },
  { id: 'initiator', label: '发起人', value: '员工', status: 'confirmed' },
  { id: 'handler', label: '处理人', value: '直属经理', status: 'confirmed' },
  { id: 'hr', label: 'HR 角色', value: '接收结果 / 记录结果，是否审批待确认', status: 'needs_confirmation' },
  { id: 'version', label: '第一版倾向', value: '单级审批，暂不做复杂审批链', status: 'ai_assumption' },
]

const assumptions: Assumption[] = [
  {
    id: 'hr-role',
    title: 'HR 只接收结果，不参与审批',
    status: 'needs_confirmation',
    source: '来自“通知 HR”的用户描述，AI 暂未判断 HR 是否审批。',
    impact: ['影响审批流程是否为单级或两级', '影响是否需要 HR 审批页面', '影响页面 04 第一版范围复杂度'],
    recommendedAction: '先确认 HR 的角色，再生成完整流程。',
    route: '页面 02：要做什么',
  },
  {
    id: 'single-approval',
    title: '第一版只做单级审批',
    status: 'ai_assumption',
    source: 'Lite 轻应用默认建议先保持最小闭环。',
    impact: ['流程更短', '规则更少', '页面 05 原型更容易闭环'],
    recommendedAction: '若组织确实需要多级审批，再在页面 04 标记为后续增强或本期范围。',
    route: '页面 04：范围与交付',
  },
  {
    id: 'status-view',
    title: '员工需要查看审批状态',
    status: 'ai_assumption',
    source: '审批类应用通常需要反馈状态，但用户尚未明确提出。',
    impact: ['影响任务候选：查看申请结果', '影响流程：状态变化', '影响原型：员工列表页'],
    recommendedAction: '在页面 02 确认是否需要基础状态查看。',
    route: '页面 02：要做什么',
  },
  {
    id: 'return-resubmit',
    title: '退回后允许员工修改再提交',
    status: 'needs_confirmation',
    source: '审批流程常见分支，但用户未说明退回处理。',
    impact: ['影响规则：退回后处理', '影响流程：是否回到填写步骤', '影响原型：是否出现“修改后再提交”入口'],
    recommendedAction: '在页面 03 确认退回后处理规则。',
    route: '页面 03：怎么运作',
  },
]

function TopBar() {
  return (
    <div className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">页面 01：概览 · 草稿审查 × 协作探索合一</div>
          <div className="text-xs text-slate-500">工作台本身承载草稿、假设、确认、预览和下一步探索</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700">查看草稿依据</button>
          <button className="rounded-2xl bg-sky-600 px-4 py-2 text-sm font-medium text-white">生成当前草稿</button>
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
            <Pill tone="warning">4 个关键假设</Pill>
            <Pill tone="info">可生成草图预览</Pill>
            <div className="text-xs font-medium tracking-wide text-slate-500">当前方案控制台</div>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">员工请假申请</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            先快速看见一个草稿，再看清它基于哪些假设。每确认一步，草稿就更可靠；每一次预览，都能发现下一步该修哪里。
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
    { label: '概览', active: true, maturity: '初始草稿', tone: 'warning' as PillTone },
    { label: '要做什么', maturity: '待展开', tone: 'neutral' as PillTone },
    { label: '怎么运作', maturity: '待前置信息', tone: 'neutral' as PillTone },
    { label: '范围与交付', maturity: '待流程', tone: 'neutral' as PillTone },
    { label: '预览与验证', maturity: '可看草图', tone: 'info' as PillTone },
  ]
  return (
    <aside className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 px-2 text-xs font-semibold tracking-wide text-slate-500">工作台视角</div>
      <nav className="space-y-2">
        {nav.map((item) => (
          <button
            key={item.label}
            className={`w-full rounded-2xl px-3 py-3 text-left ${item.active ? 'bg-sky-50 ring-1 ring-sky-200' : 'bg-slate-50 hover:bg-slate-100'}`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className={`text-sm font-medium ${item.active ? 'text-sky-800' : 'text-slate-800'}`}>{item.label}</div>
              <Pill tone={item.tone}>{item.maturity}</Pill>
            </div>
          </button>
        ))}
      </nav>
      <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-xs leading-5 text-slate-500 ring-1 ring-slate-200">
        这些不是强制步骤，而是检查当前草稿的不同视角。确认越多，草稿越收敛。
      </div>
    </aside>
  )
}

function ModeTabs({ view, setView }: { view: MainView; setView: (view: MainView) => void }) {
  const tabs = [
    { key: 'current', label: '当前状态', note: '已知信息与成熟度' },
    { key: 'draft', label: '当前草稿', note: '阶段性投影' },
    { key: 'assumptions', label: '假设显影', note: '影响与分岔' },
    { key: 'next', label: '下一步探索', note: '从假设进入工作台' },
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

function StatusLegend() {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 text-sm font-semibold text-slate-900">信息状态</div>
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(statusMeta).map(([key, meta]) => (
          <div key={key} className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
            <div className="mb-2"><Pill tone={meta.tone}>{meta.label}</Pill></div>
            <div className="text-xs leading-5 text-slate-500">{meta.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function FactCard({ fact }: { fact: KnownFact }) {
  const meta = statusMeta[fact.status]
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="text-sm font-semibold text-slate-900">{fact.label}</div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="text-sm leading-6 text-slate-700">{fact.value}</div>
    </div>
  )
}

function CurrentStateView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">当前状态</h2>
            <p className="mt-1 text-sm text-slate-500">这里同时显示已确认信息和 AI 假设，避免草稿边界模糊。</p>
          </div>
          <div className="flex gap-2"><Pill tone="success">3 项已确认</Pill><Pill tone="warning">2 项待确认</Pill><Pill tone="info">2 项 AI 假设</Pill></div>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          当前草稿不是最终方案。它是基于已知信息生成的阶段性投影；确认关键假设后，后续任务、流程、范围和预览会继续收敛。
        </div>
      </section>

      <section className="grid grid-cols-3 gap-4 rounded-3xl border border-slate-200 bg-slate-50 p-5 shadow-sm">
        {knownFacts.map((fact) => <FactCard key={fact.id} fact={fact} />)}
      </section>

      <StatusLegend />
    </main>
  )
}

function DraftProjectionView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">当前草稿投影</h2>
            <p className="mt-1 text-sm text-slate-500">草稿在工作台内生成和审查，不跳转到独立前厅。</p>
          </div>
          <Pill tone="warning">初始草稿</Pill>
        </div>
        <div className="rounded-3xl bg-slate-50 p-5 ring-1 ring-slate-200">
          <div className="mb-3 text-sm font-semibold text-slate-900">AI 当前草稿</div>
          <div className="text-base leading-8 text-slate-800">
            这是一个申请与审批类轻应用。员工提交请假申请，直属经理审批，审批完成后通知员工，并可能通知 HR 记录结果。
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
              <div className="mb-2 text-xs font-semibold tracking-wide text-slate-400">草稿依据</div>
              <div className="text-sm leading-6 text-slate-700">用户一句话、员工、经理、HR 通知意图</div>
            </div>
            <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
              <div className="mb-2 text-xs font-semibold tracking-wide text-slate-400">主要假设</div>
              <div className="text-sm leading-6 text-slate-700">HR 不审批、单级审批、员工可查看状态</div>
            </div>
            <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
              <div className="mb-2 text-xs font-semibold tracking-wide text-slate-400">当前风险</div>
              <div className="text-sm leading-6 text-slate-700">HR 角色不清会影响流程、范围和原型</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-[minmax(0,1fr)_360px] gap-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 text-lg font-semibold text-slate-900">草图式流程</div>
          <div className="grid grid-cols-5 gap-3">
            {['员工填写申请', '员工提交', '经理审批', '通知员工', 'HR 记录？'].map((step, index) => (
              <div key={step} className="rounded-2xl bg-slate-50 p-4 text-center ring-1 ring-slate-200">
                <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-white text-xs font-semibold text-slate-700 ring-1 ring-slate-200">{index + 1}</div>
                <div className="text-sm font-semibold leading-5 text-slate-900">{step}</div>
                <div className="mt-3"><Pill tone={step.includes('？') ? 'warning' : index < 2 ? 'success' : 'info'}>{step.includes('？') ? '待确认' : index < 2 ? '已知' : 'AI 推测'}</Pill></div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-3xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
          <div className="mb-2 text-sm font-semibold text-slate-900">草稿不会自动回写</div>
          <div className="text-sm leading-6 text-amber-800">
            当前草稿只是阶段性投影。只有你点击“采纳”“修改后采纳”或“标记已确认”，它才会进入正式对象空间。
          </div>
          <button className="mt-4 rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">基于草稿继续探索</button>
        </div>
      </section>
    </main>
  )
}

function AssumptionCard({ item }: { item: Assumption }) {
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
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">暂不确定</button>
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
            <h2 className="text-xl font-semibold text-slate-900">假设显影</h2>
            <p className="mt-1 text-sm text-slate-500">这些是假设，不是结论。确认或修改它们，可以避免后面的流程和范围跑偏。</p>
          </div>
          <Pill tone="warning">2 个关键待确认</Pill>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          最建议先确认“HR 是否参与审批”。这个判断会影响任务、流程、范围和预览，是当前草稿的第一个关键分岔。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {assumptions.map((item) => <AssumptionCard key={item.id} item={item} />)}
      </section>
    </main>
  )
}

function NextExplorationView() {
  const steps = [
    {
      title: '先确认 HR 的角色',
      desc: '这会决定流程是单级审批，还是需要 HR 参与审批。',
      page: '页面 02：要做什么',
      primary: true,
    },
    {
      title: '确认员工是否需要查看状态',
      desc: '这会影响任务候选、状态规则和员工原型。',
      page: '页面 02：要做什么',
      primary: false,
    },
    {
      title: '确认退回后处理',
      desc: '这会影响审批流程分支和是否需要“修改后再提交”。',
      page: '页面 03：怎么运作',
      primary: false,
    },
    {
      title: '看一个当前草图预览',
      desc: '先跑一遍当前草稿，看看最大的不确定点在哪里。',
      page: '页面 05：预览与验证',
      primary: false,
    },
  ]

  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-slate-900">下一步探索</h2>
          <p className="mt-1 text-sm text-slate-500">草稿揭示的问题就是后续探索入口。每次只确认一个关键分岔。</p>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          建议先确认 HR 的角色。这样后续生成任务、流程和范围时，不会因为角色判断错误而牵一发动全身。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {steps.map((step, index) => (
          <div key={step.title} className={`rounded-3xl border p-5 shadow-sm ${step.primary ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-white'}`}>
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <div className="text-base font-semibold text-slate-900">{index + 1}. {step.title}</div>
                <div className="mt-1 text-sm leading-6 text-slate-600">{step.desc}</div>
              </div>
              <Pill tone={step.primary ? 'info' : 'neutral'}>{step.page}</Pill>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">开始确认</button>
              <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">稍后处理</button>
            </div>
          </div>
        ))}
      </section>
    </main>
  )
}

function RightRail({ setView }: { setView: (view: MainView) => void }) {
  return (
    <aside className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">假设账本</div>
        <div className="space-y-3">
          {assumptions.map((item) => {
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
        <div className="mb-3 text-sm font-semibold text-slate-900">草稿依据</div>
        <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">
          当前草稿主要依据用户的一句话、员工与经理两个明确角色，以及“通知 HR”的业务意图。HR 的责任边界仍待确认。
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">建议动作</div>
        <div className="space-y-2">
          {[
            ['确认 HR 的角色', 'info'],
            ['生成当前草图预览', 'neutral'],
            ['解释单级审批假设', 'neutral'],
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
    view === 'current'
      ? '例如：帮我解释当前草稿里哪些是假设'
      : view === 'draft'
        ? '例如：基于当前信息生成一个更保守的草稿'
        : view === 'assumptions'
          ? '例如：如果 HR 也审批，会影响哪些页面？'
          : '例如：带我从 HR 角色开始确认'

  return (
    <div className="fixed bottom-5 left-1/2 z-10 w-[780px] -translate-x-1/2 rounded-3xl border border-slate-200 bg-white/95 px-5 py-4 shadow-xl backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 ring-1 ring-sky-200">页面 01：当前方案</div>
        <input className="h-11 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none" placeholder={placeholder} />
        <button className="rounded-2xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white">AI 帮我推进</button>
      </div>
    </div>
  )
}

export default function LitePage01IntegratedDraftExploration() {
  const [view, setView] = useState<MainView>('current')
  const maturity = useMemo<DraftMaturity>(() => 'initial', [])

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
              {view === 'current' ? <CurrentStateView /> : view === 'draft' ? <DraftProjectionView /> : view === 'assumptions' ? <AssumptionsView /> : <NextExplorationView />}
            </div>
            <RightRail setView={setView} />
          </div>
        </div>
        <FloatingAI view={view} />
      </div>
    </div>
  )
}
