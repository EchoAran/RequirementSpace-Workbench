# P2：What 阶段闭环与 Feature-Actor 手动绑定

## 1. 阶段目标

P2 的目标是让 What 阶段能够真正闭环。

当前 What 阶段依赖 AI 生成角色、功能、场景和验收标准，但用户手动补齐能力不足，尤其是 Feature 与 Actor 的绑定入口不完整。

P2 完成后，用户应能通过手动操作补齐 What Gate 所需全部条件。

## 2. 改造范围

主要文件：

```text
frontend/src/pages/WhatToDo.tsx
frontend/src/components/shared/RightObjectPanel.tsx
frontend/src/store/useWorkspaceStore.ts
frontend/src/lib/api.ts
backend/api/routes/project_routes.py 或 feature_routes.py
backend/api/services/project_service.py 或 feature_service.py
```

具体以后端现有 API 结构为准。

## 3. 核心任务

### 3.1 Feature-Actor 绑定 UI

在 Feature 编辑面板中增加 Actor 多选控件：

- 展示当前项目所有 Actor。
- 勾选表示绑定。
- 取消勾选表示解绑。
- 保存后更新 Feature 的 `actorIds`。

交互要求：

- 叶子 Feature 缺少 Actor 时，卡片上应有明显但不过度警告的提示。
- 非叶子 Feature 可不强制绑定 Actor。
- Slot 手动处理可以高亮目标 Feature 并打开编辑面板。

### 3.2 Feature 卡片展示绑定状态

Feature 节点卡片至少展示：

- 关联 Actor 数量。
- Actor 名称摘要。
- 无 Actor 时显示“未绑定角色”。

### 3.3 Scenario 与 AC Gate 联动

What Gate 要求：

- 每个叶子 Feature 至少有 Scenario。
- 每个 Scenario 至少有 AC。

需要确保：

- Scenario 管理弹窗能从目标 Feature 快速打开。
- AC 管理入口清晰。
- 生成 Scenario 后的 draft 确认仍在弹窗预览中完成。

### 3.4 Slot 手动定位

What 阶段 Slot 的 manual action 应能定位到：

- Actor 创建入口。
- Feature 创建入口。
- 具体 Feature 卡片。
- 具体 Scenario 管理弹窗。
- 具体 AC 缺失的 Scenario。

### 3.5 API 适配

如果现有 `updateFeature` 已支持 actorIds：

- 前端直接复用。

如果不支持：

新增或扩展接口：

```http
PUT /api/projects/{project_id}/features/{feature_id}
```

请求可包含：

```json
{
  "actor_ids": [1, 2]
}
```

或者新增专门绑定接口：

```http
PUT /api/projects/{project_id}/features/{feature_id}/actors
```

## 4. 验收标准

1. 用户可以手动给叶子 Feature 绑定 Actor。
2. 用户可以手动解绑 Actor。
3. 保存后刷新页面，绑定关系仍存在。
4. 缺少 Actor 的叶子 Feature 会阻塞 What Gate。
5. 绑定 Actor 后，对应 blocking Slot 消失或转向下一优先级缺口。
6. 全部叶子 Feature 有 Actor、Scenario、AC 后，What Gate 通过。
7. What Gate 通过后，`/flow` 可进入。

## 5. 对接下一阶段

P2 完成后，How 阶段可以依赖稳定的 What 数据：

- Flow Step 可引用已定义 Actor。
- Flow 生成器和手动编辑器可以基于叶子 Feature 与 Actor 关系工作。
- Shadow Preview 的 What 补齐逻辑可以复用 Feature-Actor binding 的写入能力。

