# P0：Schema、Gate 与规则基础设施

## 1. 阶段目标

P0 的目标是先统一“语言”和“判断标准”：

1. 明确 Stage、Issue、Perception Slot、Gate Result、Shadow Draft 的数据结构。
2. 明确 What、How、Scope 三个 Gate 的判定规则。
3. 建立前后端可共享语义的规则基础，避免前端 selector 和后端 API 各算各的。

P0 不要求完成复杂 UI，但必须能让后续阶段基于稳定 schema 开发。

## 2. 主要改造范围

### 2.1 前端类型定义

建议位置：

```text
frontend/src/core/schema.ts
frontend/src/core/selectors.ts
```

新增或收敛以下类型：

```typescript
export type Stage = 'what' | 'how' | 'scope';

export interface StageGateResult {
  stage: Stage;
  passed: boolean;
  issues: Issue[];
  blockingSlot?: PerceptionSlot;
  missingKinds: string[];
}
```

`Issue` 需要包含：

```typescript
stage
domain
severity
blocking
relatedNodeIds
suggestedActionKind
```

`PerceptionSlot` 需要包含：

```typescript
stage
blocking
kind
description
targetKind
targetId
actions.manual
actions.ai
```

### 2.2 后端 schema

建议位置：

```text
backend/api/schemas/stage_gate_schema.py
backend/api/schemas/issue_schema.py
backend/api/schemas/perception_slot_schema.py
backend/api/schemas/preview_shadow_schema.py
```

后端 schema 应与前端语义一致，但字段命名可使用 Python/FastAPI 惯例，API 层负责序列化。

### 2.3 Gate evaluator

建议新增：

```text
backend/api/services/stage_gate_service.py
```

职责：

1. 获取项目当前聚合数据。
2. 计算 What Gate。
3. 计算 How Gate。
4. 计算 Scope Gate。
5. 输出 StageGateResult。

第一版可以先在前端 selector 实现完整算法，后端 Gate service 作为 P5 Shadow Preview 的基础再补齐。但产品规则必须从 P0 起固定。

## 3. Gate 规则清单

### 3.1 What Gate

通过条件：

1. 至少存在一个 Actor。
2. 至少存在一个叶子 Feature。
3. 每个叶子 Feature 至少绑定一个 Actor。
4. 每个叶子 Feature 至少有一个 Scenario。
5. 每个 Scenario 至少有一个 Acceptance Criterion。
6. 当前 What 阶段无 blocking Slot。

### 3.2 How Gate

通过条件：

1. 至少存在一个 Flow。
2. Flow 至少有有效 Step。
3. Step 拓扑或顺序链路有效。
4. Step 引用的 Actor 存在。
5. Step 引用的输入/输出 Business Object 存在。
6. Business Object Attribute 遵循增量非平衡算法。
7. 当前 How 阶段无 blocking Slot。

### 3.3 Scope Gate

通过条件：

1. 每个叶子 Feature 都有范围决策。
2. Kano 已生成，或用户明确跳过。
3. 当前 Scope 阶段无 blocking Slot。

### 3.4 Preview 访问规则

Preview 不被 Gate 硬锁。

如果 What/How/Scope 全部通过：

```text
Preview source = real_project
```

否则：

```text
Preview source = shadow_project
```

## 4. 增量非平衡算法

通用判断：

```text
total == 0
  -> 不报 Issue，生成 non-blocking onboarding Slot

completed == 0
  -> 不报 Issue，生成 blocking Slot

0 < completed < total
  -> 对未完成对象生成 Issue，并由最高优先级 Issue 驱动唯一 Slot

completed == total
  -> 通过
```

需要应用到：

1. 叶子 Feature 的 Scenario 缺失。
2. Scenario 的 AC 缺失。
3. Business Object 的 Attribute 缺失。
4. Scope 决策缺失。

## 5. 验收标准

P0 完成后应满足：

1. 文档中定义的 schema 已落到前端或后端类型文件。
2. Gate 规则在代码中有明确函数入口或接口定义。
3. Issue domain 覆盖 What、How、Scope 所有对象。
4. Slot schema 支持 manual 和 ai 双通道 actions。
5. Preview 访问规则被明确标记为“不硬锁”。

## 6. 对接下一阶段

P0 输出给 P1：

1. StageGateResult 类型。
2. Issue 类型。
3. PerceptionSlot 类型。
4. Gate 判定规则。
5. Issue -> Slot 优先级。

P1 将基于这些规则改造 selector、LeftNav 和 Router Guard。

