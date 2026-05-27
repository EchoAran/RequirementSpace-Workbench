# P3：AI 草稿生成生命周期迁移

## 一、阶段目标

将前端所有 AI 生成草稿从 localStorage Mock 迁移到后端 draft routes，实现生成、重生成、确认、丢弃的真实后端生命周期。

本阶段完成后，前端的：

- 项目创建推演
- 角色生成
- 功能生成
- 流程与业务对象生成
- 场景生成
- 成功标准生成
- 范围/Kano 生成

都应通过后端服务完成。

## 二、背景问题

前端当前 `workspaceApi` 中每类 draft 都是硬编码数据，并保存到 `rs_workspace_drafts`。

后端已有 draft routes：

- `/api/project_creation_drafts`
- `/api/actor_generation_drafts`
- `/api/feature_generation_drafts`
- `/api/flow_generation_drafts`
- `/api/scenario_generation_drafts/full|single`
- `/api/acceptance_criteria_generation_drafts/full|single|batch`
- `/api/scope_generation_drafts`

但后端草稿当前存储在 service 实例内存 `_drafts`，重启会丢失。

## 三、范围

### 本阶段必须做

1. 前端迁移所有 generation draft create/confirm/discard。
2. 前端迁移 regenerate，并传递 user feedback。
3. 前端根据 draft type 分发到正确后端路由。
4. confirm 后刷新聚合项目详情。
5. 明确内存 draft 的产品限制。

### 本阶段可选做

- 草稿持久化到数据库。
- 草稿详情查询 `GET /drafts/{id}`。

### 本阶段不做

- 不处理 Issue/Slot/Choice。
- 不处理 Preview force generation。
- 不统一 skill 和 legacy 生成质量。

## 四、前端 API 迁移对照

### Project Creation

| 前端方法 | 后端 API |
| --- | --- |
| `createProjectCreationDraft(payload)` | `POST /api/project_creation_drafts` |
| `regenerateProjectCreationDraft(draftId, feedback)` | `POST /api/project_creation_drafts/{draft_id}/regenerate` |
| `confirmProjectCreationDraft(draftId)` | `POST /api/project_creation_drafts/{draft_id}/confirm` |
| `discardProjectCreationDraft(draftId)` | `DELETE /api/project_creation_drafts/{draft_id}` |

### Actor

| 前端方法 | 后端 API |
| --- | --- |
| `createActorGenerationDraft(projectId)` | `POST /api/actor_generation_drafts` |
| `confirmActorGenerationDraft(draftId)` | `POST /api/actor_generation_drafts/{draft_id}/confirm` |
| `discard` | `DELETE /api/actor_generation_drafts/{draft_id}` |

### Feature

| 前端方法 | 后端 API |
| --- | --- |
| `createFeatureGenerationDraft(projectId)` | `POST /api/feature_generation_drafts` |
| `confirmFeatureGenerationDraft(draftId)` | `POST /api/feature_generation_drafts/{draft_id}/confirm` |
| `discard` | `DELETE /api/feature_generation_drafts/{draft_id}` |

### Flow

| 前端方法 | 后端 API |
| --- | --- |
| `createFlowGenerationDraft(projectId)` | `POST /api/flow_generation_drafts` |
| `confirmFlowGenerationDraft(draftId)` | `POST /api/flow_generation_drafts/{draft_id}/confirm` |
| `discard` | `DELETE /api/flow_generation_drafts/{draft_id}` |

### Scenario

| 前端方法 | 后端 API |
| --- | --- |
| `createScenarioGenerationDraft(projectId)` | `POST /api/scenario_generation_drafts/full` |
| `createScenarioGenerationDraft(projectId, featureId)` | `POST /api/scenario_generation_drafts/single` |
| `confirmScenarioGenerationDraft(draftId, { generate_acceptance_criteria })` | `POST /api/scenario_generation_drafts/{draft_id}/confirm` |
| `discard` | `DELETE /api/scenario_generation_drafts/{draft_id}` |

### Acceptance Criteria

| 前端方法 | 后端 API |
| --- | --- |
| `createAcceptanceCriteriaGenerationDraft(projectId)` | `POST /api/acceptance_criteria_generation_drafts/full` |
| `createAcceptanceCriteriaGenerationDraft(projectId, [oneId])` | `POST /api/acceptance_criteria_generation_drafts/single` |
| `createAcceptanceCriteriaGenerationDraft(projectId, scenarioIds)` | `POST /api/acceptance_criteria_generation_drafts/batch` |
| `confirmAcceptanceCriteriaGenerationDraft(draftId)` | `POST /api/acceptance_criteria_generation_drafts/{draft_id}/confirm` |
| `discard` | `DELETE /api/acceptance_criteria_generation_drafts/{draft_id}` |

### Scope

| 前端方法 | 后端 API |
| --- | --- |
| `createScopeGenerationDraft(projectId)` | `POST /api/scope_generation_drafts` |
| `confirmScopeGenerationDraft(draftId)` | `POST /api/scope_generation_drafts/{draft_id}/confirm` |
| `discard` | `DELETE /api/scope_generation_drafts/{draft_id}` |

