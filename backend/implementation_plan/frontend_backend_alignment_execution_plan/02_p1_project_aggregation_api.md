# P1：项目聚合读取 API 与前端打开项目主链路

## 一、阶段目标

补齐前端最依赖的基础项目 API，使前端 Home、Onboarding、OpenWorkspace 能使用真实后端数据库。

本阶段完成后，用户应可以：

1. 在 Home 页面看到后端项目列表。
2. 创建空白项目或确认 AI 项目草稿后，打开真实后端项目。
3. 前端拿到完整 `RequirementSpace` 聚合 IR，而不是 localStorage 数据。

## 二、背景问题

前端当前依赖：

- `workspaceApi.list()`
- `workspaceApi.getById(id)`
- `workspaceApi.delete(id)`
- `workspaceApi.createBlankProject(...)`
- `workspaceApi.createProjectCreationDraft(...)`
- `workspaceApi.confirmProjectCreationDraft(...)`

后端已有：

- `POST /api/blank_projects`
- `POST /api/project_creation_drafts`
- `POST /api/project_creation_drafts/{draft_id}/confirm`

后端缺失：

- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `DELETE /api/projects/{project_id}`

## 三、范围

### 本阶段必须做

1. 后端新增项目列表路由。
2. 后端新增项目详情聚合路由。
3. 后端新增项目删除路由。
4. 前端 `workspaceApi.list/getById/delete/createBlankProject/projectCreationDraft` 迁移到真实 HTTP。
5. 前端建立后端 DTO -> `RequirementSpace` mapper。

### 本阶段不做

- 不迁移所有手动 CRUD。
- 不迁移 AI actor/feature/flow/scenario/ac/scope 生成。
- 不接 Issue/Choice/Perception。
- 不做 export/impact preview。

## 四、后端 API 设计

### 1. GET /api/projects

返回项目列表卡片。

建议响应：

```json
[
  {
    "id": "1",
    "project_id": 1,
    "name": "项目名",
    "idea": "用户原始需求",
    "updated_at": "2026-05-24T12:00:00+08:00",
    "status": "设计中",
    "issue_count": 0,
    "node_count": 12
  }
]
```

前端可以映射为：

```ts
WorkspaceListItem {
  id: string;
  name: string;
  idea: string;
  updatedAt: string;
  status: string;
  issueCount: number;
  nodeCount: number;
}
```

### 2. GET /api/projects/{project_id}

返回完整聚合 `RequirementSpace`。

建议后端直接返回前端可消费的 CamelCase：

```json
{
  "kind": "requirement_space",
  "projectId": 1,
  "projectName": "项目名",
  "projectDescription": "描述",
  "userRequirements": "原始需求",
  "perceptionSlot": null,
  "actors": [],
  "features": [],
  "businessObjects": [],
  "flows": []
}
```

如果后端坚持 snake_case，则前端 mapper 必须统一转换，不允许页面直接使用 snake_case。

聚合需要加载：

- project
- perception_slot
- actors
- features
- feature parent/children relations
- feature actors
- scenarios
- acceptance criteria
- feature scope
- business objects
- attributes
- flows
- flow features
- flow steps
- flow step actors/input/output/next steps

### 3. DELETE /api/projects/{project_id}

删除项目及其级联数据。

响应：

```json
{
  "project_id": 1,
  "message": "project_deleted"
}
```

## 五、后端实现任务

### 任务 1：新增 schema

建议新增：

- `backend/api/schemas/project_schema.py`
  - `ProjectListItemResponse`
  - `ProjectDetailResponse` 或复用 `backend.schemas.RequirementSpace`
  - `ProjectDeleteResponse`

### 任务 2：新增 service

建议新增：

- `backend/api/services/project_service.py`

职责：

- list projects
- get project detail
- delete project
- serialize aggregate requirement space

### 任务 3：新增 route

建议新增：

- `backend/api/routes/project_routes.py`

并在 `backend/main.py` 注册。

### 任务 4：聚合 serializer

serializer 必须保证：

