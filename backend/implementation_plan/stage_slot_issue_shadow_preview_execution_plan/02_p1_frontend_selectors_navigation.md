# P1：前端 Selector、页面健康度与导航守卫

## 1. 阶段目标

P1 的目标是让前端页面流转遵守新的阶段规则：

1. 使用统一 Gate 计算页面是否可进入。
2. 使用阶段隔离后的 Issue 和 Slot 构建页面健康度。
3. LeftNav 能展示真实状态、禁用原因和下一步入口。
4. Router Guard 能阻止直接 URL 访问受限页面。
5. Preview 始终可访问。

## 2. 改造范围

主要文件：

```text
frontend/src/core/selectors.ts
frontend/src/core/schema.ts
frontend/src/App.tsx
frontend/src/components/layout/LeftNav.tsx
frontend/src/store/useWorkspaceStore.ts
```

具体文件名可按现有结构调整。

## 3. 核心任务

### 3.1 重构 selectors

新增或重写：

```typescript
buildWhatGate(space)
buildHowGate(space)
buildScopeGate(space)
buildStageGate(space, stage)
detectStageIssues(space, stage)
buildSinglePerceptionSlot(space, stage, issues)
buildPageHealth(space, path)
buildOverviewModel(space)
```

要求：

- Issue 必须按 stage 过滤。
- Slot 必须唯一。
- Page Health 不再只按 issueCount 判断，而应综合 Gate、Slot、Issue。

### 3.2 Page Health 返回结构

建议包含：

```typescript
{
  status: '未开始' | '进行中' | '待补齐' | '已就绪' | '已锁定';
  disabled: boolean;
  disabledReason?: string;
  issueCount: number;
  hasBlockingSlot: boolean;
  nextSlot?: PerceptionSlot;
}
```

### 3.3 LeftNav 改造

规则：

- `/what` 默认可进入。
- `/flow` 依赖 What Gate。
- `/scope` 依赖 What Gate + How Gate。
- `/preview` 始终可进入。

交互要求：

- 禁用项显示原因，例如“请先补齐 What 阶段”。
- 可以提供“去处理”入口，跳转到阻碍 Slot 所在页面。
- Preview 若前序未收敛，显示“将进入临时预览模式”之类提示。

### 3.4 Router Guard

直接访问 URL 时也必须守卫：

```text
What Gate 未通过 -> 禁止 /flow 和 /scope
How Gate 未通过 -> 禁止 /scope
Preview -> 始终允许
```

被拦截时：

- 跳转到对应阶段页面。
- 展示 toast 或 banner 告诉用户原因。
- 如果存在 blocking Slot，则定位到该 Slot。

### 3.5 Overview 模型改造

Overview 可以展示全局信息，但必须按 stage 分组：

- What 待处理
- How 待处理
- Scope 待处理
- Preview 状态

不能把所有 Issue 混成一个无阶段列表。

## 4. 验收标准

1. What 空白时不显示大量 Issue，只显示暖场 Slot。
2. What 未通过时，LeftNav 中 How/Scope 禁用。
3. 用户直接访问 `/flow` 会被拦截并回到 `/what`。
4. 用户直接访问 `/preview` 不会被拦截。
5. How 页不展示 What 阶段 Issue。
6. Scope 页不展示 What/How 阶段 Issue。
7. 每个页面主区域最多展示一个 Slot。
8. 非平衡状态下，Issue 列表展示具体缺失对象。

## 5. 对接下一阶段

P1 输出给 P2/P3/P4：

1. 可复用的 Gate 计算函数。
2. 页面可读取的 `nextSlot`。
3. 阶段隔离后的 Issue 列表。
4. 可定位对象的 manual action 数据。

P2 将接入 What 页 Feature-Actor 绑定和 Slot 定位。

