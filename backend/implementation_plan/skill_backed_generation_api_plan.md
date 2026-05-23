# 基于 Skill 的生成 API 平替实施计划

## 目标

构建一套基于 `backend/integration` 中各个 skill 的生成服务，用于平替当前的特征树生成、场景生成、成功标准生成和范围生成流程，同时保留现有 API 和现有服务实现。

新的实现需要满足：

- 保持现有 route URL、请求 schema、响应 schema、草稿生命周期、确认生命周期和持久化行为不变。
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

route 层原则上不修改。除非新增的 skill 错误需要暴露为明确的 HTTP 错误码，否则保持现有 route 文件稳定。

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

现有成功标准 API：

```text
POST   /api/acceptance_criteria_generation_drafts
POST   /api/acceptance_criteria_generation_drafts/{draft_id}/regenerate
POST   /api/acceptance_criteria_generation_drafts/{draft_id}/confirm
DELETE /api/acceptance_criteria_generation_drafts/{draft_id}
```

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
- 在用户反馈重新生成时，根据当前 draft 或已落库的 scenario/criteria 重新组装 raw Gherkin。
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

- 按当前逻辑持久化 scenarios。
- 如果 `generate_acceptance_criteria=True`，直接持久化同一次 Gherkin 生成得到的 criteria，不再调用第二个不相关的 LLM 生成器。
- 如果 `generate_acceptance_criteria=False`，只持久化 scenarios。

重新生成行为：

- 如果存在 user feedback 且 draft 中有 raw Gherkin，优先使用 `scenario-feedback-skill` 修订 Gherkin。
- 如果没有 raw Gherkin，则重新调用 `scenario-generation-skill`。
- 将修订后的 Gherkin 再拆回当前 draft response 结构。

### Skill-backed Acceptance Criteria Service 职责

新增 `SkillBackedAcceptanceCriteriaGenerationService`。

它的存在是为了保留当前独立的成功标准 API。

行为：

- 和当前服务一样加载已有 scenarios。
- 根据已有 `ScenarioModel` 组装每组 feature/actor 对应的 Gherkin 输入。
- 如果有 user feedback，优先使用 `scenario-feedback-skill` 修订。
- 如果没有 user feedback，建议新增一个轻量的 skill 方法，从已有 scenario list 生成 criteria。

推荐第一版新增一个场景成功标准生成函数，放在 `scenario-generation-skill` 内：

```text
requirement + feature + actor + existing scenario list
```

输出：

```text
scenario_id -> acceptance_criteria[]
```

这样可以避免“重新生成一批 Gherkin scenario 后再用标题模糊匹配已有 scenario_id”的风险。

### 当前逻辑需要调整的点

- 当前场景和成功标准是两个相对独立的 LLM 流程。skill-backed 版本应以 Gherkin 作为核心中间结构。
- draft payload 需要新增内部字段 `raw_gherkin` 和草稿级 criteria，即使 response schema 不暴露它们。
- 场景确认时，如果 `generate_acceptance_criteria=True`，应持久化同一份 Gherkin 中的 criteria，而不是再次调用旧的成功标准生成器。
- 有用户反馈的重新生成，应优先使用 `scenario-feedback-skill`。
- 独立成功标准 API 需要一条新的 skill-backed 路径，因为它必须保留已有 scenario id。

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
- 能从已有 scenario 和 criteria 重新组装 raw Gherkin。

Kano scope adapter 测试：

- 能把 `M/O/A/I/R/Q` 映射为 scope status。
- 能把 summary 和 explanation 映射到 `ScopeNode` 相关字段。
- 能保证所有叶子 feature 都有 scope。
- 缺少图表依赖时能优雅降级。

Service 测试：

- `create_draft` 返回与旧服务相同的 response schema。
- `confirm_draft` 持久化与旧服务兼容的数据库记录。
- 场景确认且 `generate_acceptance_criteria=True` 时，同时持久化 scenarios 和 criteria。
- `service_registry` 默认使用 legacy，并能通过环境变量切换到 skill。

## 阶段 6：上线顺序

1. 新增 adapters 和 skill-backed services，但暂时不接入 registry。
2. 添加 adapter 测试。
3. 添加使用 mock skill 输出的 service 测试。
4. 在 `service_registry` 中增加开关，默认 `legacy`。
5. 手动验证 `legacy` 模式下所有现有草稿 API 行为不变。
6. 手动验证 `skill` 模式下所有草稿 API 可正常创建、重新生成、确认、丢弃。
7. 等 skill 模式稳定后，再考虑是否把默认值切到 `skill`。

## 待确认决策

- 是否给数据库增加 raw Gherkin 字段。第一版可以只存在内存 draft 中。
- `Common` 是否映射到所有 actor 或默认 actor。推荐：所有 actor。
- `Attractive(A)` 且 Better 较高时是否进入 `CURRENT`。推荐：`Better >= 0.6` 时进入 `CURRENT`。
- 图表渲染依赖是否强制安装。推荐：第一版可选，缺少依赖时图片字段为空。
- feature-tree skill 是否强制生成 description。推荐：要求生成，但 adapter 仍提供 fallback。

