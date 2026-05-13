import React, { useMemo, useState } from 'react'

type PillTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
type DraftMaturity = 'initial' | 'structure' | 'flow' | 'delivery'
type InfoStatus = 'confirmed' | 'ai_assumption' | 'needs_confirmation' | 'conflict' | 'deferred' | 'excluded'
type MainView = 'flow' | 'branch' | 'rules' | 'preview'
type ReturnRule = 'allow_resubmit' | 'reject_final' | 'manager_note' | 'uncertain'

type FlowStep = {
  id: string
  title: string
  actor: string
  desc: string
  status: InfoStatus
  source: string
  affectedBy?: string
}

type RuleCandidate = {
  id: string
  title: string
  desc: string
  status: InfoStatus
  source: string
  impact: string[]
  relatedStep: string
}

type BranchPoint = {
  id: string
  title: string
  question: string
  status: InfoStatus
  options: string[]
  impact: string
  route: string
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
  needs_confirmation: { label: '待确认', tone: 'warning', desc: '会影响后续流程、规则或范围' },
  conflict: { label: '有冲突', tone: 'danger', desc: '当前信息之间存在不一致' },
  deferred: { label: '暂不确定', tone: 'neutral', desc: '可以先保留，不阻塞当前探索' },
  excluded: { label: '已排除', tone: 'neutral', desc: '已明确不纳入当前方案' },
}

const maturityMeta: Record<DraftMaturity, { label: string; tone: PillTone; desc: string; progress: number }> = {
  initial: { label: '初始草稿', tone: 'warning', desc: '基于一句话和少量上下文，假设较多。', progress: 22 },
  structure: { label: '结构草稿', tone: 'info', desc: '角色和任务基本明确，流程仍待确认。', progress: 46 },
  flow: { label: '流程草稿', tone: 'info', desc: '流程和规则正在形成，适合确认关键分支。', progress: 64 },
  delivery: { label: '交付草稿', tone: 'success', desc: '范围、依赖和预览基本确认。', progress: 84 },
}

const flowSteps: FlowStep[] = [
  {
    id: 'fill',
    title: '员工填写请假信息',
    actor: '员工',
    desc: '填写请假类型、开始时间、结束时间和原因。',
    status: 'confirmed',
    source: '来自已确认任务：员工提交请假申请',
  },
  {
    id: 'submit',
    title: '员工提交申请',
    actor: '员工',
    desc: '提交后进入待审批状态。',
    status: 'confirmed',
    source: '来自已确认任务：员工提交请假申请',
  },
  {
    id: 'create-record',
    title: '系统创建待审批记录',
    actor: '系统',
    desc: '系统生成一条可被经理处理的待审批记录。',
    status: 'ai_assumption',
    source: 'AI 根据审批类应用自动推导',
  },
  {
    id: 'manager-approve',
    title: '经理审批',
    actor: '直属经理',
    desc: '经理查看申请详情，并选择通过或退回。',
    status: 'confirmed',
    source: '来自已确认任务：经理审批申请',
  },
  {
    id: 'notify-employee',
    title: '通知员工结果',
    actor: '系统',
    desc: '审批完成后通知员工审批结果。',
    status: 'ai_assumption',
    source: 'AI 根据员工体验闭环建议生成',
    affectedBy: '是否需要员工查看状态',
  },
  {
    id: 'notify-hr',
    title: '通知 HR 或由 HR 记录结果',
    actor: '系统 / HR',
    desc: '是否通知 HR、是否由 HR 在系统内记录仍待确认。',
    status: 'needs_confirmation',
    source: '来自页面 02 的 HR 角色分岔',
    affectedBy: 'HR 是审批人、记录人还是结果接收人',
  },
]

const branchPoints: BranchPoint[] = [
  {
    id: 'return-rule',
    title: '退回后如何处理',
    question: '经理退回后，员工是否可以修改再提交？',
    status: 'needs_confirmation',
    options: ['允许修改后再提交', '退回即结束', '经理必须填写退回原因', '暂不确定'],
    impact: '会影响流程是否回到填写步骤、规则是否需要退回原因、原型是否出现“修改后再提交”入口。',
    route: '页面 03：怎么运作',
  },
  {
    id: 'hr-condition',
    title: 'HR 是否条件参与',
    question: '超过一定天数或特殊请假类型时，HR 是否需要参与？',
    status: 'needs_confirmation',
    options: ['不参与审批，只接收结果', '超过 3 天时参与', '所有申请都参与', '后续验证'],
    impact: '会影响是否出现审批分支、是否增加 HR 审批任务、页面 04 第一版复杂度。',
    route: '页面 02 / 页面 04',
  },
  {
    id: 'hr-notification',
    title: '通知 HR 的方式',
    question: '通知 HR 是系统内通知，还是由经理 / 员工线下告知？',
    status: 'ai_assumption',
    options: ['系统自动通知', '人工通知', '只导出记录', '暂不做'],
    impact: '会影响通知能力是否进入第一版范围，以及页面 05 原型是否需要 HR 视角。',
    route: '页面 04：范围与交付',
  },
]

