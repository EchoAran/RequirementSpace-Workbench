# 基于 Skill 的生成 API 平替实施计划

## 目标

构建一套基于 `backend/integration` 中各个 skill 的生成服务，用于平替当前的特征树生成、场景生成、成功标准生成和范围生成流程，同时保留旧服务实现，并按新的设计调整成功标准创建 API。

新的实现需要满足：

- 特征树、场景、范围生成保持现有 route URL、请求 schema、响应 schema、草稿生命周期、确认生命周期和持久化行为不变。
- 成功标准生成的创建入口直接改为 `full` / `single` / `batch`，不保留旧的根路径创建入口；其草稿响应、重新生成、确认和删除接口保持当前风格。
- 不删除、不破坏当前基于 `backend/core/generators` 的旧实现。
- 在 `backend/api/services/service_registry.py` 中增加切换逻辑，使应用可以选择旧服务或 skill-backed 新服务。
- skill 改造、adapter 和 skill-backed service 尽量集中放在 `backend/integration` 下，避免逻辑散落到太多目录。
- 只有在当前领域模型无法安全表达 skill 输出时，才修改核心后端逻辑或数据模型。

## 服务切换策略

增加一个生成后端开关，建议通过环境变量控制：

```text
REQUIREMENTSPACE_GENERATION_BACKEND=legacy | skill
```

默认值应为 `legacy`，避免在未显式配置时改变当前行为。

该变量必须支持配置在项目根目录 `.env` 中，例如：

```env
REQUIREMENTSPACE_GENERATION_BACKEND=skill
```

实现时不能只使用 `os.environ.get(...)`，因为 `service_registry.py` 可能在 `LLM_service.py` 加载 `.env` 之前被导入。`service_registry.py` 或统一配置模块需要主动加载项目根目录 `.env`，再读取 `REQUIREMENTSPACE_GENERATION_BACKEND`。

在 `backend/api/services/service_registry.py` 中根据开关实例化不同服务：

```python
if generation_backend == "skill":
    feature_generation_service = SkillBackedFeatureGenerationService()
    scenario_generation_service = SkillBackedScenarioGenerationService()
    acceptance_criteria_generation_service = SkillBackedAcceptanceCriteriaGenerationService()
    scope_generation_service = SkillBackedScopeGenerationService()
else:
    feature_generation_service = FeatureGenerationService()
    scenario_generation_service = ScenarioGenerationService()
    acceptance_criteria_generation_service = AcceptanceCriteriaGenerationService()
    scope_generation_service = ScopeGenerationService()
```

route 层原则上不修改。例外是成功标准生成创建入口需要直接改为 `full` / `single` / `batch`。除此之外，除非新增的 skill 错误需要暴露为明确的 HTTP 错误码，否则保持现有 route 文件稳定。

更高层 API 也必须遵守同一个切换逻辑。尤其是项目创建草稿 API：

```text
POST   /api/project_creation_drafts
POST   /api/project_creation_drafts/{draft_id}/regenerate
POST   /api/project_creation_drafts/{draft_id}/confirm
DELETE /api/project_creation_drafts/{draft_id}
```

当前项目创建服务内部会生成 actors 和 features，因此它不能直接绕过 `service_registry.py`。实施要求：

- `project_creation_service` 也要放入 `backend/api/services/service_registry.py` 统一管理。
- `project_creation_routes.py` 不应直接实例化 `ProjectCreationService()`。
- `legacy` 模式继续使用当前 `ProjectCreationService`。
- `skill` 模式使用 `SkillBackedProjectCreationService`。
- 第一版可以保留旧的 actor 生成和 blank project 生成逻辑，只把项目创建过程中的 feature 生成替换为 feature-tree-skill + adapter。
- 后续如果 actor 生成也有 skill，再单独纳入切换。

## 大模型调用方式要求

skill-backed API 必须使用系统原有的大模型调用入口：

```text
backend/services/LLM_service.py
```

也就是说，`feature-tree-skill`、`scenario-generation-skill`、`scenario-feedback-skill` 和 `kano-skill` 在被后端 API 调用时，不应再直接读取各自 config 中的模型配置或直接依赖 `OPENAI_API_KEY`。后端 API 路径下应统一使用 `.env` 中的：

```env
LLM_API_URL=...
LLM_API_KEY=...
LLM_MODEL_NAME=...
LLM_TEMPERATURE=...
```

实施方式：

