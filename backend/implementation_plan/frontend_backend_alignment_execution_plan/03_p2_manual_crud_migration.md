# P2：手动编辑 CRUD 迁移

## 一、阶段目标

把前端所有手动编辑动作从 `workspaceApi.save(updatedRequirementSpace)` 迁移到后端细粒度 CRUD，让用户在 UI 中新增、编辑、删除节点后，数据真实落库并可刷新恢复。

本阶段完成后，前端 `workspaceApi.save(space)` 不再作为默认写入路径。

## 二、背景问题

当前前端手动编辑统一模式：

1. 从 `ir` 克隆和修改完整 `RequirementSpace`。
2. `set({ ir: updated })` 乐观更新。
3. `await workspaceApi.save(updated)` 保存整项目到 localStorage。

后端没有整项目覆盖保存接口，而是已有细粒度 CRUD：

- actor
- feature
- scenario
- acceptance criterion
- business object
- business object attribute
- flow
- flow step
- scope

## 三、范围

### 本阶段必须做

1. 迁移 actor 手动 CRUD。
2. 迁移 feature 手动 CRUD。
3. 迁移 scenario 和 acceptance criterion 手动 CRUD。
4. 迁移 business object 和 attribute 手动 CRUD。
5. 迁移 flow 和 flow step 手动 CRUD。
6. 迁移 scope update。
7. 所有 mutation 后统一 refresh 聚合项目详情。

### 本阶段不做

- 不处理 AI generation draft。
- 不处理 Issue/Slot/Choice。
- 不处理 Preview force generation 合并。
- 不新增 Proposal 后端能力。

## 四、迁移策略

推荐采用“后端写入 + 重新拉取聚合详情”的保守策略：

```text
UI action
  -> store action
  -> workspaceApi.xxx HTTP call
  -> refreshWorkspace()
  -> normalizeRequirementSpace()
```

短期不建议复杂乐观更新。原因：

- 后端会生成真实自增 ID。
- feature relation、flow step position、next steps 需要以后端为准。
- 前端本地随机 ID 与后端 DB ID 容易冲突。

## 五、API 对照表

### Actor

| 前端 action | 后端 API |
| --- | --- |
| `addActor(name, description)` | `POST /api/projects/{project_id}/actors` |
| `updateActor(actorId, updates)` | `PUT /api/projects/{project_id}/actors/{actor_id}` |
| `deleteActor(actorId)` | `DELETE /api/projects/{project_id}/actors/{actor_id}` |

### Feature

| 前端 action | 后端 API |
| --- | --- |
| `addFeature(name, description, parentId)` | `POST /api/projects/{project_id}/features` |
| `updateFeature(featureId, updates)` | `PUT /api/projects/{project_id}/features/{feature_id}` |
| `deleteFeature(featureId)` | `DELETE /api/projects/{project_id}/features/{feature_id}` |

注意：

- `FeatureUpdateRequest` 支持 `actor_ids`。
- feature rename/description 和 actor binding 应共用该接口。

### Scenario / Acceptance Criterion

| 前端 action | 后端 API |
| --- | --- |
| `addScenario(featureId, actorId, name, content)` | `POST /api/projects/{project_id}/scenarios` |
| `updateScenario(featureId, scenarioId, updates)` | `PUT /api/projects/{project_id}/scenarios/{scenario_id}` |
| `deleteScenario(featureId, scenarioId)` | `DELETE /api/projects/{project_id}/scenarios/{scenario_id}` |
| `addAcceptanceCriterion(featureId, scenarioId, content)` | `POST /api/projects/{project_id}/scenarios/{scenario_id}/acceptance_criteria` |
| `updateAcceptanceCriterion(featureId, scenarioId, criterionId, content)` | `PUT /api/projects/{project_id}/scenarios/{scenario_id}/acceptance_criteria/{ac_id}` |
| `deleteAcceptanceCriterion(featureId, scenarioId, criterionId)` | `DELETE /api/projects/{project_id}/scenarios/{scenario_id}/acceptance_criteria/{ac_id}` |

### Business Object / Attribute

| 前端 action | 后端 API |
| --- | --- |
| `addBusinessObject(name, description)` | `POST /api/projects/{project_id}/business_objects` |
| `updateBusinessObject(id, name, description)` | `PUT /api/projects/{project_id}/business_objects/{bo_id}` |
| `deleteBusinessObject(id)` | `DELETE /api/projects/{project_id}/business_objects/{bo_id}` |
| `addBusinessObjectAttribute(...)` | `POST /api/projects/{project_id}/business_objects/{bo_id}/attributes` |
| `updateBusinessObjectAttribute(...)` | `PUT /api/projects/{project_id}/business_objects/{bo_id}/attributes/{attr_id}` |
| `deleteBusinessObjectAttribute(...)` | `DELETE /api/projects/{project_id}/business_objects/{bo_id}/attributes/{attr_id}` |

### Flow / Flow Step

