# 前后端联调一致性差异核查报告

核查日期：2026-05-24

核查范围：

- 前端：`frontend/src/lib/api.ts`、`frontend/src/store/useWorkspaceStore.ts`、`frontend/src/core/schema.ts`、`frontend/src/core/selectors.ts`、主要页面与右侧面板组件。
- 后端：`backend/main.py`、`backend/api/routes/*`、`backend/api/schemas/*`、`backend/api/services/*`、`backend/database/model.py`、`backend/schemas.py`、`backend/integration/skill_backed_services/*`。
- 验证命令：`npm run lint`、`python -m compileall backend`、直接导入 `backend.main`。

## 结论摘要

当前项目还没有真正完成前后端 API 对接。前端 `workspaceApi` 仍是完整的 `localStorage` Mock 层，负责项目列表、项目详情、整项目保存、AI 草稿、导出、影响分析等所有行为；后端已经实现了一批 FastAPI 路由和数据库模型，但路由粒度、字段命名、生命周期、草稿存储、Issue/Slot/Choice 机制与前端当前状态模型并不一致。

最大阻断有四类：

1. **前端没有发 HTTP 请求**：`frontend/src/lib/api.ts` 没有 `fetch`/`axios`，所有项目和草稿都落在浏览器 `localStorage`。
2. **后端缺少前端最依赖的基础聚合路由**：没有项目列表、项目详情聚合读取、整项目保存、项目删除、导出、范围影响预览等路由。
3. **数据模型一边是前端 CamelCase 聚合 IR，一边是后端 SnakeCase 细粒度 CRUD**：即使接上 HTTP，也需要适配层。
4. **AI 推演/感知槽/Choice 生命周期不一致**：前端是单个 `perceptionSlot + activeDraft` 的本地状态，后端是 `perception_jobs + issue resolver + slot filling drafts + choice_groups` 的异步/持久化机制。

另外，联调前还有一个前端静态阻断和一个环境核查结论：

- `npm run lint` 当前仍失败，包含 `@/types` 缺失、React 命名空间缺失、若干类型比较错误。
- 使用项目 `.venv\Scripts\python.exe` 直接导入 `backend.main` 成功，FastAPI app 当前可加载出 81 条 route。此前默认 shell `python` 缺包属于解释器环境未切到项目虚拟环境，不应作为后端依赖缺失结论。

## 一、联调前置阻断

### 1. 前端 TypeScript 不能通过

执行 `npm run lint` 失败，主要错误：

- `frontend/src/components/right-panel/ChoiceGroupPanel.tsx`
- `frontend/src/components/right-panel/ChoicePanel.tsx`
- `frontend/src/components/right-panel/ProposalPanel.tsx`
- `frontend/src/components/shared/ChoiceCard.tsx`

这些文件引用 `@/types`，但仓库中没有 `frontend/src/types.ts` 或 `frontend/src/types/index.ts`。真实类型定义在 `frontend/src/core/schema.ts`。

已复核：`frontend/backup` 目录当前不存在，`npm run lint` 不再扫描备份代码。当前剩余错误均来自 `frontend/src` 下的真实源码。

其他前端类型错误：

- `frontend/src/components/layout/LeftNav.tsx` 中多个状态字符串比较与推断类型不相交。
- `frontend/src/components/shared/RightObjectPanel.tsx` 的 `PanelErrorBoundary` 类组件缺少显式 props/state 类型。
- `frontend/src/components/shared/ScopedAIBar.tsx`、`frontend/src/pages/HowItWorks.tsx` 使用 `React.MouseEvent`，但没有导入 `React` 命名空间。

### 2. 后端 app 在项目虚拟环境中可正常导入

`python -m compileall backend` 可以通过语法编译。使用项目虚拟环境执行：

```powershell
.venv\Scripts\python.exe -c "from backend.main import app; print('ok', len(app.routes))"
```

结果为：

```text
ok 81
```

因此后端依赖本身在项目虚拟环境中是满足的。联调时应明确使用 `.venv` 启动后端服务，避免默认系统 Python 造成误判。