const rules: RuleCandidate[] = [
  {
    id: 'status-pending',
    title: '提交后状态变为待审批',
    desc: '员工提交申请后，系统将申请状态设为“待审批”。',
    status: 'confirmed',
    source: '来自流程步骤：员工提交申请',
    relatedStep: '员工提交申请',
    impact: ['员工可以知道申请已提交', '经理可以看到待处理申请', '页面 05 流程图形成清晰起点'],
  },
  {
    id: 'approve-notify',
    title: '审批通过后通知员工',
    desc: '经理通过申请后，系统通知员工审批结果。',
    status: 'ai_assumption',
    source: 'AI 根据审批类应用体验闭环建议生成',
    relatedStep: '经理审批',
    impact: ['员工知道结果', '减少线下询问', '页面 05 员工原型闭环更完整'],
  },
  {
    id: 'return-resubmit',
    title: '审批退回后员工可修改再提交',
    desc: '如果经理退回申请，员工可以查看原因，修改后再次提交。',
    status: 'needs_confirmation',
    source: '来自流程分岔：退回后如何处理',
    relatedStep: '经理审批',
    impact: ['流程可能回到填写步骤', '需要退回原因字段', '原型需要“修改后再提交”入口'],
  },
  {
    id: 'hr-long-leave',
    title: '超过 3 天时 HR 是否参与处理',
    desc: '长假是否需要 HR 参与审批或记录仍未确认。',
    status: 'needs_confirmation',
    source: '来自 HR 条件参与分岔',
    relatedStep: '通知 HR 或由 HR 记录结果',
    impact: ['可能增加流程分支', '可能增加 HR 审批任务', '可能影响第一版范围'],
  },
]

function TopBar() {
  return (
    <div className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">页面 03：怎么运作 · 草稿审查 × 协作探索合一</div>
          <div className="text-xs text-slate-500">基于已确认角色和任务生成最小流程，围绕分支规则逐步收敛</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700">查看流程依据</button>
          <button className="rounded-2xl bg-sky-600 px-4 py-2 text-sm font-medium text-white">生成最小流程</button>
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
            <Pill tone="warning">2 个流程分岔待确认</Pill>
            <Pill tone="info">可做流程 checkpoint</Pill>
            <div className="text-xs font-medium tracking-wide text-slate-500">流程和规则共创</div>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">员工请假申请</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            本页不从一句话直接生成完整流程，而是基于已确认任务串出最小流程。每确认一个分支规则，流程草稿就更稳定，后续范围和预览也更可靠。
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
    { label: '怎么运作', active: true, maturity: '流程草稿', tone: 'info' as PillTone },
    { label: '范围与交付', maturity: '待流程确认', tone: 'neutral' as PillTone },
    { label: '预览与验证', maturity: '可做 checkpoint', tone: 'info' as PillTone },
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
        页面 03 只推进流程和规则层级；范围会在流程基本成立后继续收敛。
      </div>
    </aside>
  )
}

function ModeTabs({ view, setView }: { view: MainView; setView: (view: MainView) => void }) {
  const tabs = [
    { key: 'flow', label: '最小流程', note: '基于已确认任务生成' },
    { key: 'branch', label: '流程分岔', note: '退回、HR、通知方式' },
    { key: 'rules', label: '规则候选', note: '由流程分岔产生' },
    { key: 'preview', label: '流程预览', note: '阶段性 checkpoint' },
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

function FlowStepCard({ step, index }: { step: FlowStep; index: number }) {
  const meta = statusMeta[step.status]
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-slate-50 text-sm font-semibold text-slate-700 ring-1 ring-slate-200">{index + 1}</div>
          <div>
            <div className="text-base font-semibold text-slate-900">{step.title}</div>
            <div className="mt-1 text-sm leading-6 text-slate-500">责任方：{step.actor}</div>
          </div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">{step.desc}</div>
      <div className="mt-3 rounded-2xl bg-white p-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-200">来源：{step.source}</div>
      {step.affectedBy ? (
        <div className="mt-3 rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">影响因素：{step.affectedBy}</div>
      ) : null}
    </div>
  )
}

function FlowView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">基于已确认任务的最小流程</h2>
            <p className="mt-1 text-sm text-slate-500">先形成最小闭环，再围绕退回、HR 和通知方式确认分支。</p>
          </div>
          <div className="flex gap-2"><Pill tone="success">3 步已确认</Pill><Pill tone="info">2 步 AI 推导</Pill><Pill tone="warning">1 步待确认</Pill></div>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          当前流程只基于页面 02 已确认的核心任务生成。HR 记录、退回再提交等分支仍保持为待确认，不会自动污染正式流程。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {flowSteps.map((step, index) => <FlowStepCard key={step.id} step={step} index={index} />)}
      </section>
    </main>
  )
}