| 前端 action | 后端 API |
| --- | --- |
| `addFlow(name, description, featureIds)` | `POST /api/projects/{project_id}/flows` |
| `updateFlow(flowId, updates)` | `PUT /api/projects/{project_id}/flows/{flow_id}` |
| `deleteFlow(flowId)` | `DELETE /api/projects/{project_id}/flows/{flow_id}` |
| `addFlowStep(flowId, step)` | `POST /api/projects/{project_id}/flows/{flow_id}/steps` |
| `updateFlowStep(flowId, stepId, updates)` | `PUT /api/projects/{project_id}/flows/{flow_id}/steps/{step_id}` |
| `deleteFlowStep(flowId, stepId)` | `DELETE /api/projects/{project_id}/flows/{flow_id}/steps/{step_id}` |

### Scope

| 前端 action | 后端 API |
| --- | --- |
| `updateScope(featureId, updates)` | `PUT /api/projects/{project_id}/features/{feature_id}/scope` |

## 六、前端实现任务

### 任务 1：扩展 workspaceApi

为每个后端 CRUD 增加方法：

- `createActor`
- `updateActor`
- `deleteActor`
- `createFeature`
- `updateFeature`
- `deleteFeature`
- ...

方法入参保持前端 store 好用，内部转换为后端 request body。

### 任务 2：重写 store actions

每个 store action 改为：

1. 获取当前 `projectId`。
2. 调用后端 API。
3. `await get().refreshWorkspace()`。
4. 设置 `lastActionMessage`。
5. 如删除当前选中对象，清空 selection。

### 任务 3：错误处理

所有 action 捕获后端错误：

- 404：对象不存在，提示刷新。
- 400：参数/引用错误，提示具体 `detail`。
- 500：服务异常，提示重试。

### 任务 4：移除随机 ID 写入路径

以下场景不再由前端生成最终 ID：

- actorId
- featureId
- scenarioId
- criterionId
- businessObjectId
- flowId
- stepId

前端可以临时显示 loading item，但最终 ID 必须来自后端。

### 任务 5：保留 normalizeRequirementSpace

`normalizeRequirementSpace` 仍可保留，用于合成：

- nodes
- links
- issuesCompatible
- actorsCompatible
- flowStepsCompatible
- scopeItemsCompatible

但它不应再负责“保存事实源”。

## 七、后端补充任务

### 任务 1：确认 CRUD 响应与聚合刷新兼容

每个 mutation 后，即使单接口响应字段是 snake_case，也要保证 `GET /api/projects/{id}` 能立即反映变更。

### 任务 2：完善缺失校验

重点检查：

- feature parent 必须属于同项目。
- actor_ids 必须属于同项目。
- scenario feature/actor 必须属于同项目。
- flow feature_ids 必须属于同项目。
- flow step input/output BO IDs 必须属于同项目。
- next_step_ids 必须属于同 flow。

### 任务 3：审计日志一致性

已有多个 service 会写 `AuditLogModel`。本阶段应确认所有手动 CRUD 都有审计日志，便于 P5 export audit。

## 八、页面验收路径

### What 页面

验收动作：

1. 新增 actor。
2. 编辑 actor 名称和描述。
3. 删除 actor。
4. 新增 feature。
5. 编辑 feature。
6. 绑定/解绑 actor。
7. 新增 scenario。
8. 新增 acceptance criterion。
9. 刷新页面，所有数据保持一致。

### How 页面

验收动作：

1. 新增 business object。
2. 新增 attribute。
3. 编辑 attribute。
4. 新增 flow。
5. 新增 flow step。
6. 绑定 actor/input/output BO。
7. 编辑 next step。
8. 删除 step/flow/object。
9. 刷新页面，流程图和对象面板保持一致。

### Scope 页面

验收动作：

1. 修改 feature scope 到 `本期`。
2. 修改到 `暂缓`。
3. 修改到 `排除`。
4. 编辑 reason、positive/negative summary。
5. 刷新页面，Kanban 分组保持一致。

## 九、验收标准

P2 验收必须全部满足：

1. 所有手动 CRUD 操作在 Network 面板中出现对应 `/api/...` 请求。
2. 所有手动 CRUD 操作刷新页面后仍保留。
3. 前端默认路径不再调用 `workspaceApi.save(space)`。
4. 新增对象 ID 来自后端数据库，不再使用前端随机 ID 作为最终 ID。
5. 删除对象后，相关引用正确清理或后端返回明确错误。
6. 聚合详情接口能反映每次 mutation。
7. 手动编辑产生审计日志，`GET /api/projects/{id}/audit-logs` 可看到记录。
8. `npm run lint` 通过。

## 十、风险与处理

| 风险 | 处理 |
| --- | --- |
| mutation 后全量 refresh 性能一般 | 当前数据规模小，优先一致性；后续再做局部缓存 |
| 删除级联与前端预期不一致 | 以数据库级联和后端 service 为准，前端展示删除后结果 |
| 前端某些 UI 仍调用 applyPatch | P2 先记录，不在本阶段接 patch engine，P4/P5 处理 |

## 十一、进入 P3 的条件

P2 通过后，进入 P3 前需确认：

- 手动创建的项目结构已全部在后端持久化。
- 前端 store 不再需要整项目保存来支持基础编辑。
- AI 生成草稿 confirm 后可以复用 P2 的刷新机制。
- 聚合详情 serializer 已覆盖 AI 生成后落库的数据结构。