### 3. 跨端开发缺少 CORS 或 Vite 代理

`backend/main.py` 没有配置 `CORSMiddleware`，`frontend/vite.config.ts` 也没有配置 `/api` proxy。前端 dev server 与 FastAPI 分别启动时，浏览器请求会被 CORS 或跨端口问题挡住。

## 二、前端 API 层仍是 Mock/localStorage

`frontend/src/lib/api.ts` 的 `workspaceApi` 是“Core Mock API Implementation”，没有真实 HTTP 调用：

- 项目数据读取：`localStorage.getItem('rs_workspace_spaces')`
- 草稿数据读取：`localStorage.getItem('rs_workspace_drafts')`
- 项目保存：直接替换 localStorage 中的完整 `RequirementSpace`
- AI 草稿生成：硬编码 demo 数据
- 导出与影响分析：前端本地拼装

这意味着：

- 后端任何路由目前都没有被前端调用。
- 浏览器刷新、不同用户、不同设备与后端数据库完全无关。
- 前端 `workspaceApi.save(space)` 保存的是整棵 IR，但后端没有对应整项目保存端点。

## 三、前端需要但后端缺失的关键基础路由

前端当前核心依赖如下：

| 前端方法 | 当前行为 | 后端现状 | 缺口 |
| --- | --- | --- | --- |
| `workspaceApi.list()` | 返回项目卡片列表，含 `id/name/idea/updatedAt/status/issueCount/nodeCount` | 无 `GET /api/projects` | 缺项目列表聚合路由 |
| `workspaceApi.getById(id)` | 返回完整 `RequirementSpace` 聚合对象 | 无 `GET /api/projects/{project_id}` | 缺项目详情聚合路由 |
| `workspaceApi.save(space)` | 整项目覆盖保存 | 后端只有细粒度 CRUD | 缺整项目保存或前端适配为多路由 patch |
| `workspaceApi.delete(id)` | 删除项目 | 无 `DELETE /api/projects/{project_id}` | 缺项目删除路由 |
| `workspaceApi.exportMarkdown(id)` | 本地生成 Markdown | 无导出路由 | 缺 `GET /api/projects/{id}/export.md` 或前端继续本地导出 |
| `workspaceApi.exportJson(id)` | 返回完整 IR | 无聚合 JSON 路由 | 同 `getById` |
| `workspaceApi.impactPreview(id)` | 返回简单数量统计 | 后端无影响分析路由 | 缺 scope/patch impact preview |
| `workspaceApi.discardDraft(draftId)` | 不区分类型删除草稿 | 后端每类草稿各自 DELETE | 缺统一 draft registry 或前端按类型分发 |

后端现有基础路由更多是“动作型”和“细粒度 CRUD 型”：

- `POST /api/blank_projects`
- `POST /api/project_creation_drafts`
- `POST /api/actor_generation_drafts`
- `POST /api/feature_generation_drafts`
- `POST /api/flow_generation_drafts`
- `POST /api/scenario_generation_drafts/full|single`
- `POST /api/acceptance_criteria_generation_drafts/full|single|batch`
- `POST /api/scope_generation_drafts`
- `GET/POST/PUT/DELETE /api/projects/{project_id}/actors`
- `GET/POST/PUT/DELETE /api/projects/{project_id}/features`
- `POST/PUT/DELETE /api/projects/{project_id}/scenarios`
- `POST/PUT/DELETE /api/projects/{project_id}/business_objects`
- `POST/PUT/DELETE /api/projects/{project_id}/flows`
- `PUT /api/projects/{project_id}/features/{feature_id}/scope`

后端没有一个可以一次性组装前端工作台所需 `RequirementSpace` 的 serializer，这会成为联调主瓶颈。

## 四、路由粒度与前端调用方式错配

### 1. 前端是整对象保存，后端是细粒度 CRUD

前端手动编辑统一走：

```ts
await workspaceApi.save(updated)
```

这覆盖整棵 `RequirementSpace`。后端没有这种端点，而是拆为：

