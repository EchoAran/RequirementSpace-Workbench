# P3：How 阶段手动 Flow、Step 与数据对象编辑

## 1. 阶段目标

P3 的目标是让 How 阶段摆脱完全依赖 AI 自动推演的状态，补齐手动编辑闭环。

完成后，用户应能够：

1. 手动新增业务流。
2. 手动新增、编辑、删除流程步骤。
3. 调整步骤顺序或拓扑关系。
4. 手动新增、编辑、删除 Business Object。
5. 手动新增、编辑、删除 Business Object Attribute。
6. 通过手动操作让 How Gate 收敛。

## 2. 改造范围

主要文件：

```text
frontend/src/pages/HowItWorks.tsx
frontend/src/store/useWorkspaceStore.ts
frontend/src/lib/api.ts
frontend/src/components/shared/RightObjectPanel.tsx
backend/api/routes/project_routes.py 或 flow_routes.py
backend/api/services/project_service.py 或 flow_service.py
backend/database/model.py
```

## 3. 核心任务

### 3.1 新增自定义 Flow

UI 入口：

- How 页面主工具栏。
- 空白 How 阶段暖场 Slot 的 manual action。

表单字段：

- Flow 名称。
- Flow 描述。
- 关联 Feature，可多选。

验收：

- 新增后出现在 Flow 列表。
- 刷新页面后仍存在。
- How Gate 中“至少存在 Flow”通过。

### 3.2 Flow Step 编辑

Step 表单字段：

- Step 名称。
- Step 描述。
- 执行 Actor。
- 输入 Business Object。
- 输出 Business Object。
- 顺序位置或前后连接关系。

操作：

- 新增 Step。
- 编辑 Step。
- 删除 Step。
- 调整 Step 顺序。

第一版如果没有图形拓扑编辑器，可以先支持线性排序。

### 3.3 拓扑校验

第一版拓扑有效性按现有数据结构选择最低可行规则：

若使用 position：

- 每个 Flow 至少一个 Step。
- Step position 不重复。
- Step position 可排序。
- 删除 Step 后 position 可重新整理。

若已有 next/previous：

- 不存在引用已删除 Step。
- 不存在循环死结。
- 不存在孤立中间节点。

### 3.4 Business Object 编辑

Business Object 操作：

- 新增。
- 编辑名称和描述。
- 删除。

Business Object Attribute 操作：

- 新增字段。
- 编辑字段名称、描述、类型、示例。
- 删除字段。

### 3.5 Flow Step 与 Business Object 引用

要求：

- Step 引用输入/输出对象时，只能选择已存在 Business Object。
- 删除 Business Object 时，需要处理被 Step 引用的情况：
  - 阻止删除并提示。
  - 或允许删除并自动清理引用。

建议第一版采用阻止删除，风险更小。

## 4. 验收标准

1. 用户可以手动创建 Flow。
2. 用户可以为 Flow 添加 Step。
3. 用户可以编辑 Step 的 Actor 和输入/输出 Business Object。
4. 用户可以调整 Step 顺序。
5. 用户可以创建 Business Object 和 Attribute。
6. Step 引用不存在对象时，How Issue 能检测出来。
7. Business Object 全部无 Attribute 时，不报 Issue，但生成 blocking Slot。
8. Business Object 部分有 Attribute、部分无 Attribute 时，生成具体 Issue。
9. How Gate 通过后，`/scope` 可进入。

## 5. 对接下一阶段

P3 输出给 P4：

- 稳定的 Flow 数据。
- 稳定的 Business Object 数据。
- How Gate 通过状态。

P4 将基于已收敛的 What/How 数据进行 Scope 决策和 Kano 分析。

P5 Shadow Preview 也会复用 P3 的写入能力，在 commit 影子项目时创建 Flow、Step、Business Object 和 Attribute。

