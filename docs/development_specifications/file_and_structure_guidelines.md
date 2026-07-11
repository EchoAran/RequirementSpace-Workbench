# 文件与目录结构开发规范

本文档用于约束 RequirementSpace Workbench 后续新增、迁移和重命名文件时的结构决策。目标是维持高内聚、低耦合，避免重新退回按技术层横向堆叠的 `routes`、`schemas`、`services` 扁平结构。

## 1. 总原则

- 按业务领域组织代码，优先把相关的路由、Schema、应用服务、端口和规则放在同一领域模块内。
- 跨模块依赖只能通过 `public.py`、`ports.py` 或明确的稳定接口完成，不直接导入对方内部 `application`、`routes`、`schemas` 文件。
- 不因为“复用方便”创建新的全局大目录。新增横向目录前必须先证明它是基础设施能力，而不是某个领域逻辑的外溢。
- 文件移动和命名治理不得改变外部 HTTP URL、JSON 字段或数据库 Schema。需要改变外部契约时，必须走独立迁移提案。

## 2. 命名规范

### Python 后端

- 目录、文件、函数、方法、变量统一使用 `snake_case`。
- 类名使用 `PascalCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 文件名不得包含大写字母、空格、连字符或含混缩写。
- 已成为领域术语的缩写可以保留在类名或字段含义中，例如 `AI`、`LLM`、`AC`、`ID`；但文件名仍使用小写形式，例如 `llm_handler_service.py`。

### 前端

- React 组件文件保持 `PascalCase.tsx`，例如 `StageGuidanceBanner.tsx`。
- 非组件工具、store、API client 使用 `camelCase.ts` 或既有目录约定。
- 前端不强制套用 Python 的文件命名规则，但同一目录内必须保持一致。

### 文档

- 计划、规范、分析报告优先使用小写 `snake_case.md`。
- 用户明确指定的目录名称可以保留原样，例如 `docs/Development Specifications`。
- 历史迁移文档可以保留旧路径引用，但新增规范文档不得继续推荐旧扁平目录。

## 3. 后端目录结构规则

后端业务代码应优先放在：

```text
backend/api/modules/<domain>/
```

推荐模块结构：

```text
<domain>/
  routes.py 或 routes/
  schemas.py 或 schemas/
  public.py
  ports.py
  application/
  domain/
```

使用规则：

- `routes` 只负责 HTTP 编排、鉴权依赖、请求响应转换。
- `schemas` 只定义 HTTP 边界模型，不作为跨模块领域模型。
- `application` 放用例服务、编排器、handler。
- `domain` 放纯业务规则和不依赖 FastAPI/SQLAlchemy Session 的核心逻辑。
- `public.py` 是模块对外导出入口。
- `ports.py` 是跨模块反向依赖、运行时注入或适配器注册入口。

禁止恢复以下旧结构：

```text
backend/api/routes/
backend/api/schemas/
backend/api/services/
```

## 4. 依赖方向

允许的常规方向：

```text
routes -> application -> domain
application -> ports/public
integration -> public/ports
core -> core 或显式 ports
```

禁止：

- `backend/core` 直接导入 `backend.api` 的具体实现。
- 一个模块直接导入另一个模块的内部 `application` 文件。
- 路由直接承载复杂业务规则或数据库写入细节。
- Schema 在多个领域之间随意共享。

如果确实需要跨模块协作：

1. 优先在被依赖模块暴露 `public.py`。
2. 若存在反向依赖或插件式替换，定义 `ports.py`。
3. 为新增依赖补充架构测试或在例外清单中说明原因和删除条件。

## 5. 文件拆分规则

以下情况应拆分文件：

- 单文件超过约 500 行且包含多个职责。
- 同时包含 HTTP、数据库写入、业务规则、外部服务调用中的三类以上职责。
- 一个类既负责创建、确认、废弃、校验、持久化等完整生命周期，且任一职责可独立测试。
- 修改一个小功能时需要理解大量无关上下文。

拆分优先级：

1. 先按用例拆分，例如 `draft_creator.py`、`draft_confirmer.py`。
2. 再按技术职责拆分，例如 `normalizers.py`、`validators.py`。
3. 最后才抽公共工具，避免过早抽象。

## 6. 兼容层和重命名规则

- 内部命名重构时，新旧符号应短期共存。
- 所有 alias/shim 必须有可导入兼容测试。
- 兼容测试至少验证：
  - 新旧符号都能从公开 facade 导入；
  - 旧符号与新符号指向同一对象，或委托关系明确；
  - 全量测试矩阵包含该测试。
- 删除兼容层前必须确认全仓旧 import 为零，并更新文档。

## 7. 结构改动流程

任何结构改动至少执行以下步骤：

1. 明确所属领域模块。
2. 更新 import，禁止留下旧路径 shim，除非阶段计划明确允许。
3. 运行定向测试。
4. 运行架构依赖测试。
5. 如涉及 HTTP 边界，运行 OpenAPI 快照测试。
6. 更新对应文档或迁移清单。

推荐验证命令：

```powershell
python -m compileall -q backend
pytest backend/tests/contracts/test_architecture_dependency.py -q
pytest backend/tests/contracts/test_openapi_snapshot.py -q
```

## 8. 当前项目结构基线

当前后端领域模块基线：

```text
backend/api/modules/
  ai_interaction/
  auth_account/
  collaboration/
  decision_workflow/
  diagnosis_quality/
  preview_convergence/
  project_configuration/
  project_knowledge/
  project_lifecycle/
  requirements_core/
```

新增后端业务能力应优先归入上述模块；只有出现稳定的新业务边界时，才新增同级领域模块。