- actor CRUD
- feature CRUD
- scenario/acceptance criteria CRUD
- business object/attribute CRUD
- flow/flow step CRUD
- scope update

因此接后端时不能只把 `workspaceApi.save` 改成一个 URL。需要二选一：

1. 后端新增 `PUT /api/projects/{project_id}/requirement-space` 聚合保存接口。
2. 前端每个 action 改为调用对应细粒度路由，并在成功后重新拉取聚合详情。

第二种更符合后端现有设计，但改动面更大。

### 2. 部分后端 CRUD 缺少列表读取

后端 actor、feature 有 `GET` 列表；但以下资源只有 create/update/delete，没有对应 list：

- `business_objects`
- `flows`
- `scenarios`
- `acceptance_criteria`

如果没有聚合详情路由，前端无法在打开项目时重建完整 IR。

### 3. 前端方法与后端路径需要显式分发

前端：

- `createScenarioGenerationDraft(projectId, featureId?)`
- `createAcceptanceCriteriaGenerationDraft(projectId, scenarioIds?)`

后端：

- 场景生成：`/api/scenario_generation_drafts/full` 和 `/single`
- 成功标准生成：`/api/acceptance_criteria_generation_drafts/full`、`/single`、`/batch`

前端适配层需要根据参数选择后端路径。当前 mock 方法没有暴露这个分发差异。

## 五、数据模型与字段命名脱节

### 1. 顶层项目模型不一致

前端 `RequirementSpace`：

- `projectId`
- `projectName`
- `projectDescription`
- `userRequirements`
- `perceptionSlot`
- `actors`
- `features`
- `businessObjects`
- `flows`
- 兼容字段：`nodes`、`links`、`issues`、`slots`、`choiceGroups`、`proposals`

后端数据库 `ProjectModel`：

- `id`
- `name`
- `description`
- `user_requirements`
- relationships: `actors`、`features`、`scenarios`、`business_objects`、`flows`、`choice_groups`、`audit_logs`

后端 `backend/schemas.py` 里确实有 CamelCase dataclass `RequirementSpace`，但 FastAPI routes 当前没有返回这个聚合 schema。

### 2. 节点字段命名不一致

| 领域 | 前端字段 | 后端 CRUD 响应字段 |
| --- | --- | --- |
| Actor | `actorId/actorName/actorDescription` | `actor_id/name/description` |
| Feature | `featureId/featureName/featureDescription/parentId/childrenIds/actorIds` | `feature_id/name/description/parent_id/child_ids/actor_ids` |
| Scenario | `scenarioId/scenarioName/scenarioContent/acceptanceCriteria` | `scenario_id/name/content/acceptance_criteria` |
| AC | `criterionId/criterionContent` | `criterion_id/content/position` |
| Business Object | `businessObjectId/businessObjectName/businessObjectDescription/businessObjectAttributes` | `business_object_id/name/description/attributes` |
| BO Attribute | `businessObjectAttributeId/...Type/...Example` | `attribute_id/data_type/example` |
| Flow | `flowId/flowName/flowDescription/flowSteps` | `flow_id/name/description/steps` |
| Flow Step | `stepId/stepName/stepDescription/stepType` | `step_id/name/description/step_type` |
| Scope | `scopeId/scopeStatus/positiveSummary` | `scope_id/status/positive_summary` |

接后端必须有统一 mapping，否则 UI 读不到字段。

### 3. Issue 模型完全不同

前端 `Issue`：

- `id`
- `title`
- `description`
- `severity: high|medium|low`
- `status: open|ignored|resolved`
- `relatedNodeIds`
- `suggestedProjection`
- `category`

后端 `Issue`：

- `issueId` 是由 `stage/code/target` 计算出来的属性
- `stage: what|how|scope|preview`
- `severity: blocking|warning|info`
- `target`
- `resolverCode`
- `metadata`

后端 API `IssueResponse` 返回的是 `issue_id/code/stage/severity/title/description/target/resolver_code/metadata`。前端目前的 `detectIssues` 在本地生成 `rule_*` ID，不能直接调用后端 `/api/projects/{project_id}/issues/resolve`，因为该接口需要 `issue_code + target`，不是前端本地 `issue.id`。

