# P5：Preview、Export、Impact、Proposal 决策与发布收尾

## 一、阶段目标

处理剩余产品体验与发布前问题，包括 Preview force generation、导出、影响分析、Proposal 概念取舍、审计日志展示和最终联调发布验收。

本阶段完成后，系统应从“可联调”进入“可演示/可试用”的稳定状态。

## 二、背景问题

差异报告指出：

- Preview 页面有本地 force generation，会临时补角色、流程、业务对象，并可通过 `workspaceApi.save(normalized)` 合并回项目。
- `workspaceApi.exportMarkdown/exportJson` 当前前端本地生成。
- `workspaceApi.impactPreview` 当前只返回本地数量统计。
- 前端有 Proposal UI 和 store action，但后端无 Proposal model/API。
- 后端已有 audit logs，但 Preview 里的 audit export 读取的是 `(draftIr as any).audit || []`，没有接后端。

## 三、范围

### 本阶段必须做

1. 明确 Preview force generation 的产品定位。
2. 实现或下线本地 force generation 合并入口。
3. 实现导出策略。
4. 实现 scope/patch impact preview 或明确降级。
5. 决策 Proposal：接入、隐藏或移除。
6. 接入 audit logs 展示/导出。
7. 完成全链路回归验收。

### 本阶段不做

- 不再新增大型需求建模概念。
- 不重写整体 UI。
- 不引入多用户权限体系。

## 四、产品决策项

### 决策 1：Preview force generation

当前 Preview 会在前端本地补齐缺失数据，属于演示辅助能力。

可选方案：

#### 方案 A：保留为“临时预览”，禁止合并

- 用户可看到临时预览。
- 不允许写回后端。
- UI 明确标识“仅用于预览，不会保存”。

优点：实现简单，风险低。

缺点：用户不能一键接受补齐结果。

#### 方案 B：改为后端正式生成草稿

- force generation 调用后端 flow/scenario/ac/scope generation。
- 生成结果以 draft preview 展示。
- 用户 confirm 后落库。

优点：数据链路一致。

缺点：实现量较大。

#### 方案 C：保留合并，但走后端 GraphPatch API

- 前端把临时补齐结果转换为 patch。
- 后端提供 `POST /api/projects/{id}/patches/apply`。
- 后端应用 patch、写审计日志、刷新 IR。

优点：可复用 PatchEngine。

缺点：需要补 route、校验和 patch 格式约束。

推荐：短期采用方案 A 或 B。若已有 PatchEngine 要产品化，则采用方案 C，但需要严格验收。

### 决策 2：Export

可选方案：

#### 方案 A：前端基于聚合 IR 导出

- 保持前端生成 Markdown/JSON。
- 数据来自后端 `GET /api/projects/{id}`。
- 不新增后端 export route。

优点：简单。

缺点：后端无法审计导出，格式难复用。

#### 方案 B：后端导出

新增：

- `GET /api/projects/{id}/export/json`
- `GET /api/projects/{id}/export/markdown`

优点：格式统一，可审计。

缺点：需要后端模板。

推荐：JSON 直接复用聚合详情；Markdown 可后端实现，以便后续分享、下载、审计一致。

### 决策 3：Impact Preview

当前 Scope 页面拖动前调用 `workspaceApi.impactPreview()`，但只返回数量统计。

推荐新增：

```http
POST /api/projects/{project_id}/impact-preview
```

body：

```json
{
  "change_type": "scope_update",
  "target": {
    "feature_id": 1,
    "next_status": "暂缓"
  }
}
```

响应：

```json
{
  "affected_scenarios": [],
  "affected_flows": [],
  "affected_business_objects": [],
  "warnings": [],
  "summary": "..."
}
```

如果 P5 不实现完整分析，至少应返回真实后端计算的关联对象，而不是前端本地假数据。

### 决策 4：Proposal

前端有：

- `ProposalPanel`
- `acceptProposal`
- `rejectProposal`
- `convertProposalToChoice`
- `proposals` record

后端无 Proposal。

必须三选一：

1. **隐藏 Proposal UI**：最快，避免无效入口。
2. **将 Proposal 合并进 Choice 概念**：Proposal 作为 Choice 的一种 status 或 source，不单独建模。
3. **新增 Proposal model/API**：完整支持候选提案生命周期。

推荐短期选择 1 或 2。除非产品明确需要 Proposal 与 Choice 并存，否则不要新增概念。

## 五、后端实现任务

### 任务 1：导出 API

可新增：

- `GET /api/projects/{project_id}/export/markdown`
- `GET /api/projects/{project_id}/export/json`

JSON 可直接返回聚合详情。

Markdown 至少包含：

- 项目名称
- 项目描述
- 原始用户需求
- 角色
- 功能树
- 场景与成功标准
- 业务对象
- 流程
- 范围决策

### 任务 2：Impact Preview API

先支持 scope update：

