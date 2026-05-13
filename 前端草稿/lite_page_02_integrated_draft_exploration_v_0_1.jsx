import React, { useMemo, useState } from 'react'

type PillTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
type DraftMaturity = 'initial' | 'structure' | 'flow' | 'delivery'
type InfoStatus = 'confirmed' | 'ai_assumption' | 'needs_confirmation' | 'conflict' | 'deferred' | 'excluded'
type MainView = 'roles' | 'decision' | 'tasks' | 'capabilities'
type RoleOption = 'hr_record' | 'hr_approve' | 'hr_conditional' | 'uncertain'

type Actor = {
  id: string
  name: string
  responsibility: string
  status: InfoStatus
  source: string
}

type Task = {
  id: string
  title: string
  actor: string
  outcome: string
  status: InfoStatus
  type: 'primary' | 'supporting' | 'deferred'
  dependsOn?: string
}

type Capability = {
  id: string
  title: string
  desc: string
  status: InfoStatus
  recommendation: '建议保留' | '待确认' | '建议后置'
  impact: string
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
  initial: { label: '初始草稿', tone: 'warning', desc: '基于一句话和少量上下文，假设较多。', progress: 22 },
  structure: { label: '结构草稿', tone: 'info', desc: '角色和任务正在形成，适合确认关键分岔。', progress: 42 },
  flow: { label: '流程草稿', tone: 'info', desc: '流程和规则基本明确，范围仍待收敛。', progress: 68 },
  delivery: { label: '交付草稿', tone: 'success', desc: '范围、依赖和预览基本确认。', progress: 84 },
}

const actors: Actor[] = [
  { id: 'employee', name: '员工', responsibility: '提交请假申请，并查看审批结果。', status: 'confirmed', source: '来自用户输入“员工提交请假申请”' },
  { id: 'manager', name: '直属经理', responsibility: '审批员工提交的请假申请。', status: 'confirmed', source: '来自用户输入“经理审批”' },
  { id: 'hr', name: 'HR', responsibility: '接收审批结果或记录结果，是否参与审批待确认。', status: 'needs_confirmation', source: '来自用户输入“通知 HR”，AI 暂未判断责任边界' },
  { id: 'system', name: '系统', responsibility: '创建记录、更新状态、发送通知。', status: 'ai_assumption', source: 'AI 根据审批类应用自动推导' },
]

const tasks: Task[] = [
  { id: 'submit', title: '提交请假申请', actor: '员工', outcome: '生成一条待审批申请', status: 'confirmed', type: 'primary' },
  { id: 'approve', title: '审批请假申请', actor: '直属经理', outcome: '申请被通过或退回', status: 'confirmed', type: 'primary' },
  { id: 'view-result', title: '查看审批结果', actor: '员工', outcome: '员工知道申请是否通过', status: 'ai_assumption', type: 'primary', dependsOn: '是否需要状态查看' },
  { id: 'notify-hr', title: '通知 HR 审批结果', actor: '系统 / HR', outcome: 'HR 知道需要记录或处理', status: 'needs_confirmation', type: 'supporting', dependsOn: 'HR 的角色责任' },
  { id: 'hr-record', title: '记录审批结果', actor: 'HR', outcome: '审批结果被同步或记录', status: 'needs_confirmation', type: 'supporting', dependsOn: '是否纳入系统内功能' },
  { id: 'history', title: '查看历史申请', actor: '员工 / HR', outcome: '可回看历史记录', status: 'deferred', type: 'deferred', dependsOn: '第一版范围' },
]