### 4. Slot/PerceptionJob 模型不一致

前端只有一个简单 `perceptionSlot`：

- `perceptionSlotId`
- `perceptionKind`
- `perceptionDescription`

后端有更复杂的 `PerceptionJobModel`：

- `stage`
- `perception_kind`
- `target_type`
- `target_id`
- `context_hash`
- `status`
- `result_slot_payload`
- `error_message`

且 slot filling 路由要求：

- `project_id`
- `perception_job_id`

前端没有保存 `perception_job_id`，`createSlotFromIssue` 也是 no-op，因此无法使用后端 slot filling 流程。

### 5. Choice/ChoiceGroup/Proposal 模型不一致

前端把 `choiceGroups`、`proposals` 放在 `RequirementSpace` 的 record 字段中；选择器 `selectChoices/selectProposals` 当前返回空数组。

后端只有：

- `ChoiceGroupModel`
- `ChoiceModel`
- `GET /api/projects/{project_id}/choice_groups`
- `POST /api/projects/{project_id}/choices/{choice_id}/accept`
- `POST /api/projects/{project_id}/choices/{choice_id}/reject`

后端没有 `Proposal` 数据表和 API；前端 `ProposalPanel`、`acceptProposal/rejectProposal/convertProposalToChoice` 没有对应后端能力。

### 6. Scope 图片字段不一致

前端 Scope：

- `positivePictureBase64`
- `negativePictureBase64`

后端 DB：

- `positive_picture: LargeBinary`
- `negative_picture: LargeBinary`

后端生成 draft schema 返回 base64 图片字段，但 CRUD `ScopeResponse` 没有返回图片字段。范围看板如果要展示 Kano 图或正反方图片，需要统一图片的存储与响应策略。

### 7. 前端存在后端未建模的 UI/IR 概念

前端 schema 和 selectors 使用或合成了：

- `screen`
- `goal`
- `capability`
- `task`
- `field`
- `state_machine`
- `state_transition`
- `links`
- `nodes`
- `actorsCompatible`
- `flowStepsCompatible`
- `issuesCompatible`
- `linksCompatible`

后端 DB 当前没有 screen/page/state-machine 等表。`nodes/links` 主要是前端兼容层合成，并不是后端真实 IR。

### 8. ID 生成生命周期错配：前端随机 ID vs 后端自增主键

- **现象**：前端在手动编辑模式下，增加 Actor、Feature 或 Flow Step 等实体时，使用本地辅助函数 `makeIntId()` 生成一个随机的 4 位整数 ID（如 `5280`），然后通过 `workspaceApi.save` 存储。
- **冲突点**：后端数据库实体使用标准的 SQLAlchemy Integer 自增主键 (`id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)`)。后端对每个手动 CRUD 创建动作，均由数据库在落库时自动分配 ID，并不接受前端自定义的随机 ID。
- **风险**：如果前端继续使用随机生成的 ID 并在后续依赖中使用（如将随机 `featureId` 绑定到 FlowStep 的 `featureIds`），一旦落库，数据库里的真实主键和前端的随机 ID 将完全对不上，导致前端维护的依赖网和后端数据库中的真实外键级联关系彻底断网，乃至触发外键约束冲突错误。
- **对齐要求**：前端手动 CRUD 的 POST 动作**绝不能在本地生成随机 ID**，必须在 POST 成功后直接捕获并使用后端返回的 JSON 中自带的真实数据库 ID（如自增的 `1`、`2` 等）更新本地状态。

### 9. ID 数据类型不一致：string 与 number 的严格相等 (===) 比较失败风险