- 输入 feature_id 和目标 scope status。
- 输出受影响 scenarios、flows、business objects。

关联规则：

- feature 下直接 scenarios。
- 引用该 feature 的 flows。
- flows 中 steps 引用的 business objects。
- 如 feature 有 children，递归统计。

### 任务 3：Audit logs 聚合

已有：

- `GET /api/projects/{project_id}/audit-logs`

需要前端接入。后端确认每类关键 mutation 都写审计：

- create/update/delete nodes
- draft confirm
- choice accept/reject
- requirements refine
- export 可选审计

### 任务 4：Patch API 可选

如采用 Preview 方案 C 或 NodePanel 关系编辑统一 patch：

新增：

```http
POST /api/projects/{project_id}/patches/apply
```

body：

```json
{
  "patch": {},
  "source": "preview_force_generation"
}
```

必须校验：

- patch 引用对象属于同项目。
- 支持的 kind 白名单。
- 不允许跨项目 ID。
- 写 audit log。

## 六、前端实现任务

### 任务 1：Preview force generation 改造

根据产品决策实施：

- 方案 A：移除“合并到项目”按钮，只保留临时预览。
- 方案 B：按钮改为引导用户使用后端 generation draft。
- 方案 C：按钮调用 patch apply API。

无论选哪种，都不允许继续调用 `workspaceApi.save(normalized)`。

### 任务 2：Export 改造

- JSON：调用后端 export json 或 `getById`。
- Markdown：调用后端 export markdown 或基于真实聚合 IR 前端生成。
- 导出内容不得来自 Preview 临时 mock，除非 UI 明确选择“导出预览草稿”。

### 任务 3：Scope impact preview 改造

Scope 拖动前：

1. 调用后端 impact preview。
2. 展示真实 affected groups。
3. 用户确认后调用 `updateScope`。
4. refreshWorkspace。

### 任务 4：Proposal UI 处理

根据决策：

- 隐藏 Proposal：RightObjectPanel 不再路由到 ProposalPanel，Overview 不展示 pendingProposalCount。
- 合并 Choice：ProposalPanel 删除或改为 ChoicePanel 变体。
- 新增后端：接 API。

### 任务 5：Audit logs 展示/导出

Preview 或 Overview 中接入：

- `workspaceApi.listAuditLogs(projectId)`

导出 audit JSON 时使用后端返回内容，不再读取 `(draftIr as any).audit || []`。

## 七、发布级回归验收

### 主链路 1：空白项目建模

1. 创建空白项目。
2. 新增 actor。
3. 新增 feature。
4. 绑定 actor。
5. 新增 scenario。
6. 新增 AC。
7. 新增 business object。
8. 新增 flow 和 flow step。
9. 修改 scope。
10. 刷新页面，全部存在。

### 主链路 2：AI 项目推演

1. 输入需求。
2. 生成项目草稿。
3. 重生成。
4. 确认。
5. 生成场景。
6. 生成 AC。
7. 生成 scope。
8. 导出 Markdown。

### 主链路 3：Issue/Choice 闭环

1. 制造一个缺口。
2. 后端 Issue 出现。
3. 触发解决。
4. 生成 draft 或 choice。
5. confirm/accept。
6. 数据落库。
7. Issue 消失或减少。

### 主链路 4：Scope impact

1. 拖动范围卡片。
2. 后端返回影响分析。
3. 确认变更。
4. Scope 落库。
5. 刷新保持。

### 主链路 5：审计与导出

1. 完成若干增删改。
2. 查看 audit logs。
3. 导出 audit JSON。
4. 导出 requirement JSON/Markdown。

## 八、最终验收标准

P5 验收必须全部满足：

1. 前端默认不再使用 localStorage 作为项目或草稿事实源。
2. `workspaceApi.save(space)` 不再被主要业务路径调用。
3. Preview 不再把本地 mock 直接整项目覆盖保存。
4. Export 使用后端真实项目数据。
5. Scope impact preview 来自后端或被明确降级并在 UI 中标识。
6. Proposal 无效入口已隐藏、合并或接入后端。
7. Audit logs 使用后端数据。
8. `npm run lint` 通过。
9. 后端 `.venv` 启动成功。
10. 完成所有发布级回归验收。

## 九、上线/合并前检查

- `.env` 中敏感 key 不进入提交。
- `.gitignore` 已覆盖数据库、本地环境、前端 dist、缓存目录。
- 后端数据库 migration 策略明确。
- README 或运行文档包含前后端启动命令。
- 所有新增 API 在代码注释或文档中有路径、请求、响应说明。
- 手动验收记录写入 PR 或实施总结。

## 十、后续迭代建议

P5 后可以进入下一轮产品化：

1. 草稿持久化。
2. 多用户 workspace。
3. 权限与审计增强。
4. 更完整的 Impact graph。
5. Proposal/Choice 概念合并优化。
6. 后端 OpenAPI schema 生成前端类型。
7. Playwright 端到端测试。