- skill 原有 CLI 可以保留 OpenAI SDK 调用方式，避免破坏其独立运行能力。
- skill-backed service 应通过 adapter/wrapper 调用 skill prompt，但实际请求由 `LLMHandler` 发出。
- `LLMHandler` 需要轻度增强，支持 JSON object 输出，例如 `response_format={"type": "json_object"}`，因为这些 skill 都依赖模型返回可解析 JSON。
- skill-backed service 不应直接使用 `OPENAI_API_KEY`、skill 内部 `config.json` 的 model 字段，或 OpenAI SDK 客户端完成后端 API 请求。

## Kano 图片传输和入库要求

Kano 图表在业务层和 API 响应中使用 base64 字符串：

```text
positive_picture_base64
negative_picture_base64
```

入库时继续复用已有转换服务：

```text
backend/services/binary_conversion_service.py
```

也就是：

- API/draft/service 层传输：base64。
- `ScopeModel.positive_picture` / `ScopeModel.negative_picture` 入库：二进制 bytes。
- 从数据库读取后返回前端：二进制 bytes 再转 base64。

第一版不新增图片存储字段，继续使用现有 scope 表字段。

## 推荐目录结构

新增的 skill-backed 适配和服务逻辑集中放在 `backend/integration` 下：

```text
backend/integration/
  skill_backed_services/
    __init__.py
    feature_tree_adapter.py
    feature_generation_service.py
    gherkin_adapter.py
    scenario_generation_service.py
    acceptance_criteria_generation_service.py
    kano_scope_adapter.py
    scope_generation_service.py
    chart_renderer.py
    errors.py
```

这样做的原因：

- 现有 skill package 继续留在各自目录。
- 新服务一眼能看出是 skill-backed 实现。
- route 和 schema 层保持稳定。
- adapter 逻辑不会散落到 `backend/core/generators`。

## 阶段 1：Feature Tree Skill 平替特征树生成

### 需要保持的现有行为

现有 API：

```text
POST   /api/feature_generation_drafts
POST   /api/feature_generation_drafts/{draft_id}/regenerate
POST   /api/feature_generation_drafts/{draft_id}/confirm
DELETE /api/feature_generation_drafts/{draft_id}
```

现有响应结构：

```json
{
  "draft_id": "...",
  "project_id": 1,
  "features": [
    {
      "feature_name": "...",
      "feature_description": "...",
      "actor_names": ["..."]
    }
  ]
}
```

现有持久化逻辑需要的内部结构：

```json
{
  "feature_number": "F001-001-001",
  "feature_name": "...",
  "feature_description": "...",
  "actor_ids": [1]
}
```

### 对 Feature Tree Skill 的轻度改造

在 `backend/integration/feature-tree-skill` 中轻度改造输出格式，使其可以输出结构化值，同时继续兼容原有字符串格式。

推荐的新输出格式：

```json
{
  "L1": {
    "name": "Local Music Player",
    "description": "A lightweight local desktop music player."
  },
  "L2.1": {
    "name": "Local Music Library",
    "description": "Manage locally imported music files.",
    "role": "Common"
  },
  "L3.1.1": {
    "name": "Scan Local Audio Files",
    "description": "Scan folders and import supported audio files.",
    "role": "Local Music Listener"
  }
}
```

仍然要兼容旧格式：

```json
{
  "L3.1.1": "Scan Local Audio Files [Role: Local Music Listener]"
}
```

### Adapter 职责

新增 `feature_tree_adapter.py`。

职责：

- 解析字符串格式和结构化格式两种 skill 输出。
- 将 `L1` 转成 `F001`。
- 将 `L2.1` 转成 `F001-001`。
- 将 `L3.1.1` 转成 `F001-001-001`。
- 从 feature name 中移除 `[Role: ...]` 标签。
- 根据 role name 反查当前项目中的 actor id。
- 将 `Common` 映射为当前项目下的所有 actor id。原因是当前场景生成逻辑不允许叶子 feature 没有关联 actor。
- 当 skill 未提供 description 时，生成一个确定性的 fallback description。
- 校验根节点数量。
- 校验父节点是否存在。
- 输出当前特征树持久化逻辑可以直接消费的 `features` payload。

### Skill-backed Service 职责

新增 `SkillBackedFeatureGenerationService`。

需要镜像当前 `FeatureGenerationService` 的方法：