- **现象**：前端为了与旧版本架构兼容，在 Selector、组件以及状态映射时，经常在 string 和 number 之间反复横跳（例如将 `actorId` 转为 `id = actorId.toString()` 进行比对，或者使用状态机内的 `selectedObjectId: string | number`）。
- **冲突点**：后端数据库和 Schema 中定义的 ID 都是严格的 `int`。在前端的代码（如 `findSelectedObjectInIr`）和各种页面选中态管理中，存在大量的 `===` 严格等值比对。
- **风险**：网络通信下发的 ID 序列化后若没有进行类型归一，当前端尝试使用 string 类型的 ID（如 `'101'`）与后端返回的原始 number 类型 ID（如 `101`）使用 `===` 进行匹配时，将无声失败。这会导致诸如“选中节点后右侧编辑面板显示空白/暂无数据”等难以排查的 UI 灵异 Bug。
- **对齐要求**：前端在 API Client 封装层和 Zustand Selector 中，必须确立 ID 类型的归一化原则：内存和接口传输中的原始数据一律保持 `number`，仅在呈现前端定制 Graph Nodes 时转为 `string`。

## 六、AI 推演与草稿生命周期不一致

### 1. 前端草稿是本地、单 activeDraft

前端 store 只有一个：

- `activeDraft`
- `activeDraftType: project|actor|feature|flow|scenario|ac|scope`

confirm 后通常：

1. 调用 mock confirm。
2. mock 修改 localStorage 中完整项目。
3. 前端 `refreshWorkspace()` 再从 localStorage 读项目。

### 2. 后端草稿是服务实例内存 `_drafts`

后端 generation services 都用类似：

```py
self._drafts: dict[str, dict] = {}
```

这带来几个问题：

- 后端重启后草稿丢失。
- 多进程/多 worker 下草稿不共享。
- 草稿没有用户/session/project 级隔离。
- 前端如果刷新页面，只有 draft id 也无法从后端重新获取 draft，因为没有 `GET /drafts/{id}`。

这和前端 localStorage 草稿“刷新后仍存在”的体验不一致。

### 3. Regenerate 反馈没有贯通

后端 regenerate 路由普遍支持 `DraftRegenerateRequest.user_feedback`。

前端 `ProjectOnboarding` 有 `feedback` 输入，但 `regenerateAIOnboarding()` 调用 `workspaceApi.regenerateProjectCreationDraft(draft_id)` 时没有传 feedback。mock 也只是硬编码改几项内容。

其他 actor/feature/flow/scenario/ac/scope 生成，前端没有对应的 regenerate UI/参数路径。

### 4. Skill-backed 接入只覆盖部分生成链路

`service_registry.py` 根据 `REQUIREMENTSPACE_GENERATION_BACKEND=skill` 切换：

- project creation
- feature generation
- scenario generation
- acceptance criteria generation
- scope generation

但以下服务始终使用 legacy：

- `actor_generation_service = ActorGenerationService()`
- `flow_generation_service = FlowGenerationService()`
- blank project service 也仍走 legacy blank generator

所以即使环境变量启用 skill，AI 生成链路仍是混合模式。前端不会感知这种差异，但联调结果会出现生成质量和字段风格不一致。

### 5. Perception/Issue/Slot 生命周期前后端完全错位

后端设计：

1. `GET /api/projects/{project_id}/next-suggestion?stage=...`
2. 如果需要，后台启动 perception job。
3. job 变为 `running/done_empty/done_with_slot/failed/stale`。
4. 产生 slot suggestion。
5. 通过 `/api/perception_slot_filling_drafts/{kind}` 生成填补草稿。
6. confirm 后落库，并将相关 perception jobs 标记 stale。

前端当前：

- 页面健康与 Issue 由 `detectIssues(space)` 本地静态规则生成。
- `createSlotFromIssue` 返回 `null`。
- `expandSlot` no-op。
- `clearPerceptionSlot` 只是把 `space.perceptionSlot = null`。
- `runDiagnosis` 只设置一句消息。
- `rewrite`、`explainImpact` no-op。

因此后端已有的感知任务、异步状态、slot filling draft，目前完全没有被 UI 使用。

## 七、Issue/Choice/Patch 机制错配

### 1. 前端 patch 操作是空实现

前端 store 中这些动作都是空或近似空实现：