const capabilities: Capability[] = [
  {
    id: 'notification',
    title: '通知与确认',
    desc: '审批完成后通知员工，必要时通知 HR。',
    status: 'ai_assumption',
    recommendation: '建议保留',
    impact: '缺少通知会让员工不知道结果，也会影响 HR 是否能及时记录。',
  },
  {
    id: 'status',
    title: '基础状态跟踪',
    desc: '显示待审批、已通过、已退回等基础状态。',
    status: 'ai_assumption',
    recommendation: '待确认',
    impact: '会影响员工是否需要主动查看申请进度。',
  },
  {
    id: 'record',
    title: '记录与查询',
    desc: '保存审批结果，支持后续查看或人工同步。',
    status: 'needs_confirmation',
    recommendation: '待确认',
    impact: '会影响 HR 是否需要系统内记录页，以及页面 04 范围复杂度。',
  },
  {
    id: 'advanced-report',
    title: '高级统计报表',
    desc: '按部门、时间、请假类型做统计分析。',
    status: 'deferred',
    recommendation: '建议后置',
    impact: '第一版用户价值有限，容易让 Lite 应用变重。',
  },
]

function TopBar() {
  return (
    <div className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">页面 02：要做什么 · 草稿审查 × 协作探索合一</div>
          <div className="text-xs text-slate-500">围绕当前草稿中的角色、任务和能力假设逐步展开，不一次性生成完整任务树</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700">查看任务依据</button>
          <button className="rounded-2xl bg-sky-600 px-4 py-2 text-sm font-medium text-white">生成任务候选</button>
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
            <Pill tone="warning">HR 角色待确认</Pill>
            <Pill tone="info">任务候选可生成</Pill>
            <div className="text-xs font-medium tracking-wide text-slate-500">角色和任务共创</div>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">员工请假申请</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            本页不让 AI 一次性替你决定全部任务，而是先确认角色责任，再生成局部任务候选。每确认一个关键角色，后续流程和范围就更不容易跑偏。
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
    { label: '要做什么', active: true, maturity: '结构草稿', tone: 'info' as PillTone },
    { label: '怎么运作', maturity: '待任务确认', tone: 'neutral' as PillTone },
    { label: '范围与交付', maturity: '待流程', tone: 'neutral' as PillTone },
    { label: '预览与验证', maturity: '可看草图', tone: 'info' as PillTone },
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
        页面 02 只推进角色和任务层级；流程、规则和范围将在确认后继续生长。
      </div>
    </aside>
  )
}

function ModeTabs({ view, setView }: { view: MainView; setView: (view: MainView) => void }) {
  const tabs = [
    { key: 'roles', label: '角色假设', note: '谁参与，以及责任边界' },
    { key: 'decision', label: '关键分岔', note: '先确认 HR 的角色' },
    { key: 'tasks', label: '任务候选', note: '基于已确认角色生成' },
    { key: 'capabilities', label: '辅助能力', note: '通知、状态、记录等能力' },
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

function ActorCard({ actor }: { actor: Actor }) {
  const meta = statusMeta[actor.status]
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="text-base font-semibold text-slate-900">{actor.name}</div>
          <div className="mt-1 text-sm leading-6 text-slate-500">{actor.source}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">{actor.responsibility}</div>
      {actor.id === 'hr' ? (
        <div className="mt-3 rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          先确认 HR 的角色，可以避免后续流程、规则、范围和原型一起跑偏。
        </div>
      ) : null}
    </div>
  )
}

function RolesView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">角色假设</h2>
            <p className="mt-1 text-sm text-slate-500">先看当前草稿中有哪些参与者，哪些来自用户输入，哪些是 AI 推测。</p>
          </div>
          <div className="flex gap-2"><Pill tone="success">2 个已确认</Pill><Pill tone="warning">1 个待确认</Pill><Pill tone="info">1 个 AI 推测</Pill></div>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          当前最重要的分岔是 HR 的责任：如果 HR 只是接收 / 记录结果，第一版可以保持轻；如果 HR 也审批，流程会变成两级审批。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {actors.map((actor) => <ActorCard key={actor.id} actor={actor} />)}
      </section>
    </main>
  )
}

