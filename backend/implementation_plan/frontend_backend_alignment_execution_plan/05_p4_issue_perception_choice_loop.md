# P4：Issue、Perception、Slot Filling、Choice 闭环接入

## 一、阶段目标

把前端当前的本地静态 Issue 与 no-op AI 操作，迁移到后端 IssueService、NextSuggestion、PerceptionJob、Slot Filling Draft 和 ChoiceGroup 机制。

本阶段完成后，至少要打通一条真实闭环：

```text
检测问题 -> 展示后端 Issue -> 生成解决方案/填补草稿 -> 确认或接受 Choice -> 数据落库 -> 聚合 IR 刷新 -> Issue 消失或状态变化
```

## 二、背景问题

前端当前：

- `detectIssues(space)` 本地生成 `rule_*` issue。
- `createSlotFromIssue` 返回 `null`。
- `expandSlot` no-op。
- `acceptChoice/rejectChoice` no-op。
- `runDiagnosis` 只设置提示文案。
- `rewrite/explainImpact` no-op。
- `selectChoices/selectProposals` 返回空数组。

后端已有：

- `GET /api/projects/{project_id}/issues?stage=...`
- `POST /api/projects/{project_id}/issues/resolve`
- `GET /api/projects/{project_id}/next-suggestion?stage=...`
- `POST /api/projects/{project_id}/next-suggestion/start`
- `POST /api/perception_slot_filling_drafts/{kind}`
- `POST /api/perception_slot_filling_drafts/{draft_id}/confirm`
- `GET /api/projects/{project_id}/choice_groups`
- `POST /api/projects/{project_id}/choices/{choice_id}/accept`
- `POST /api/projects/{project_id}/choices/{choice_id}/reject`

## 三、范围

### 本阶段必须做

1. 前端接入后端 Issue list。
2. 建立后端 Issue -> 前端 Issue view model mapper。
3. 接入 Issue resolve。
4. 接入 next-suggestion。
5. 接入 slot filling draft create/confirm/discard。
6. 接入 choice group list/accept/reject。
7. 至少替换 Overview、IssuePanel、SlotPanel、ChoicePanel 的 no-op 动作。

### 本阶段不做

- 不实现 Proposal 后端能力。
- 不实现复杂多人协作。
- 不要求所有 issue resolver 都完美覆盖，但必须有可验收闭环。

## 四、产品决策

### 1. Issue 来源

推荐策略：后端 Issue 为主，前端本地 `detectIssues` 作为临时 fallback。

页面显示：

- 如果后端请求成功，展示后端 issues。
- 如果后端不可用且 dev 模式开启，可展示本地静态 issues，并明确标记为 local diagnostics。

### 2. Issue ID 策略

前端旧 Issue 使用 `id`，后端 Issue 使用：

- `issue_id`
- `code`
- `stage`
- `target`

前端 view model 应保留：

```ts
{
  id: issue.issue_id,
  backendIssueCode: issue.code,
  backendTarget: issue.target,
  title,
  description,
  severity: mapSeverity(issue.severity),
  status: 'open',
  suggestedProjection: mapStage(issue.stage),
}
```

调用 resolve 时必须使用 `issue_code + target`，不能只传前端 id。

### 3. Perception Slot 表达

前端旧 `perceptionSlot` 只有单个 slot。后端以 perception job 和 next suggestion 为核心。

推荐 P4 做法：

- 聚合详情中仍可返回当前 active slot，兼容旧 UI。
- 但 SlotPanel 操作需要持有 `perception_job_id`。
- 如果聚合 IR 无法表达 job id，则在 slotsRecord 中合成：

```ts
{
  id,
  perceptionJobId,
  kind: 'perception_slot',
  status,
  fillerKind,
  title,
  description
}
```

## 五、后端 API 接入任务

### 任务 1：Issue list

前端按页面 stage 调用：

- What -> `stage=what`
- How -> `stage=how`
- Scope -> `stage=scope`
- Preview -> `stage=preview`

**前端并发请求优化（Promise.all）**：由于后端目前获取 Issue 时强制要求传入 `stage` 参数，Overview 页面如需展示全量诊断数据，必须通过 `Promise.all()` 同时并发请求上述 4 个 stage 的 Issue 列表，以保障页面首次加载的速度与性能。

例如：
```ts
const [what, how, scope, preview] = await Promise.all([
  workspaceApi.listIssues(projectId, 'what'),
  workspaceApi.listIssues(projectId, 'how'),
  workspaceApi.listIssues(projectId, 'scope'),
  workspaceApi.listIssues(projectId, 'preview')
]);
```

如果产品要求“任一 stage 加载失败则 Overview 整体进入错误态”，使用 `Promise.all()` 即可；如果产品要求“单个 stage 失败不影响其他 stage 展示”，则应使用 `Promise.allSettled()` 做局部降级：

```ts
const stages = ['what', 'how', 'scope', 'preview'] as const;

const results = await Promise.allSettled(
  stages.map((stage) => workspaceApi.listIssues(projectId, stage))
);

const issuesByStage = Object.fromEntries(
  results.map((result, index) => [
    stages[index],
    result.status === 'fulfilled' ? result.value : []
  ])
);
```

默认建议 Overview 使用 `Promise.allSettled()`，以免单个阶段诊断失败导致整页诊断概览不可用；同时需要在 UI 中对失败的 stage 给出轻量错误提示。

### 任务 2：Issue resolve

调用：

```http
POST /api/projects/{project_id}/issues/resolve
```

body：

```json
{
  "issue_code": "xxx",
  "target": {},
  "metadata": {}
}
```

响应可能包含：

- action
- draft_id
- draft
- patch

前端需要根据 `resolution_type/action` 决定：