- `applyPatch`
- `expandSlot`
- `acceptChoice`
- `rejectChoice`
- `createSlotFromIssue`
- `rewrite`
- `explainImpact`
- `createIssue`
- `updateIssueAttributes`
- `updateChoiceAttributes`
- `addChoiceToGroup`
- `acceptProposal`
- `rejectProposal`
- `convertProposalToChoice`

但 UI 组件已经大量暴露这些入口：

- `ScopedAIBar`
- `Overview`
- `IssuePanel`
- `SlotPanel`
- `ChoicePanel`
- `ChoiceGroupPanel`
- `ProposalPanel`
- `NodePanel` 的关系编辑器

用户点击后不会真实触发后端。

### 2. 后端有 PatchEngine，但没有直接路由

后端 `GraphPatchEngine` 支持对数据库应用 `addNodes/updateNodes/deleteNodes/addLinks/removeLinkIds` 等 patch，`ChoiceService.accept_choice` 会调用它。

但前端 `applyPatch(patch)` 没有对应后端 API。当前只有通过“接受后端已存在的 Choice”才能间接应用 patch。

这造成：

- NodePanel 关系编辑器无法落库。
- SlotPanel 暂缓 slot 的 patch 无法落库。
- 右侧面板里手动状态变更不能走统一 patch audit。

### 3. Choice 来源断裂

后端 choice group 可以 list/accept/reject，但仓库中没有看到前端调用 `/api/projects/{id}/choice_groups`，也没有将后端 choice groups 合并进 `RequirementSpace.choiceGroups`。

后端也没有创建 ChoiceGroup 的通用路由。Choice 主要应由 issue resolver 或 slot filling 产生，但前端目前没有接这个闭环。

## 八、页面级功能与后端能力错配

### Home

依赖 `workspaceApi.list()`。后端没有项目列表路由；也没有返回 `issueCount/nodeCount/status/updatedAt` 的 project card DTO。

### ProjectOnboarding

AI 创建草稿和 confirm 的后端路由基本存在，但：

- 前端仍走 mock。
- regenerate feedback 没有传后端。
- confirm 后前端调用 `getById(project_id)`，后端没有项目聚合详情路由。

### WhatToDo

页面读取本地聚合 IR 中的 actors/features/scenarios/acceptanceCriteria。后端可以分别生成/CRUD 这些资源，但缺聚合读取。页面上的 Issue 仍来自前端静态规则，不是后端 IssueService。

### HowItWorks

页面依赖 flows、flowSteps、businessObjects，以及合成的 slots/choices。后端 flow/business object CRUD 存在，但缺列表/聚合读取；slot/choice 机制没有前端接入。

### ScopeAndDelivery

页面拖动 scope 后调用 `workspaceApi.impactPreview()`，当前只是本地数量统计。后端没有影响分析预览接口。实际落库是 `updateScope()` 通过整项目 save，本应改为 `PUT /api/projects/{project_id}/features/{feature_id}/scope`。

### Preview

Preview 有“AI 临时补全缺失业务流和角色进行仿真演示”的本地 force generation，并可把生成结果 `workspaceApi.save(normalized)` 合并回项目。后端没有同等“预览临时补齐/合并”生命周期，也没有导出 Markdown/JSON 的路由。

### Overview

Overview 显示 Choice、Issue、Slot、Readiness，但 choices/proposals 选择器返回空数组，Issue 由前端本地规则生成。后端的 issues/choice_groups 没接入。

## 九、后端已有但前端未使用的能力

后端已经实现、但前端没有调用的关键能力：

- `GET /api/projects/{project_id}/issues?stage=...`
- `POST /api/projects/{project_id}/issues/resolve`
- `GET /api/projects/{project_id}/next-suggestion?stage=...`
- `POST /api/projects/{project_id}/next-suggestion/start`
- `POST /api/perception_slot_filling_drafts/{actor|feature|scenario|acceptance_criteria|flow}`
- `GET /api/projects/{project_id}/choice_groups`
- `POST /api/projects/{project_id}/choices/{choice_id}/accept`
- `POST /api/projects/{project_id}/choices/{choice_id}/reject`
- `GET /api/projects/{project_id}/audit-logs`
- `PUT /api/projects/{project_id}/user-requirements`
- `POST /api/projects/{project_id}/user-requirements/refine`