function ReturnRuleOption({ selected, title, desc, impacts, onClick, tone = 'neutral' }: { selected: boolean; title: string; desc: string; impacts: string[]; onClick: () => void; tone?: PillTone }) {
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

function BranchView({ returnRule, setReturnRule }: { returnRule: ReturnRule; setReturnRule: (rule: ReturnRule) => void }) {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-slate-900">关键分岔：退回后如何处理？</h2>
          <p className="mt-1 text-sm text-slate-500">每次只确认一个流程分支。这个判断会影响规则、原型和员工下一步体验。</p>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          AI 建议：第一版允许员工查看退回原因并修改后再提交。这样流程更完整，但需要增加退回原因和再提交入口。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        <ReturnRuleOption
          selected={returnRule === 'allow_resubmit'}
          title="允许修改后再提交"
          desc="经理退回后，员工查看原因，修改申请后重新提交。"
          impacts={['流程会回到填写 / 提交步骤', '需要退回原因字段', '页面 05 员工原型需要再提交入口']}
          onClick={() => setReturnRule('allow_resubmit')}
          tone="success"
        />
        <ReturnRuleOption
          selected={returnRule === 'reject_final'}
          title="退回即结束"
          desc="经理退回后，该申请结束，员工需要新建申请。"
          impacts={['流程更短', '员工体验可能不够顺', '需要说明何时需要重新申请']}
          onClick={() => setReturnRule('reject_final')}
          tone="warning"
        />
        <ReturnRuleOption
          selected={returnRule === 'manager_note'}
          title="经理必须填写退回原因"
          desc="无论是否允许再提交，经理退回时都必须说明原因。"
          impacts={['增加经理填写规则', '员工更容易理解下一步', '原型需要退回原因展示']}
          onClick={() => setReturnRule('manager_note')}
          tone="info"
        />
        <ReturnRuleOption
          selected={returnRule === 'uncertain'}
          title="暂时不确定"
          desc="先保留退回处理为待确认，不阻塞当前流程草稿。"
          impacts={['流程预览会保留问题标记', '导出时带待确认项', '页面 04 范围不受强约束']}
          onClick={() => setReturnRule('uncertain')}
          tone="neutral"
        />
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">其他流程分岔</div>
        <div className="grid grid-cols-3 gap-3">
          {branchPoints.slice(1).map((branch) => {
            const meta = statusMeta[branch.status]
            return (
              <div key={branch.id} className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-900">{branch.title}</div>
                  <Pill tone={meta.tone}>{meta.label}</Pill>
                </div>
                <div className="text-sm leading-6 text-slate-600">{branch.question}</div>
              </div>
            )
          })}
        </div>
      </section>
    </main>
  )
}

