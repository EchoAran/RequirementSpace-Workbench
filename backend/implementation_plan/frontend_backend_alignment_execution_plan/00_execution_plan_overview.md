# 前后端联调执行计划总览

本文档集基于 `backend/implementation_plan/frontend_backend_alignment_gap_report.md` 编写，目标是把当前“前端 localStorage Mock + 后端细粒度 API”状态，逐步推进到“后端作为事实源、前端通过统一 API client 消费聚合 IR”的可联调、可验收架构。

## 一、计划原则

1. **先打通主链路，再完善高级闭环**
   - 先保证 Home -> Onboarding -> 打开项目 -> 查看/编辑核心需求空间能真实访问后端。
   - Issue、Perception、Choice、Preview、Export 等高级能力在基础链路稳定后再接入。

2. **后端作为事实源**
   - 前端 `localStorage` Mock 只能保留为 dev fixture 或删除。
   - 项目、节点、草稿、Issue、Choice、审计日志以数据库和后端服务为准。

3. **聚合读，细粒度写**
   - 读：后端提供 `GET /api/projects` 和 `GET /api/projects/{project_id}`，返回前端可消费的聚合 `RequirementSpace`。
   - 写：优先复用后端现有 actor/feature/scenario/business_object/flow/scope CRUD。
   - 写后统一刷新聚合详情，降低前端局部状态漂移风险。

4. **字段映射集中化**
   - 所有 snake_case <-> CamelCase、后端 DTO <-> 前端 IR 的转换集中在 `frontend/src/lib/api.ts` 或独立 mapper 文件。
   - 页面和组件不直接消费后端原始 DTO。

5. **每阶段必须可独立验收**
   - 每个阶段都有明确的交付物、验收标准和下一阶段进入条件。
   - 不以后续阶段补救当前阶段未完成项。

## 二、阶段拆分

| 阶段 | 文件 | 核心目标 |
| --- | --- | --- |
| P0 | `01_p0_preflight_and_dev_foundation.md` | 清除联调前置阻断，建立 HTTP、CORS/proxy、类型检查基础 |
| P1 | `02_p1_project_aggregation_api.md` | 补齐项目列表和项目详情聚合读取，让前端能打开真实后端项目 |
| P2 | `03_p2_manual_crud_migration.md` | 把手动编辑从整项目 localStorage save 迁移到后端细粒度 CRUD |
| P3 | `04_p3_ai_draft_generation_migration.md` | 把 AI 生成草稿生命周期迁移到后端 draft routes |
| P4 | `05_p4_issue_perception_choice_loop.md` | 接入后端 Issue、PerceptionJob、Slot Filling、Choice 闭环 |
| P5 | `06_p5_preview_export_impact_and_release.md` | 完成 Preview、Export、Impact、Proposal 取舍和最终联调发布 |

## 三、总体验收目标

完成全部阶段后，应满足：

- 前端不再依赖 `rs_workspace_spaces` 和 `rs_workspace_drafts` 作为事实源。
- 使用 `.venv` 启动 FastAPI 后端，使用 Vite 启动前端，可以完成真实数据库读写。
- Home 可以列出后端项目。
- Onboarding AI 推演可以生成、重生成、确认、丢弃后端草稿。
- 打开项目后，What / How / Scope / Preview / Overview 读取同一个后端聚合 IR。
- 手动增删改 actor、feature、scenario、acceptance criterion、business object、flow、scope 后，刷新页面仍保留。
- Issue/Slot/Choice 至少完成一条端到端闭环：检测问题 -> 生成解决草稿或 Choice -> 确认 -> 落库 -> 刷新聚合 IR。
- 前端 `npm run lint` 通过，后端 app 可在 `.venv` 中导入和启动。

## 四、全局风险

1. **范围膨胀风险**
   - 前端已有 UI 暗示了 Proposal、Screen、StateMachine 等能力，但后端未建模。
   - 应在 P5 明确“接入、降级、隐藏、删除”的产品决策。

2. **草稿内存态风险**
   - 后端 generation services 当前使用内存 `_drafts`。
   - P3 前可以接受单进程联调；若要支持刷新恢复、多 worker 或生产，需要草稿持久化。

3. **字段映射风险**
   - 如果每个页面自行适配后端字段，会迅速失控。
   - 必须在 P1 建立统一 mapper 并写样例测试。

4. **AI 调用不稳定风险**
   - 部分生成链路依赖 LLM 或 skill。
   - 验收时需要准备可复现 seed fixture 或 mock backend response，用于区分“联调失败”和“AI 生成质量波动”。

## 五、推荐执行节奏

- P0：0.5-1 天
- P1：1-2 天
- P2：2-4 天
- P3：2-3 天
- P4：3-5 天
- P5：2-4 天

实际排期取决于是否补后端测试、是否需要持久化 draft、是否保留 Proposal 与 Preview force generation。

## 六、阶段推进规则

每个阶段结束时必须产出：

- 完成项清单。
- 未完成项和降级说明。
- 可复现验收步骤。
- 当前阶段新增或变更的 API 合约。
- 下一阶段可直接使用的交接说明。

只有当前阶段验收通过，才进入下一阶段。