这些能力如果要保留，就需要前端新增：

- API client
- response mapper
- polling/background job UI
- issue/slot/choice 状态同步
- audit log 展示/导出

## 十、后端缺失但 UI 暗示存在的能力

以下 UI 或 store action 暗示了后端应有能力，但后端目前没有完整实现或没有公开路由：

- 项目聚合详情读取。
- 项目列表。
- 项目删除。
- 整项目导出 Markdown。
- 整项目导出 JSON。
- Scope 变更影响预览。
- 任意 GraphPatch 应用路由。
- Proposal 创建、接受、拒绝、转 Choice。
- 手动创建 ChoiceGroup/Choice。
- Slot 暂缓、忽略、标记 filled/deferred 的状态路由。
- Screen/Page 原型节点持久化。
- State machine / state transition / field 节点持久化。
- 完整 readiness/checkpoint 后端计算。

## 十一、具体 Stub/Mock 统计

### 前端 Stub/Mock

| 位置 | Stub/Mock 内容 | 风险 |
| --- | --- | --- |
| `frontend/src/lib/api.ts` | 整个 `workspaceApi` 使用 localStorage 和硬编码数据 | 完全未连后端 |
| `workspaceApi.createProjectCreationDraft` | 硬编码 actors/features | AI 结果不是后端生成 |
| `workspaceApi.createActorGenerationDraft` | 硬编码 actors | 不使用后端 actor generation |
| `workspaceApi.createFeatureGenerationDraft` | 硬编码 features | 不使用后端 feature generation |
| `workspaceApi.createFlowGenerationDraft` | 硬编码 BO/flows | 不使用后端 flow generation |
| `workspaceApi.createScenarioGenerationDraft` | 硬编码 scenario | 不使用后端 scenario generation |
| `workspaceApi.createAcceptanceCriteriaGenerationDraft` | 硬编码 AC | 不使用后端 AC generation |
| `workspaceApi.createScopeGenerationDraft` | 硬编码 scope | 不使用后端 Kano/skill |
| `workspaceApi.impactPreview` | 只返回 affected counts | 没有真实依赖分析 |
| `workspaceApi.exportMarkdown/exportJson` | 前端拼装 | 无审计/后端一致性 |
| `detectIssues` | 前端静态规则 | 与后端 IssueService 重复且 ID 不兼容 |
| `normalizeRequirementSpace` | 合成 nodes/links/screens/issues | 后端不持久化这些合成物 |
| `selectChoices/selectProposals` | 永远空数组 | Choice/Proposal UI 无真实数据 |
| `applyPatch` | no-op | 关系编辑、slot 状态不落库 |
| `expandSlot` | no-op | SlotPanel 无法生成 Choice |
| `createSlotFromIssue` | 返回 null | Issue -> Slot 流程断裂 |
| `acceptChoice/rejectChoice` | no-op | ChoicePanel 无效 |
| `runDiagnosis` | 只写提示消息 | 不调用 next-suggestion |
| `rewrite/explainImpact` | no-op | ScopedAIBar 关键动作无效 |
| `acceptProposal/rejectProposal/convertProposalToChoice` | no-op | ProposalPanel 无效 |
| `Preview` force generation | 本地临时造流程/角色/页面 | 与后端生成、审计、ID 均不一致 |

### 后端临时/不完整点

| 位置 | 状态 | 风险 |
| --- | --- | --- |
| generation services `_drafts` | 内存草稿 | 重启/多 worker 丢失 |
| `service_registry.py` | skill backend 只切 project/feature/scenario/ac/scope | actor/flow 仍 legacy |
| aggregate RequirementSpace serializer | 缺失 | 前端无法打开真实项目 |
| project list/detail/delete routes | 缺失 | Home 和 openWorkspace 无法接后端 |
| CORS/proxy | 缺失 | 浏览器跨端口请求失败 |
| GraphPatch route | 缺失 | 前端 patch UI 无法落库 |
| Proposal model/API | 缺失 | 前端 Proposal UI 无后端 |
| business object/flow/scenario list routes | 缺失 | 无聚合路由时无法重建 IR |