function DecisionOption({ selected, title, desc, impacts, onClick, tone = 'neutral' }: { selected: boolean; title: string; desc: string; impacts: string[]; onClick: () => void; tone?: PillTone }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-3xl p-5 text-left shadow-sm transition hover:-translate-y-0.5 ${selected ? 'bg-sky-50 ring-2 ring-sky-300' : 'bg-white ring-1 ring-slate-200'}`}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-slate-900">{title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">{desc}</div>
        </div>
        <Pill tone={selected ? 'info' : tone}>{selected ? '当前选择' : '可选'}</Pill>
      </div>
      <div className="space-y-2">
        {impacts.map((impact) => (
          <div key={impact} className="rounded-xl bg-slate-50 px-3 py-2 text-sm leading-5 text-slate-700 ring-1 ring-slate-200">{impact}</div>
        ))}
      </div>
    </button>
  )
}

function DecisionView({ option, setOption }: { option: RoleOption; setOption: (option: RoleOption) => void }) {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-slate-900">关键分岔：HR 在这个应用里做什么？</h2>
          <p className="mt-1 text-sm text-slate-500">每次只确认一个关键问题。这个判断会影响任务、流程、范围和预览。</p>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          AI 建议：第一版先让 HR 只接收 / 记录结果，不参与审批。这样可以保持单级审批，降低第一版复杂度。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        <DecisionOption
          selected={option === 'hr_record'}
          title="HR 只接收 / 记录结果"
          desc="HR 不参与审批，只在审批完成后知道结果并进行记录或人工同步。"
          impacts={['流程保持单级审批', '页面 04 范围更轻', '页面 05 原型不需要 HR 审批页']}
          onClick={() => setOption('hr_record')}
          tone="success"
        />
        <DecisionOption
          selected={option === 'hr_approve'}
          title="HR 也参与审批"
          desc="直属经理审批后，还需要 HR 再审批或确认。"
          impacts={['流程变成两级审批', '需要新增 HR 审批任务', '规则和原型复杂度上升']}
          onClick={() => setOption('hr_approve')}
          tone="warning"
        />
        <DecisionOption
          selected={option === 'hr_conditional'}
          title="特定条件下 HR 参与"
          desc="例如超过一定天数、特殊请假类型或部门规则触发 HR 参与。"
          impacts={['需要定义触发条件', '流程会出现分支', '适合后续增强或真实验证']}
          onClick={() => setOption('hr_conditional')}
          tone="info"
        />
        <DecisionOption
          selected={option === 'uncertain'}
          title="暂时不确定"
          desc="先保留 HR 角色待确认，不阻塞当前任务探索，但流程和范围需要标记不确定。"
          impacts={['可以继续看任务候选', '流程草稿会保留 HR 分岔', '导出时会带待确认项']}
          onClick={() => setOption('uncertain')}
          tone="neutral"
        />
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">确认后将生成的局部对象</div>
        <div className="grid grid-cols-3 gap-3">
          {['HR 责任边界', '相关任务候选', '流程影响提示'].map((item) => (
            <div key={item} className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">{item}</div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white">采纳当前选择并生成任务候选</button>
          <button className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700">只保存为待确认</button>
        </div>
      </section>
    </main>
  )
}

function TaskCard({ task }: { task: Task }) {
  const meta = statusMeta[task.status]
  const typeTone: PillTone = task.type === 'primary' ? 'info' : task.type === 'supporting' ? 'success' : 'neutral'
  const typeLabel = task.type === 'primary' ? '核心任务' : task.type === 'supporting' ? '辅助任务' : '后置任务'
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="text-base font-semibold text-slate-900">{task.title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-500">角色：{task.actor}</div>
        </div>
        <div className="flex flex-wrap justify-end gap-2"><Pill tone={typeTone}>{typeLabel}</Pill><Pill tone={meta.tone}>{meta.label}</Pill></div>
      </div>
      <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">结果：{task.outcome}</div>
      {task.dependsOn ? <div className="mt-3 rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">依赖：{task.dependsOn}</div> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">采纳</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">修改</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">后置</button>
      </div>
    </div>
  )
}

function TasksView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">任务候选</h2>
            <p className="mt-1 text-sm text-slate-500">任务基于已知角色和当前 HR 假设生成。未确认项不会自动进入正式方案。</p>
          </div>
          <Pill tone="warning">2 个依赖 HR 判断</Pill>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          先保留最小闭环：提交申请、经理审批、员工知道结果。HR 记录、历史查询等能力可根据范围继续收敛。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {tasks.map((task) => <TaskCard key={task.id} task={task} />)}
      </section>
    </main>
  )
}

function CapabilityCard({ item }: { item: Capability }) {
  const meta = statusMeta[item.status]
  const recTone: PillTone = item.recommendation === '建议保留' ? 'success' : item.recommendation === '待确认' ? 'warning' : 'neutral'
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="text-base font-semibold text-slate-900">{item.title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">{item.desc}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">{item.impact}</div>
      <div className="mt-3"><Pill tone={recTone}>{item.recommendation}</Pill></div>
    </div>
  )
}

function CapabilitiesView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-slate-900">辅助能力</h2>
          <p className="mt-1 text-sm text-slate-500">辅助能力不是越多越好。这里用于判断哪些帮助形成最小闭环，哪些应后置。</p>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          建议第一版优先保留“通知与确认”，谨慎处理“记录与查询”，后置“高级统计报表”。
        </div>
      </section>
      <section className="grid grid-cols-2 gap-6">
        {capabilities.map((item) => <CapabilityCard key={item.id} item={item} />)}
      </section>
    </main>
  )
}

function RightRail({ view, setView }: { view: MainView; setView: (view: MainView) => void }) {
  return (
    <aside className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">当前关键分岔</div>
        <div className="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-200">
          <div className="text-sm font-semibold text-slate-900">HR 是审批人，还是只接收 / 记录结果？</div>
          <div className="mt-2 text-sm leading-6 text-amber-800">这个判断会影响任务、流程、范围和页面 05 原型。</div>
          <button onClick={() => setView('decision')} className="mt-3 rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">去确认</button>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">角色状态</div>
        <div className="space-y-3">
          {actors.map((actor) => {
            const meta = statusMeta[actor.status]
            return (
              <button key={actor.id} onClick={() => setView('roles')} className="w-full rounded-2xl bg-slate-50 p-4 text-left ring-1 ring-slate-200 hover:bg-slate-100">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-900">{actor.name}</div>
                  <Pill tone={meta.tone}>{meta.label}</Pill>
                </div>
              </button>
            )
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">AI 可以帮你</div>
        <div className="space-y-2">
          {[
            ['解释 HR 分岔影响', 'info'],
            ['生成最小任务闭环', 'neutral'],
            ['标记可后置任务', 'neutral'],
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
    view === 'roles'
      ? '例如：帮我解释每个角色目前哪些是确定的'
      : view === 'decision'
        ? '例如：如果 HR 也审批，会增加哪些任务？'
        : view === 'tasks'
          ? '例如：只保留最小闭环任务'
          : '例如：哪些辅助能力适合第一版后置？'

  return (
    <div className="fixed bottom-5 left-1/2 z-10 w-[780px] -translate-x-1/2 rounded-3xl border border-slate-200 bg-white/95 px-5 py-4 shadow-xl backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 ring-1 ring-sky-200">页面 02：要做什么</div>
        <input className="h-11 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none" placeholder={placeholder} />
        <button className="rounded-2xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white">AI 帮我推进</button>
      </div>
    </div>
  )
}

export default function LitePage02IntegratedDraftExploration() {
  const [view, setView] = useState<MainView>('roles')
  const [option, setOption] = useState<RoleOption>('hr_record')
  const maturity = useMemo<DraftMaturity>(() => 'structure', [])

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
              {view === 'roles' ? <RolesView /> : view === 'decision' ? <DecisionView option={option} setOption={setOption} /> : view === 'tasks' ? <TasksView /> : <CapabilitiesView />}
            </div>
            <RightRail view={view} setView={setView} />
          </div>
        </div>
        <FloatingAI view={view} />
      </div>
    </div>
  )
}