```python
create_draft(project_id, session)
regenerate_draft(draft_id, user_feedback, session)
confirm_draft(draft_id, session)
discard_draft(draft_id)
```

建议尽量复用当前持久化逻辑：

- 优先考虑继承 `FeatureGenerationService`，只覆写 `_generate_preview`。
- 如果继承导致耦合太重，再复制草稿和持久化相关逻辑。

推荐方案：继承并只替换生成部分，因为当前的校验和持久化逻辑已经比较完整。

### 当前逻辑需要调整的点

- 需要新增 actor name 到 actor id 的解析逻辑，因为 skill 输出的是 role name，不是 actor id。
- 必须明确 `Common` 的映射策略。第一版建议 `Common -> 所有 actor`。
- 需要确定 description 的来源：
  - 最好让 skill 直接生成 description；
  - adapter 仍需要 fallback，避免 skill 输出缺字段导致整体失败。
- 草稿内部建议保留原始 skill feature tree：

```json
{
  "raw_feature_tree": { "L1": "...", "L3.1.1": "..." }
}
```

这个原始结构后续对 Kano 分析很有用。

### 项目创建 API 中的 Feature Tree 平替

项目创建草稿是更高层 API，会在一次流程中同时生成项目预览、actors 和 features。该 API 也必须遵守 `REQUIREMENTSPACE_GENERATION_BACKEND`。

新增 `SkillBackedProjectCreationService`，建议继承当前 `ProjectCreationService`，只覆写 `_generate_actor_and_feature_previews` 中 feature 生成部分：

- actors 仍使用当前 `ActorsGenerator`。
- actor 生成完成后，用临时 `ActorNode(actorId=index, ...)` 传给 `feature-tree-skill`。
- feature-tree-skill 的输出交给 `FeatureTreeAdapter` 转为当前项目创建 draft 需要的结构。
- 当前项目创建 draft 内部 feature 使用的是 `actor_numbers`，因此 adapter 产出的 `actor_ids` 需要转换成 `A001/A002/...`。
- route 继续保持当前响应结构：

```json
{
  "actors": [
    {
      "actor_name": "...",
      "actor_description": "..."
    }
  ],
  "features": [
    {
      "feature_name": "...",
      "feature_description": "...",
      "actor_names": ["..."]
    }
  ]
}
```

项目创建 route 的错误白名单需要补充：

```text
invalid_actor_reference
invalid_feature_payload
invalid_skill_payload
```

## 阶段 2：Scenario Generation Skill + Scenario Feedback Skill 平替场景和成功标准

### 需要保持的现有行为

现有场景 API：

```text
POST   /api/scenario_generation_drafts/full
POST   /api/scenario_generation_drafts/single
POST   /api/scenario_generation_drafts/{draft_id}/regenerate
POST   /api/scenario_generation_drafts/{draft_id}/confirm
DELETE /api/scenario_generation_drafts/{draft_id}
```

成功标准 API 需要直接改成与场景生成一致的分层创建风格，不保留旧的根路径创建入口：

```text
POST   /api/acceptance_criteria_generation_drafts/full
POST   /api/acceptance_criteria_generation_drafts/single
POST   /api/acceptance_criteria_generation_drafts/batch
POST   /api/acceptance_criteria_generation_drafts/{draft_id}/regenerate
POST   /api/acceptance_criteria_generation_drafts/{draft_id}/confirm
DELETE /api/acceptance_criteria_generation_drafts/{draft_id}
```

也就是说，原来的：

```text
POST /api/acceptance_criteria_generation_drafts
```

应直接移除或停止注册，不做兼容保留。调用方必须明确表达是全量、单个场景，还是一组场景生成成功标准。

现有场景草稿响应必须保持：

```json
{
  "draft_id": "...",
  "project_id": 1,
  "generation_mode": "single",
  "feature_id": 10,
  "actor_id": null,
  "scenarios": [
    {
      "feature_id": 10,
      "feature_name": "...",
      "actor_id": 2,
      "actor_name": "...",
      "scenario_name": "...",
      "scenario_content": "As a ..., I want ..., So that ..."
    }
  ]
}
```

现有成功标准草稿响应必须保持：

```json
{
  "draft_id": "...",
  "project_id": 1,
  "scenario_acceptance_criteria": [
    {
      "scenario_id": 123,
      "scenario_name": "...",
      "acceptance_criteria": ["Given ... When ... Then ..."]
    }
  ]
}
```

### 对 Scenario Generation Skill 的轻度改造