function RuleCard({ rule }: { rule: RuleCandidate }) {
  const meta = statusMeta[rule.status]
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="text-base font-semibold text-slate-900">{rule.title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-500">关联步骤：{rule.relatedStep}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>
      <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700 ring-1 ring-slate-200">{rule.desc}</div>
      <div className="mt-3 rounded-2xl bg-white p-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-200">来源：{rule.source}</div>
      <div className="mt-3 grid gap-2">
        {rule.impact.map((impact) => (
          <div key={impact} className="rounded-xl bg-slate-50 px-3 py-2 text-sm leading-5 text-slate-700 ring-1 ring-slate-200">{impact}</div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">采纳规则</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">修改</button>
        <button className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">暂不确定</button>
      </div>
    </div>
  )
}

function RulesView() {
  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">规则候选</h2>
            <p className="mt-1 text-sm text-slate-500">规则根据流程分岔产生，而不是凭空生成。未采纳规则不会自动进入正式对象空间。</p>
          </div>
          <Pill tone="warning">2 条待确认</Pill>
        </div>
        <div className="rounded-2xl bg-sky-50 p-4 text-sm leading-6 text-sky-800 ring-1 ring-sky-200">
          建议先确认退回后处理，再让页面 05 做流程 checkpoint。这样可以更早发现员工是否知道下一步。
        </div>
      </section>

      <section className="grid grid-cols-2 gap-6">
        {rules.map((rule) => <RuleCard key={rule.id} rule={rule} />)}
      </section>
    </main>
  )
}

function PreviewView() {
  const lanes = ['员工', '系统', '直属经理', 'HR']
  const laneSteps: Record<string, FlowStep[]> = {
    员工: flowSteps.filter((step) => step.actor === '员工'),
    系统: flowSteps.filter((step) => step.actor === '系统'),
    直属经理: flowSteps.filter((step) => step.actor === '直属经理'),
    HR: flowSteps.filter((step) => step.actor.includes('HR')),
  }

  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">流程草稿 checkpoint</h2>
            <p className="mt-1 text-sm text-slate-500">在范围收敛前，先跑一遍当前流程草稿，看看是否闭环。</p>
          </div>
          <Pill tone="warning">仍有 2 个待确认分岔</Pill>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-800 ring-1 ring-amber-200">
          当前流程可以形成主闭环，但“退回后处理”和“HR 是否参与”仍会影响页面 04 范围和页面 05 原型。
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-4">
          {lanes.map((lane) => (
            <React.Fragment key={lane}>
              <div className="flex items-center justify-center rounded-2xl bg-slate-50 px-3 py-4 text-sm font-semibold text-slate-700 ring-1 ring-slate-200">{lane}</div>
              <div className="grid grid-cols-3 gap-3 rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                {laneSteps[lane].length > 0 ? laneSteps[lane].map((step) => {
                  const meta = statusMeta[step.status]
                  return (
                    <div key={step.id} className="rounded-2xl bg-white p-4 ring-1 ring-slate-200">
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <div className="text-sm font-semibold leading-5 text-slate-900">{step.title}</div>
                        <Pill tone={meta.tone}>{meta.label}</Pill>
                      </div>
                      <div className="text-xs leading-5 text-slate-500">{step.desc}</div>
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

function RightRail({ view, setView }: { view: MainView; setView: (view: MainView) => void }) {
  return (
    <aside className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">当前关键分岔</div>
        <div className="rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-200">
          <div className="text-sm font-semibold text-slate-900">退回后是否允许员工修改再提交？</div>
          <div className="mt-2 text-sm leading-6 text-amber-800">这个判断会影响流程是否回到填写步骤、规则是否需要退回原因、员工原型是否出现再提交入口。</div>
          <button onClick={() => setView('branch')} className="mt-3 rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white">去确认</button>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">流程假设账本</div>
        <div className="space-y-3">
          {branchPoints.map((branch) => {
            const meta = statusMeta[branch.status]
            return (
              <button key={branch.id} onClick={() => setView('branch')} className="w-full rounded-2xl bg-slate-50 p-4 text-left ring-1 ring-slate-200 hover:bg-slate-100">
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold leading-5 text-slate-900">{branch.title}</div>
                  <Pill tone={meta.tone}>{meta.label}</Pill>
                </div>
                <div className="text-xs leading-5 text-slate-500">{branch.route}</div>
              </button>
            )
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-slate-900">AI 可以帮你</div>
        <div className="space-y-2">
          {[
            ['解释退回分支影响', 'info'],
            ['生成当前流程 checkpoint', 'neutral'],
            ['把待确认规则推送到问题列表', 'neutral'],
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
    view === 'flow'
      ? '例如：帮我解释当前流程里哪些是 AI 推导'
      : view === 'branch'
        ? '例如：比较退回后再提交和退回即结束'
        : view === 'rules'
          ? '例如：只保留第一版必须确认的规则'
          : '例如：从当前流程预览里找断点'

  return (
    <div className="fixed bottom-5 left-1/2 z-10 w-[780px] -translate-x-1/2 rounded-3xl border border-slate-200 bg-white/95 px-5 py-4 shadow-xl backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 ring-1 ring-sky-200">页面 03：怎么运作</div>
        <input className="h-11 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none" placeholder={placeholder} />
        <button className="rounded-2xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white">AI 帮我推进</button>
      </div>
    </div>
  )
}

export default function LitePage03IntegratedDraftExploration() {
  const [view, setView] = useState<MainView>('flow')
  const [returnRule, setReturnRule] = useState<ReturnRule>('allow_resubmit')
  const maturity = useMemo<DraftMaturity>(() => 'flow', [])

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
              {view === 'flow' ? <FlowView /> : view === 'branch' ? <BranchView returnRule={returnRule} setReturnRule={setReturnRule} /> : view === 'rules' ? <RulesView /> : <PreviewView />}
            </div>
            <RightRail view={view} setView={setView} />
          </div>
        </div>
        <FloatingAI view={view} />
      </div>
    </div>
  )
}
