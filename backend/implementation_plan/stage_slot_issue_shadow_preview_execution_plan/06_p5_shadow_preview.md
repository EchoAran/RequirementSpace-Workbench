# P5：Shadow Preview 与影子需求空间

## 1. 阶段目标

P5 的目标是让 Preview 页面始终可访问，同时保证未收敛项目不会被系统自动补齐内容污染。

完成后：

1. 已收敛项目进入 Preview 时，直接展示真实项目原型。
2. 未收敛项目进入 Preview 时，提示用户生成影子方案。
3. 影子方案只保存在 shadow draft 中，不写入真实项目。
4. 用户采纳后，影子补齐内容才写回真实项目。
5. 用户丢弃后，真实项目无变化。

## 2. 改造范围

主要文件：

```text
frontend/src/pages/Preview.tsx
frontend/src/store/useWorkspaceStore.ts
frontend/src/lib/api.ts
backend/api/routes/preview_shadow_routes.py
backend/api/services/preview_shadow_convergence_service.py
backend/api/services/prototype_generation_service.py
backend/core/generators/prototype_generator.py
backend/database/model.py
backend/database/database.py
```

## 3. 数据模型

新增表建议：

```text
preview_shadow_drafts
```

字段：

```text
id
project_id
draft_id
status
source
base_snapshot_json
shadow_snapshot_json
patch_json
prototype_preview_json
prototype_preview_id
error_message
created_at
updated_at
committed_at
```

状态：

```text
generating
ready
failed
committed
discarded
```

## 4. API 设计

### 4.1 创建或准备 Preview

```http
POST /api/projects/{project_id}/preview-shadow-drafts
```

行为：

- 后端先计算 What/How/Scope Gate。
- 如果全部通过，返回 `source = real_project`。
- 如果未全部通过，创建 shadow draft。

响应关键字段：

```json
{
  "source": "shadow_project",
  "draft_id": "shadow_xxx",
  "status": "ready",
  "unready_gates": ["what", "how"],
  "shadow_summary": {},
  "prototype_preview": {}
}
```

### 4.2 查询 shadow draft

```http
GET /api/projects/{project_id}/preview-shadow-drafts/{draft_id}
```

### 4.3 重新生成

```http
POST /api/projects/{project_id}/preview-shadow-drafts/{draft_id}/regenerate
```

### 4.4 采纳写回

```http
POST /api/projects/{project_id}/preview-shadow-drafts/{draft_id}/commit
```

### 4.5 丢弃

```http
DELETE /api/projects/{project_id}/preview-shadow-drafts/{draft_id}
```

## 5. Shadow Convergence 流程

```text
读取真实项目 -> base snapshot
计算 Gate -> missing kinds
按顺序补齐 What/How/Scope -> shadow snapshot
生成 patch
基于 shadow snapshot 生成 prototype preview
保存 shadow draft
返回前端
```

补齐顺序：

1. Actor。
2. Feature。
3. Feature-Actor binding。
4. Scenario。
5. Acceptance Criteria。
6. Flow。
7. Flow Step。
8. Business Object。
9. Business Object Attribute。
10. Scope decision。
11. Kano generated 或 skipped。
12. Prototype preview。

## 6. Prototype Generator 适配

需要支持两种输入：

```python
source = "project"
project_id = 1
snapshot = None
```

或：

```python
source = "snapshot"
project_id = 1
snapshot = shadow_snapshot
```

原则：

- 真实项目预览可以继续读取数据库。
- 影子预览必须从 shadow snapshot 读取。
- 影子预览结果不应覆盖真实项目 latest preview。

## 7. Commit 写回策略

提交时必须使用事务：

1. 校验 draft 状态为 `ready`。
2. 校验 draft 未过期或未冲突。
3. 写入新增 Actor、Feature、Scenario、AC、Flow、BO、Scope。
4. 建立临时 ID 到真实 ID 映射。
5. 重映射引用关系。
6. 标记 draft 为 `committed`。
7. 重新计算 Gate/Issue/Slot。
8. 返回最新 workspace。

第一版冲突策略：

- 如果 shadow draft 创建后真实项目结构发生变化，commit 返回 `shadow_draft_conflict`。
- 前端提示重新生成 shadow draft。

## 8. 前端 Preview 交互

Preview 加载逻辑：

1. 调用 prepare/create 接口。
2. 如果返回 `real_project`，直接展示 iframe。
3. 如果返回 `shadow_project`，展示提示 banner。
4. 用户可以查看 shadow prototype。
5. 用户可以查看 shadow summary。
6. 用户可以采纳、重新生成、丢弃。

提示文案方向：

```text
当前需求空间尚未完全收敛。系统已为你临时补全一个影子方案用于预览。
这些补全内容尚未写入项目，采纳后才会同步到真实需求空间。
```

## 9. 验收标准

1. 未收敛项目可以进入 Preview。
2. 未收敛项目进入 Preview 时不会直接写真实数据库。
3. Shadow prototype 可以正常 iframe 展示。
4. 用户丢弃 shadow draft 后，真实项目无变化。
5. 用户 commit shadow draft 后，真实项目出现补齐内容。
6. commit 后 Gate/Issue/Slot 状态刷新。
7. 真实项目已收敛时，Preview 不进入 shadow 模式。
8. shadow draft 冲突时，commit 被拒绝并提示重新生成。

## 10. 对接后续

P5 完成后，工作台将具备完整的“提前看未来方案”能力。

后续可继续扩展：

- shadow diff 可视化。
- 局部采纳。
- 多版本 preview 对比。
- 智能冲突 merge。