在 `backend/integration/scenario-generation-skill` 中轻度改造，使其在保留原始 Gherkin 输出的同时，额外返回 adapter 友好的结构。

推荐新增结构：

```json
{
  "story": {},
  "system": {},
  "gherkin": {},
  "scenario_items": [
    {
      "scenario_name": "Valid local folder scan",
      "scenario_content": "As a Local Music Listener, I want to scan a local music folder, So that imported files appear in my library.",
      "acceptance_criteria": [
        "Given the user selects a local folder, When the scan starts, Then supported audio files are added to the library."
      ]
    }
  ]
}
```

如果 skill 只返回 `gherkin`，adapter 必须能从 Gherkin 中反推出 `scenario_items`。

### 对 Scenario Feedback Skill 的轻度改造

在 `backend/integration/scenario-feedback-skill` 中保持其核心职责：输入用户反馈和已有 Gherkin，输出修订后的 Gherkin。

需要加强的点：

- 保持 feature 名称和角色信息。
- 尽量保持原有 scenario 覆盖范围。
- 输出稳定 JSON，方便 adapter 重新拆分。
- 可以继续接受 raw Gherkin JSON，不强制引入当前后端的 scenario/criteria 结构。

### Gherkin Adapter 职责

新增 `gherkin_adapter.py`。

职责：

- 为 skill 构造 feature 输入字符串：

```text
Feature Name [Role: ActorName]
```

- 将 skill 的 Gherkin 输出转换为当前场景预览结构：
  - `Scenario` 或 `Scenario Outline` 标题转成 `scenario_name`。
  - `Narrative` 或生成出的 `story` 转成 `scenario_content`。
  - Gherkin step 转成成功标准字符串。
- 从 service 上下文补回 `feature_id` 和 `actor_id`。
- 在用户反馈重新生成时，优先使用当前 draft 或已落库 `GherkinSpecModel` 中的 raw Gherkin；只有 legacy 数据没有 spec 时，才根据已落库的 scenario/criteria 重新组装 raw Gherkin。
- 支持普通 scenario 和带 `Examples` 的 scenario outline。
- 在草稿内部保留 `raw_gherkin`，用于反馈修订和未来可能的前端展示。

### Skill-backed Scenario Service 职责

新增 `SkillBackedScenarioGenerationService`。

需要镜像当前 `ScenarioGenerationService`：

```python
create_full_draft(project_id, session)
create_single_draft(project_id, feature_id, session)
create_pair_draft(project_id, feature_id, actor_id, session)
regenerate_draft(draft_id, user_feedback, session)
confirm_draft(draft_id, session, generate_acceptance_criteria=False)
discard_draft(draft_id)
```

注意：当前 route 文件没有暴露 `create_pair_draft`，但 service 中存在该方法。为了平替完整性，新服务也应保留。

生成行为：

- 使用与当前服务相同的方式加载 project、leaf features、actors、feature-actor target pairs。
- 对每个 `(feature_id, actor_id)` 调用一次 `scenario-generation-skill`。
- 将 Gherkin 转换为：
  - scenario draft items；
  - 草稿内部的 acceptance criteria，并用临时 scenario key 关联。
- API 响应只返回现有 schema 要求的场景字段。
- draft payload 内部保存 raw Gherkin 和已经生成好的 criteria。

确认行为：

- 按当前逻辑持久化 scenarios，并额外持久化对应的 `GherkinSpecModel`。
- 如果 `generate_acceptance_criteria=True`，直接持久化同一次 Gherkin 生成得到的 criteria，不再调用第二个不相关的 LLM 生成器。
- 如果 `generate_acceptance_criteria=False`，不写入 criteria，但仍必须持久化 Gherkin spec，并让每个 scenario 指向对应 spec。

重新生成行为：

- 如果存在 user feedback 且 draft 中有 raw Gherkin，优先使用 `scenario-feedback-skill` 修订 Gherkin。
- 如果没有 raw Gherkin，则重新调用 `scenario-generation-skill`。
- 将修订后的 Gherkin 再拆回当前 draft response 结构。

### Skill-backed Acceptance Criteria Service 职责

新增 `SkillBackedAcceptanceCriteriaGenerationService`。

它的存在是为了保留当前独立的成功标准 API。

行为：