## 十二、建议的对齐顺序

### P0：先让应用能跑、能请求

1. 修复前端类型检查：处理 `@/types`、排除 `frontend/backup`、补 React 类型导入、修正 LeftNav 状态类型。
2. 确认后端运行环境安装 `requirements.txt`。
3. 配置 FastAPI CORS 或 Vite `/api` proxy。
4. 新增真实 HTTP client，替换 `frontend/src/lib/api.ts` 的 localStorage mock。

### P1：补齐前端打开项目所需基础 API

1. `GET /api/projects`
2. `GET /api/projects/{project_id}`，返回前端可消费的完整 `RequirementSpace`。
3. `DELETE /api/projects/{project_id}`
4. 统一字段 mapper：后端 snake_case -> 前端 CamelCase。
5. 项目列表 DTO 返回 `updatedAt/status/issueCount/nodeCount`，或前端基于详情计算。

### P2：迁移手动编辑

1. 把 actor/feature/scenario/ac/bo/flow/scope 的 store actions 改为调用后端细粒度 CRUD。
2. 每次 mutation 后重新拉取 `GET /api/projects/{id}`。
3. 移除或保留为 dev-only 的 `workspaceApi.save(space)`。

### P3：迁移 AI 草稿生成

1. project/actor/feature/flow/scenario/ac/scope 生成全部调用后端 draft routes。
2. 前端 `discardDraft` 按 `activeDraftType` 分发到不同后端 DELETE。
3. regenerate 传入用户反馈。
4. 后端草稿若需要跨刷新保留，应持久化到数据库或提供 draft 查询接口。

### P4：接入 Issue/Perception/Choice 闭环

1. 用后端 `GET /issues` 替换或合并前端 `detectIssues`。
2. 用 `next-suggestion` 替换 `runDiagnosis`。
3. 前端保存 `perception_job_id`，支持 perception job 状态轮询。
4. `createSlotFromIssue` 改为调用 `POST /issues/resolve` 或 `next-suggestion/start`。
5. `expandSlot` 调用 slot filling draft routes。
6. `acceptChoice/rejectChoice` 调用后端 choice routes。

### P5：处理 Preview/Export/Impact/Proposal

1. 明确 Preview force generation 是纯前端演示，还是后端正式能力。
2. 新增后端 export markdown/json 路由，或明确继续前端导出。
3. 新增 scope impact preview。
4. 如果 Proposal 是正式概念，补后端 model/API；否则从 UI/store/schema 中移除。

## 十三、推荐的目标架构

建议采用“后端聚合读 + 后端细粒度写 + 前端统一 mapper”的模式：

```text
Frontend UI
  -> useWorkspaceStore actions
  -> workspaceApi HTTP client
  -> response/request mapper
  -> FastAPI routes
  -> services
  -> SQLAlchemy models
```

读路径：

```text
GET /api/projects
GET /api/projects/{project_id}
```

写路径：

```text
POST/PUT/DELETE actors/features/scenarios/business_objects/flows/scope
POST draft create/regenerate/confirm/discard
POST issue resolve / choice accept / slot filling confirm
```

前端永远只持有一个 normalized `RequirementSpace`，但这个 IR 应由后端聚合结果映射而来，不再由 localStorage 作为事实源。

## 十四、最小联调切片

如果要最快验证前后端真正连通，建议先做这个最小闭环：

1. 后端新增 `GET /api/projects` 和 `GET /api/projects/{id}` 聚合读取。
2. 前端 `workspaceApi.list/getById/createBlankProject/createProjectCreationDraft/confirmProjectCreationDraft` 改 HTTP。
3. 后端 project creation confirm 后，前端能通过 `getById` 打开真实 DB 项目。
4. 前端 actor 新增/编辑/删除改为后端 actor CRUD。
5. mutation 后 refresh 聚合详情。

这个切片完成后，Home -> Onboarding -> 打开项目 -> What 页面编辑角色 这条主链路才算真正联通。
