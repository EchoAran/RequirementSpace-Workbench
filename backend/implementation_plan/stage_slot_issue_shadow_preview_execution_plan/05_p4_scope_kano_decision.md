# P4：Scope 决策闭环与 Kano 展示

## 1. 阶段目标

P4 的目标是让 Scope 阶段成为进入正式预览前的交付决策闭环。

完成后，用户应能够：

1. 对每个叶子 Feature 设置范围决策。
2. 查看 Kano 分析结果和决策依据。
3. 明确跳过 Kano 分析。
4. 让 Scope Gate 进入通过状态。

## 2. 改造范围

主要文件：

```text
frontend/src/pages/ScopeAndDelivery.tsx
frontend/src/store/useWorkspaceStore.ts
frontend/src/lib/api.ts
backend/api/routes/scope_generation_routes.py
backend/api/services/scope_generation_service.py
backend/integration/skill_backed_services/kano_scope_adapter.py
backend/integration/skill_backed_services/chart_renderer.py
```

## 3. 核心任务

### 3.1 全叶子 Feature 决策覆盖

Scope 页面必须以所有叶子 Feature 为基准展示决策项，而不是只展示已有 scope 记录。

每个叶子 Feature 的状态必须是三者之一：

- 本期包含。
- 暂缓处理。
- 排除。

缺失状态：

- 如果全部未决策：不报 Issue，生成 blocking Slot。
- 如果部分已决策、部分未决策：生成具体 Issue。

### 3.2 Kano 分析状态

Kano 状态建议分为：

```typescript
type KanoStatus = 'missing' | 'generating' | 'generated' | 'skipped' | 'failed';
```

Scope Gate 通过要求：

- `generated` 或 `skipped`。

用户选择跳过时，应记录明确状态，而不是仅在前端本地忽略。

### 3.3 Kano 展示内容

前端展示应与当前后端能力一致：

- Kano 分类。
- Kano 分类名称。
- Better / Worse。
- 正向满意度分布柱状图。
- 反向满意度分布柱状图。
- 正向依据摘要。
- 反向依据摘要。

不要求雷达图。

### 3.4 Scope 决策辅助

系统可以根据 Kano 分类给出默认建议：

- M/O：倾向本期包含。
- A：根据 Better 值判断是否本期。
- I：倾向暂缓。
- R：倾向排除。

但用户必须可以手动覆盖。

### 3.5 Scope Slot

Scope 阶段 Slot 类型：

- `missing_scope_decision`
- `missing_kano_analysis`
- `kano_failed_retry`

优先级建议：

1. `missing_scope_decision`
2. `missing_kano_analysis`
3. `kano_failed_retry`

## 4. 验收标准

1. Scope 页面展示所有叶子 Feature。
2. 每个叶子 Feature 都可以设置范围决策。
3. 部分 Feature 未决策时，生成具体 Scope Issue。
4. 全部 Feature 未决策时，不报 Issue，但生成 blocking Slot。
5. Kano 生成后，图表和依据可查看。
6. 用户可以明确跳过 Kano。
7. Kano 未生成且未跳过时，Scope Gate 不通过。
8. Scope Gate 通过后，Preview 可直接使用真实项目来源。

## 5. 对接下一阶段

P4 输出给 P5：

- Scope Gate 通过/未通过状态。
- 每个叶子 Feature 的范围决策。
- Kano generated/skipped 状态。
- 可用于 prototype generation 的 Feature 范围过滤依据。

P5 将根据 Scope Gate 判断 Preview 使用真实项目还是 Shadow Preview。