- 和当前服务一样加载已有 scenarios，但创建入口改为 `full` / `single` / `batch` 三种明确模式。
- 优先从已落库的 Gherkin 源记录恢复上下文，再生成或修订成功标准。
- 如果有 user feedback，优先使用 `scenario-feedback-skill` 基于原始 Gherkin 修订。
- 如果没有 user feedback，优先直接从原始 Gherkin steps 转换成功标准，避免对同一场景再次做语义生成。
- 如果旧数据没有 Gherkin 源记录，再 fallback 到根据 `ScenarioModel` 重新组装 Gherkin 的旧式路径。

成功标准创建 API 详细设计：

```python
create_full_draft(project_id, session)
create_single_draft(project_id, scenario_id, session)
create_batch_draft(project_id, scenario_ids, session)
regenerate_draft(draft_id, user_feedback, session)
confirm_draft(draft_id, session)
discard_draft(draft_id)
```

route 层设计：

```text
POST /api/acceptance_criteria_generation_drafts/full
request: { "project_id": 1 }

POST /api/acceptance_criteria_generation_drafts/single
request: { "project_id": 1, "scenario_id": 123 }

POST /api/acceptance_criteria_generation_drafts/batch
request: { "project_id": 1, "scenario_ids": [123, 124, 125] }
```

schema 层设计：

```python
AcceptanceCriteriaGenerationFullDraftCreateRequest:
    project_id: int

AcceptanceCriteriaGenerationSingleDraftCreateRequest:
    project_id: int
    scenario_id: int

AcceptanceCriteriaGenerationBatchDraftCreateRequest:
    project_id: int
    scenario_ids: list[int]
```

原 `AcceptanceCriteriaGenerationDraftCreateRequest(project_id, scenario_ids=None)` 不再作为 route 入参使用。service 内部如果想复用，可以保留一个私有 helper：

```python
_create_draft_for_scenarios(project_id, scenario_ids, generation_mode, session)
```

但 public API 和 route 层不再暴露“`scenario_ids` 可空代表 full”的隐式语义。

校验规则：

- `full`：加载项目下全部场景。若没有场景，返回 `no_scenarios_found`。
- `single`：校验 `scenario_id` 属于当前 `project_id`。若不存在，返回 `scenario_not_found`。
- `batch`：`scenario_ids` 不能为空，空数组返回 `empty_scenarios`。
- `batch`：`scenario_ids` 不允许重复，重复返回 `duplicate_scenario_id`。
- `batch`：每个 scenario 都必须属于当前项目，否则返回 `scenario_not_found`。
- 三种模式生成出的 draft response 继续使用当前 `AcceptanceCriteriaGenerationDraftResponse`，不改变前端展示结构。

这样可以避免旧接口“传不传 scenario_ids 含义不同”的隐式行为，也和场景生成的 `full` / `single` 风格保持一致。

### 方案 B：持久化 Gherkin 源上下文

为了解决“分阶段生成场景和成功标准时，上下文可能不一致”的问题，采用方案 B：场景确认入库时，额外持久化同一轮 skill 生成得到的原始 Gherkin 源记录。成功标准后续单独生成时，不再凭已落库的场景标题和内容重新猜测上下文，而是优先回到这份原始 Gherkin。

新增数据库模型：

```python
class GherkinSpecModel(Base):
    __tablename__ = "gherkin_specs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gherkin_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scenario_generation_skill",
    )
```

`gherkin_specs` 表不建议对 `(project_id, feature_id, actor_id)` 加唯一约束。原因是同一 feature/actor 后续可能重新生成多轮场景，历史场景仍应能指回它们各自确认时使用的 Gherkin 源。

修改 `ScenarioModel`：