- feature `parentId` 正确。
- feature `childrenIds` 顺序稳定。
- feature `actorIds` 正确。
- scenario 嵌套在对应 feature 下。
- acceptance criteria 嵌套在 scenario 下。
- business object attributes 嵌套在 business object 下。
- flow steps 嵌套在 flow 下。
- flow step `nextStepIds` 正确。
- scope 图片字段如暂不返回，明确为 `null`。

### 任务 5：列表统计

`node_count` 至少统计：

- actors
- features
- scenarios
- acceptance criteria
- business objects
- attributes
- flows
- flow steps

`issue_count` 可在 P1 先返回 0 或调用现有 detector。若返回 0，需在响应字段或代码注释中标注 P4 接入 IssueService 后再真实计算。

## 六、前端实现任务

### 任务 1：迁移 list/getById/delete

替换 localStorage：

- `workspaceApi.list()` -> `GET /api/projects`
- `workspaceApi.getById(id)` -> `GET /api/projects/{id}`
- `workspaceApi.delete(id)` -> `DELETE /api/projects/{id}`

### 任务 2：迁移 blank project

`workspaceApi.createBlankProject(payload)` -> `POST /api/blank_projects`

confirm 后继续调用 `getById(project_id)` 打开项目。

### 任务 3：迁移 project creation draft

- `createProjectCreationDraft` -> `POST /api/project_creation_drafts`
- `regenerateProjectCreationDraft` -> `POST /api/project_creation_drafts/{draft_id}/regenerate`
- `confirmProjectCreationDraft` -> `POST /api/project_creation_drafts/{draft_id}/confirm`
- `discardProjectCreationDraft` -> `DELETE /api/project_creation_drafts/{draft_id}`

### 任务 4：建立 mapper 测试样例

至少准备一个后端响应 fixture，验证前端 mapper 输出：

- `projectId`
- `projectName`
- `actors`
- `features`
- `businessObjects`
- `flows`
- `perceptionSlot`

### 任务 5：移除自动初始化 demo 数据

`ensureInitialProjects()` 当前会往 localStorage 塞 demo。P1 后默认不应自动创建前端本地项目。

可以保留为：

- `VITE_USE_MOCK_API=true` 时启用。
- 或移动到 Storybook/dev fixture。

## 七、验收标准

P1 验收必须全部满足：

1. 清空浏览器 localStorage 后，Home 仍能展示后端项目列表。
2. 创建空白项目后，数据库新增 project，前端跳转并打开该项目。
3. AI 项目创建草稿 confirm 后，数据库新增 project/actors/features，前端通过 `GET /api/projects/{id}` 打开。
4. 刷新浏览器后，当前项目仍从后端恢复。
5. 删除项目后，Home 列表不再展示该项目，数据库项目被删除。
6. 浏览器 Network 面板可看到真实 `/api/projects`、`/api/projects/{id}` 请求。
7. `workspaceApi.getById` 不再读取 `localStorage`。
8. What 页面能正确展示后端返回的 actors/features。

## 八、测试建议

后端：

- project list 空列表。
- project detail 空白项目。
- project detail 带 actor/feature/scenario/scope/flow 的复杂项目。
- delete project 后级联数据不存在。

前端：

- mapper fixture test。
- Home loadWorkspaces。
- openWorkspace。
- createBlankWorkspace。
- confirmAIOnboarding。

## 九、风险与处理

| 风险 | 处理 |
| --- | --- |
| 聚合 serializer 复杂 | 先覆盖当前 UI 必需字段，暂不返回 nodes/links/issues 兼容字段，由前端 normalize 继续合成 |
| issue_count 暂不真实 | P1 可返回 0，P4 再接真实 IssueService |
| CamelCase/SnakeCase 争议 | 推荐后端聚合接口直接面向前端 IR 返回 CamelCase，细粒度 CRUD 保持 snake_case |

## 十、进入 P2 的条件

P1 通过后，进入 P2 前需确认：

- 前端打开项目不依赖 localStorage。
- `RequirementSpace` 聚合字段稳定。
- 每次后端 mutation 后可以通过 `getById` 重新同步前端状态。
- 手动 CRUD 迁移可以逐个替换，不会影响项目打开主链路。