- 打开 panel。
- 显示 draft preview。
- 进入 slot filling。
- 直接 apply patch 或创建 choice。

### 任务 3：next-suggestion

ScopedAIBar 的 diagnose：

- `GET /api/projects/{project_id}/next-suggestion?stage=current`

如果返回需要启动：

- `POST /api/projects/{project_id}/next-suggestion/start`

需要定义 UI 状态：

- ready
- running
- done_empty
- done_with_slot
- failed
- stale

### 任务 4：slot filling draft

根据 slot/perception kind 分发：

- actor -> `/actor`
- feature -> `/feature`
- scenario -> `/scenario`
- acceptance criteria -> `/acceptance_criteria`
- flow -> `/flow`

body：

```json
{
  "project_id": 1,
  "perception_job_id": 123
}
```

confirm 后刷新聚合详情。

### 任务 5：choice groups

前端调用：

- `GET /api/projects/{project_id}/choice_groups?status=open`
- `POST /api/projects/{project_id}/choices/{choice_id}/accept`
- `POST /api/projects/{project_id}/choices/{choice_id}/reject`

accept 后：

1. 后端应用 patch。
2. 后端 resolve group。
3. 前端 refreshWorkspace。

## 六、前端实现任务

### 任务 1：新增 issue/choice API methods

在 `workspaceApi` 中新增：

- `listIssues(projectId, stage)`
- `resolveIssue(projectId, issueCode, target, metadata)`
- `getNextSuggestion(projectId, stage)`
- `startNextSuggestion(projectId, payload)`
- `createSlotFillingDraft(kind, projectId, perceptionJobId)`
- `confirmSlotFillingDraft(draftId)`
- `discardSlotFillingDraft(draftId)`
- `listChoiceGroups(projectId, status?)`
- `acceptChoice(projectId, choiceId)`
- `rejectChoice(projectId, choiceId)`

### 任务 2：store 状态扩展

建议新增：

- `backendIssuesByStage`
- `choiceGroups`
- `suggestionsByStage`
- `perceptionJobs`
- `isDiagnosing`
- `diagnosisError`

### 任务 3：替换 selectIssues

短期策略：

- 如果后端 issues 已加载，返回后端 mapped issues。
- 否则返回本地 `detectIssues`。

长期策略：

- 移除本地静态 detector 或只作为 dev diagnostic。

### 任务 4：实现 createSlotFromIssue

流程：

1. 找到后端 issue view model。
2. 调用 `resolveIssue`。
3. 根据响应：
   - 如果返回 draft，设置 activeDraft。
   - 如果返回 action open panel，选中目标对象。
   - 如果返回 slot/perception info，设置 selectedSlotId。
4. 返回 slot id 或 draft id。

### 任务 5：实现 expandSlot

流程：

1. 根据 slot 获取 `fillerKind` 和 `perceptionJobId`。
2. 调用对应 slot filling draft create。
3. 设置 `activeDraft` 和 `activeDraftType`。
4. UI 展示 draft preview。

### 任务 6：实现 acceptChoice/rejectChoice

流程：

1. 调用后端 choice action。
2. refreshWorkspace。
3. reload choice groups。
4. 设置 lastActionMessage。

### 任务 7：ScopedAIBar 接后端

三类 intent：

- diagnose -> next-suggestion。
- rewrite -> 暂时可以走 issue resolve 或明确标记 P5。
- explain_impact -> 暂时可以走 P5 impact preview，P4 可以先返回“不支持”。

至少 diagnose 必须真实接入。

## 七、验收标准

P4 验收必须全部满足：

1. What 页面至少能从后端拉取 `stage=what` issues。
2. How 页面至少能从后端拉取 `stage=how` issues。
3. Overview 不再只依赖本地 `detectIssues`。
4. IssuePanel 点击“处理”能触发后端 `issues/resolve`。
5. 至少一种 issue 能产生可确认 draft，并 confirm 落库。
6. SlotPanel 点击展开能调用 slot filling draft route。
7. ChoiceGroupPanel 能展示后端 choice groups。
8. ChoicePanel accept 能调用后端并应用 patch。
9. ChoicePanel reject 能调用后端并更新状态。
10. confirm/accept 后刷新页面，数据状态保持一致。

## 八、最小闭环验收用例

推荐选择“叶子功能缺少场景”作为最小闭环：

1. 创建项目，确保有 actor 和 leaf feature，但没有 scenario。
2. 后端 `GET /issues?stage=what` 返回缺场景 issue。
3. 前端展示 issue。
4. 点击处理，调用 `issues/resolve`。
5. 后端返回 scenario generation draft 或 action。
6. 前端展示 draft。
7. confirm draft。
8. 聚合 IR 中 leaf feature 出现场景。
9. 再次拉取 issue，该 issue 消失或数量减少。

## 九、风险与处理

| 风险 | 处理 |
| --- | --- |
| 后端 Issue 与前端本地 Issue 文案不一致 | P4 以后以后端为准，前端只做展示映射 |
| PerceptionJob 异步状态 UI 复杂 | 先做简单轮询和状态提示，后续再优化 |
| ChoiceGroup 数据为空 | 先打通由 issue/slot 产生 choice 的一个 resolver |
| Proposal 没有后端 | P4 不接 Proposal，P5 决策隐藏或补建模 |

## 十、进入 P5 的条件

P4 通过后，进入 P5 前需确认：

- 前端主要 AI 诊断入口不再是 no-op。
- Issue -> Draft/Choice -> Confirm/Accept -> Refresh 至少有一条稳定链路。
- ChoiceGroup 与 Slot 在前端 IR 中有明确映射方式。
- 未接入的 Proposal/Impact/Preview 能力已列入 P5 决策清单。