```python
gherkin_spec_id: Mapped[int | None] = mapped_column(
    ForeignKey("gherkin_specs.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
gherkin_scenario_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

含义：

- `gherkin_spec_id` 指向该 scenario 来源的原始 Gherkin spec。
- `gherkin_scenario_index` 表示该 scenario 对应 spec 内第几个 `Scenario` / `Scenario Outline`。
- legacy 生成的旧数据这两个字段为 `NULL`。

关系补充：

- `ProjectModel` 增加 `gherkin_specs` relationship。
- `ScenarioModel` 增加 `gherkin_spec` relationship。
- `GherkinSpecModel` 可增加 `project`、`feature`、`actor`、`scenarios` relationships，方便 service 查询。

场景确认流程调整：

1. `SkillBackedScenarioGenerationService` 的 draft 内部继续保存每个 feature/actor target 的 raw Gherkin。
2. `GherkinAdapter` 拆分 scenario item 时，除当前字段外，还必须补充内部字段：

```json
{
  "gherkin_target_key": "feature_id:actor_id",
  "gherkin_scenario_index": 0
}
```

3. `confirm_draft` 持久化时，先按 target 写入 `GherkinSpecModel`，得到 `gherkin_spec_id`。
4. 写入每个 `ScenarioModel` 时，同时写入对应的 `gherkin_spec_id` 和 `gherkin_scenario_index`。
5. 如果 `generate_acceptance_criteria=True`，继续使用同一份 Gherkin 直接写入 criteria。
6. 如果 `generate_acceptance_criteria=False`，只写入 scenarios，但 Gherkin spec 必须仍然入库。这样后续单独生成成功标准时仍有一致上下文。

成功标准生成流程调整：

1. `full` / `single` / `batch` 先加载目标 scenarios。
2. 对每个 scenario，优先读取 `scenario.gherkin_spec_id` 和 `scenario.gherkin_scenario_index`。
3. 如果存在有效 spec：
   - 从 `GherkinSpecModel.gherkin_json` 中取出对应 scenario。
   - 无 user feedback 时，直接用 `GherkinAdapter.acceptance_criteria_from_gherkin_scenario(...)` 转换为当前成功标准字符串数组。
   - 有 user feedback 时，把原始 Gherkin 和反馈交给 `scenario-feedback-skill` 修订，再按 `gherkin_scenario_index` 映射回当前 `scenario_id`。
4. 如果不存在有效 spec：
   - fallback 到根据 `ScenarioModel.name`、`ScenarioModel.content`、feature、actor 和已有 criteria 重新组装 Gherkin。
   - 该 fallback 主要用于 legacy 数据和迁移前生成的数据。
5. draft 内部保存：

```json
{
  "generation_mode": "full | single | batch",
  "scenario_ids": [123],
  "raw_gherkin_by_spec": {
    "gherkin_spec_id": { "...": "..." }
  },
  "scenario_acceptance_criteria": [
    {
      "scenario_id": 123,
      "acceptance_criteria": ["Given ... When ... Then ..."]
    }
  ]
}
```

6. `confirm_draft` 仍按当前成功标准确认逻辑写入 `ScenarioAcceptanceCriterionModel`，不改变成功标准表结构。

迁移和兼容数据处理：

- 新表和新列对 legacy 服务透明，legacy 写入 scenario 时保持 `gherkin_spec_id=NULL`。
- 如果当前开发环境使用 `Base.metadata.create_all`，它只会创建新表，不会自动给已有表加列。已有 SQLite 数据库需要手动迁移或重建开发库。
- 生产环境如果已有真实数据，应增加显式 migration，而不是依赖 `create_all`。
- route response 不暴露 `gherkin_spec_id` 和 `gherkin_scenario_index`，它们只作为后端一致性上下文。

这个方案的关键收益是：场景先落库、成功标准后生成时，仍然使用同一轮 skill 输出的 Gherkin 作为事实来源，不会因为草稿被删除而丢失上下文。

### 当前逻辑需要调整的点

- 当前场景和成功标准是两个相对独立的 LLM 流程。skill-backed 版本应以 Gherkin 作为核心中间结构。
- draft payload 需要新增内部字段 `raw_gherkin`、`gherkin_target_key`、`gherkin_scenario_index` 和草稿级 criteria，即使 response schema 不暴露它们。
- 场景确认后，raw Gherkin 不能只保存在内存 draft 中，必须写入 `GherkinSpecModel`。
- 场景确认时，如果 `generate_acceptance_criteria=True`，应持久化同一份 Gherkin 中的 criteria，而不是再次调用旧的成功标准生成器。
- 场景确认时，如果 `generate_acceptance_criteria=False`，也必须持久化 Gherkin spec，避免后续独立生成成功标准时上下文丢失。
- 有用户反馈的重新生成，应优先使用 `scenario-feedback-skill`。
- 独立成功标准 API 需要改成 `full` / `single` / `batch` 三个创建入口，并移除旧根路径创建入口。

## 阶段 3：Kano Skill 平替 Scope 生成

### 需要保持的现有行为

现有范围生成 API：

```text
POST   /api/scope_generation_drafts
POST   /api/scope_generation_drafts/{draft_id}/regenerate
POST   /api/scope_generation_drafts/{draft_id}/confirm
DELETE /api/scope_generation_drafts/{draft_id}
```

现有响应结构：

```json
{
  "draft_id": "...",
  "project_id": 1,
  "scopes": [
    {
      "feature_id": 10,
      "feature_name": "...",
      "scope_status": "CURRENT",
      "reason": "...",
      "positive_summary": "...",
      "negative_summary": "...",
      "positive_picture_base64": "...",
      "negative_picture_base64": "..."
    }
  ]
}
```

### 对 Kano Skill 的轻度改造

修改 `backend/integration/kano-skill` 的 feature 抽取逻辑，使其支持真正的叶子节点抽取，而不是只硬编码读取 `L3`。

原因：

- 当前系统对所有叶子 feature 生成 scope。
- 大多数 skill feature tree 中 `L3` 是叶子，但也可能存在没有子节点的 `L2`。
- skill 应支持：
  - 扁平 `L1/L2/L3` 字典；
  - 结构化字典值；
  - 可选的预处理 feature list。

推荐支持：

```python
analyze_kano(
    requirement_text=...,
    feature_tree=...,
    features=[
        {"feature_id": 10, "name": "...", "role": "..."}
    ]
)
```

这样可以消除后续按名称匹配 feature id 的风险。如果这个改造太大，第一版可以继续输入 feature tree，由 adapter 做名称映射。

### Kano Scope Adapter 职责

新增 `kano_scope_adapter.py`。

职责：

- 根据当前已持久化的叶子 `FeatureNode` 构造 Kano 输入。
- 保留稳定映射：

```text
skill feature string -> feature_id
```

- 将 Kano category 映射为当前 scope status。
- 映射分析文本字段：

```text
reason_summary.functional_viewpoint    -> positive_summary
reason_summary.dysfunctional_viewpoint -> negative_summary
explanation                            -> reason
```

- 在 `reason` 中补充映射说明：

```text
Kano 分类为 Performance(O)，映射为 CURRENT。Better=0.8，Worse=-0.6。...
```

- 根据 Kano 结构化数据生成 base64 图片。

### Kano 到 Scope 的分类映射

第一版推荐映射：

```text
M Must-be      -> CURRENT
O Performance  -> CURRENT
A Attractive   -> 默认 POSTPONED；当 Better >= 0.6 时 CURRENT
I Indifference -> POSTPONED
R Reverse      -> EXCLUDE
Q Questionable -> POSTPONED
```

该映射应明确写在 `kano_scope_adapter.py` 中，并尽量保持可配置。

### 图表渲染职责

新增 `chart_renderer.py`。

第一版推荐：

- 如果环境中有 `matplotlib`，使用它渲染图表。
- 每个 feature 生成两张简单柱状图：
  - `positive_picture_base64`：functional A/B/C/D/E 分布。
  - `negative_picture_base64`：dysfunctional A/B/C/D/E 分布。
- 输出 PNG base64 字符串。

如果 `matplotlib` 不可用：

- 两个图片字段返回 `None`。
- 不让范围生成失败。
- 如果项目已有日志能力，可以记录内部 warning。

图表数据来源：

```json
"satisfaction_distribution": {
  "functional": {
    "A": {"count": 4, "ratio": 0.8}
  },
  "dysfunctional": {
    "E": {"count": 4, "ratio": 0.8}
  }
}
```

### Skill-backed Scope Service 职责

新增 `SkillBackedScopeGenerationService`。

需要镜像当前 `ScopeGenerationService`：

```python
create_draft(project_id, session)
regenerate_draft(draft_id, user_feedback, session)
confirm_draft(draft_id, session)
discard_draft(draft_id)
```

生成行为：

- 使用与当前服务相同的方式加载 project 和 leaf features。
- 根据 leaf features 构造 Kano 输入。
- 调用 `kano-skill`。
- 将 Kano results 转换为当前 scope payload。
- 校验每个叶子 feature 都有且只有一个 scope 结果。

重新生成行为：

- 当前 `kano-skill` 没有反馈修订专用流程。
- 第一版可以重新运行 Kano，并把 user feedback 追加到 requirement context。
- 后续更好的方案是新增一个 Kano reconsideration prompt。

### 当前逻辑需要调整的点

- 当前 scope generator 直接判断 `CURRENT/POSTPONED/EXCLUDE`。
- skill-backed scope 需要先得到 Kano category，再映射到 scope status。
- 需要开始填充当前已有但旧逻辑未充分利用的字段：
  - `positive_summary` 来自 functional viewpoint。
  - `negative_summary` 来自 dysfunctional viewpoint。
  - 图片字段来自后端图表渲染。
- 当前 service 要求所有叶子 feature 都有 scope，skill-backed 版本必须保留该完整覆盖校验。

## 阶段 4：错误处理和兼容性

尽量保留现有错误码。

新增 skill 内部错误时，映射到已有 route 能理解的错误：

```text
invalid_skill_payload       -> invalid_*_payload
skill_empty_result          -> empty_*
skill_feature_mismatch      -> *_feature_mismatch
skill_actor_mismatch        -> invalid_actor_reference
skill_missing_dependency    -> invalid_*_payload 或 500，视具体原因而定
```

除非后续单独做 v2 API，否则不要改现有 response schema。

## 阶段 5：测试计划

优先写 adapter 测试，再写 service 测试。

Feature tree adapter 测试：

- 能解析字符串 role tag。
- 能解析结构化 skill 输出。
- 能把 `L*` key 转成 `F*` 编号。
- 能把 actor name 映射到 actor id。
- 能把 `Common` 映射到所有 actor。
- 能检测缺失父节点和重复编号。

Gherkin adapter 测试：

- 能把 `Narrative` 和 `Scenarios` 转成当前 scenario preview 结构。
- 能把 Gherkin steps 转成成功标准字符串。
- 能保留 feature id 和 actor id。
- 能处理 scenario outline。
- 能给每个 scenario item 补充 `gherkin_target_key` 和 `gherkin_scenario_index`。
- 能从 `GherkinSpecModel.gherkin_json` 和 `gherkin_scenario_index` 精确恢复单个 scenario 的成功标准。
- 能从已有 scenario 和 criteria 重新组装 raw Gherkin，作为 legacy 数据 fallback。

Kano scope adapter 测试：

- 能把 `M/O/A/I/R/Q` 映射为 scope status。
- 能把 summary 和 explanation 映射到 `ScopeNode` 相关字段。
- 能保证所有叶子 feature 都有 scope。
- 缺少图表依赖时能优雅降级。

Service 测试：

- `create_draft` 返回与旧服务相同的 response schema。
- `confirm_draft` 持久化与旧服务兼容的数据库记录。
- 场景确认且 `generate_acceptance_criteria=True` 时，同时持久化 scenarios 和 criteria。
- 场景确认且 `generate_acceptance_criteria=False` 时，也会持久化 `GherkinSpecModel`，并让 scenarios 指向对应 spec。
- 成功标准 `full` / `single` / `batch` 三个创建入口都能生成相同 response schema 的 draft。
- 成功标准 `batch` 对空数组、重复 id、跨项目 scenario id 有明确错误。
- 成功标准生成在存在 Gherkin spec 时优先使用 spec；没有 spec 时 fallback 到 legacy 重组路径。
- `service_registry` 默认使用 legacy，并能通过环境变量切换到 skill。

## 阶段 6：上线顺序

1. 新增 adapters 和 skill-backed services，但暂时不接入 registry。
2. 添加 adapter 测试。
3. 添加使用 mock skill 输出的 service 测试。
4. 在 `service_registry` 中增加开关，默认 `legacy`。
5. 手动验证 `legacy` 模式下除成功标准创建入口外的草稿 API 行为不变。
6. 手动验证 `legacy` 和 `skill` 模式下成功标准 `full` / `single` / `batch` 都可创建草稿。
7. 手动验证 `skill` 模式下所有草稿 API 可正常创建、重新生成、确认、丢弃。
8. 等 skill 模式稳定后，再考虑是否把默认值切到 `skill`。

## 已确认决策与剩余待确认

- 已确认：成功标准创建入口直接改为 `full` / `single` / `batch`，不保留旧根路径创建入口。
- 已确认：采用方案 B，新增 `GherkinSpecModel` 持久化 raw Gherkin，上下文不只保存在内存 draft。
- `Common` 是否映射到所有 actor 或默认 actor。推荐：所有 actor。
- `Attractive(A)` 且 Better 较高时是否进入 `CURRENT`。推荐：`Better >= 0.6` 时进入 `CURRENT`。
- 图表渲染依赖是否强制安装。推荐：第一版可选，缺少依赖时图片字段为空。
- feature-tree skill 是否强制生成 description。推荐：要求生成，但 adapter 仍提供 fallback。