## 五、前端实现任务

### 任务 1：扩展 activeDraft metadata

当前只有：

- `activeDraft`
- `activeDraftType`

建议新增：

- `activeDraftCreatedAt`
- `activeDraftSource: 'backend' | 'mock'`
- `activeDraftCanRegenerate`
- `activeDraftProjectId`

这样 UI 可以识别草稿丢失或过期。

### 任务 2：实现统一 discard 分发

当前 `discardDraft(draftId)` 不区分类型。后端每类草稿 DELETE 路径不同。

实现：

```ts
discardDraft: async () => {
  switch (activeDraftType) {
    case 'actor': DELETE /api/actor_generation_drafts/{id}
    case 'feature': DELETE /api/feature_generation_drafts/{id}
    ...
  }
}
```

### 任务 3：传递 regenerate feedback

ProjectOnboarding 当前有 `feedback` 输入，但 store 没有传给 API。

需要：

- `regenerateAIOnboarding(feedback?: string)`
- 其他生成面板如未来有反馈输入，也复用 `DraftRegenerateRequest`。

### 任务 4：confirm 后统一 refresh

所有 confirm 完成后：

1. 清空 activeDraft。
2. 清空 activeDraftType。
3. `await refreshWorkspace()`。
4. 展示 `lastActionMessage`。

Project creation confirm 需要：

1. 根据 response `project_id` 调用 `getById`。
2. 切换到 workspace view。

### 任务 5：错误状态处理

必须处理：

- `draft_not_found`
- `project_not_found`
- `empty_*`
- `invalid_*`
- LLM/skill 相关 502 或 400

UI 行为：

- draft_not_found：提示“草稿已失效，请重新生成”，清空 activeDraft。
- project_not_found：回到 Home 或提示刷新项目列表。
- empty/invalid：保留当前页面，展示错误详情。

## 六、后端实现任务

### 任务 1：确认所有 draft routes 注册

通过 app routes 确认：

- project creation
- actor generation
- feature generation
- flow generation
- scenario generation
- acceptance criteria generation
- scope generation

### 任务 2：统一 regenerate request

所有 regenerate route 已基本支持 `DraftRegenerateRequest`。需要确认：

- request body 为空时不报错。
- `user_feedback` 能进入 generator/skill。
- response 结构与 create draft 一致。

### 任务 3：记录内存 draft 限制

如果本阶段不做持久化，则需要在计划或 README 标注：

- 后端重启后草稿失效。
- 不支持多 worker。
- 刷新前端页面后 activeDraft 可能丢失。

### 任务 4：可选草稿持久化

如要生产化，新增：

- `generation_drafts` 表：
  - `id`
  - `project_id`
  - `draft_type`
  - `payload`
  - `status`
  - `created_at`
  - `updated_at`
  - `expires_at`

并提供：

- `GET /api/generation_drafts/{draft_id}`
- 统一 `DELETE /api/generation_drafts/{draft_id}`

本任务可推迟，但必须形成产品决策。

## 七、验收标准

P3 验收必须全部满足：

1. 前端所有 AI 生成按钮触发真实后端 `/api/*generation_drafts*` 请求。
2. 每类 draft preview UI 能展示后端返回内容。
3. 每类 confirm 后数据真实落库，刷新页面仍存在。
4. 每类 discard 后草稿不可继续 confirm。
5. regenerate 能把用户反馈传到后端 request body。
6. `draft_not_found` 有明确 UI 处理。
7. `rs_workspace_drafts` 不再作为默认草稿事实源。
8. Project creation、actor、feature、flow、scenario、AC、scope 至少各完成一次端到端验收。

## 八、分场景验收

### Project Creation

1. 输入需求。
2. 生成项目草稿。
3. 输入反馈并重生成。
4. 确认草稿。
5. 打开新项目。
6. 刷新页面确认数据存在。

### Actor/Feature

1. 打开空白项目。
2. 生成角色草稿，确认。
3. 生成功能草稿，确认。
4. What 页面显示角色和功能。

### Flow/Scenario/AC/Scope

1. 基于已有角色和功能生成流程。
2. 生成场景。
3. 生成成功标准。
4. 生成范围。
5. How/Scope 页面显示结果。

## 九、风险与处理

| 风险 | 处理 |
| --- | --- |
| LLM 结果不稳定 | 验收时允许使用固定输入，必要时后端支持 mock generator profile |
| 内存 draft 丢失 | UI 识别 draft_not_found 并引导重新生成 |
| skill backend 与 legacy 混用 | 在 UI 不暴露 backend 差异，但测试记录实际 env |
| 生成结果字段与 UI 不匹配 | 统一 mapper 和 draft response 类型 |

## 十、进入 P4 的条件

P3 通过后，进入 P4 前需确认：

- 手动 CRUD 和 AI confirm 后都能通过聚合详情恢复。
- activeDraft 生命周期不再依赖 localStorage。
- 后端 generation routes 的错误码和 detail 已被前端统一处理。
- 下一阶段可以基于真实项目结构运行 IssueService 和 PerceptionJob。
