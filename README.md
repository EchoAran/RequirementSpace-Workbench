# RequirementSpace Workbench

RequirementSpace Workbench 是一个面向产品需求分析和需求空间建模的本地工作台。它把原始需求逐步整理为参与者、功能树、业务流程、业务对象、场景、验收标准、范围决策和原型预览，帮助团队在进入开发前发现缺口、确认假设并沉淀可交付的需求资产。

项目采用前后端分离架构：

- 后端：FastAPI + SQLAlchemy + SQLite + Alembic
- 前端：React + TypeScript + Vite + Zustand + Tailwind CSS
- AI 能力：通过统一 LLM Chat Completions 兼容接口，支持 legacy 生成器和 skill-backed 生成器两种模式
- 本地开发：Vite dev server 代理 `/api` 到 FastAPI，前端代码始终使用相对路径调用接口

## 核心能力

- 项目创建：从自然语言需求创建项目，也支持空白项目手动建模。
- What 阶段：维护系统参与者和功能能力树，支持 AI 草稿生成、确认、丢弃和按反馈重新生成。
- How 阶段：维护用户场景、验收标准、业务流程和业务对象，支持阶段门禁和缺口感知。
- Scope 阶段：维护功能范围决策，包括本期、暂缓、排除，以及 Kano 分析结果。
- AI 感知与补齐：根据当前阶段自动识别缺口，生成 slot filling 草稿或方案 choice。
- 预览与导出：生成原型预览，支持 shadow draft、提交预览草稿、Markdown/JSON 导出。
- 审计与一致性：后端保留审计日志、阶段健康度、问题检测和影响预览能力。

## 目录结构

```text
.
├── backend/
│   ├── main.py                         # FastAPI 应用入口
│   ├── api/
│   │   ├── routes/                     # HTTP 路由
│   │   ├── schemas/                    # Pydantic 请求/响应模型
│   │   └── services/                   # 应用服务层
│   ├── core/
│   │   ├── generators/                 # legacy AI 生成器
│   │   ├── perceptrons/                # 缺口感知与槽位填充
│   │   ├── detectors/                  # 问题检测与问题处理
│   │   ├── engines/                    # patch 应用引擎
│   │   ├── shadow_preview/             # 预览草稿校验
│   │   └── stage_gates/                # 阶段门禁判断
│   ├── database/
│   │   ├── database.py                 # SQLite 连接、会话、启动迁移
│   │   └── model.py                    # SQLAlchemy 数据模型
│   ├── integration/
│   │   ├── skill_backed_services/      # skill-backed 服务适配层
│   │   ├── feature-tree-skill/
│   │   ├── ft-feedback-skill/
│   │   ├── gherkin-code-skill/
│   │   ├── kano-skill/
│   │   ├── scenario-feedback-skill/
│   │   └── scenario-generation-skill/
│   └── services/
│       └── LLM_service.py              # 统一 LLM HTTP 客户端
├── frontend/
│   ├── src/
│   │   ├── pages/                      # 页面：概览、What、How、Scope、Preview
│   │   ├── components/                 # 布局、右侧面板、共享组件
│   │   ├── core/                       # 前端 IR schema、选择器、阶段规则
│   │   ├── lib/                        # HTTP/API 封装
│   │   └── store/                      # Zustand 工作区状态
│   ├── package.json
│   └── vite.config.ts                  # Vite 配置和 /api 代理
├── alembic/                            # 数据库迁移脚本
├── docs/                               # 设计记录和实施计划
├── alembic.ini
├── requirements.txt
└── README.md
```

## 环境要求

- Python 3.10 或更高版本，建议使用 Python 3.11+
- Node.js 20 LTS 或更高版本
- npm 10 或更高版本
- Windows PowerShell、macOS Terminal 或 Linux shell

## 后端依赖

所有 Python 直接依赖声明在根目录 `requirements.txt`，传递依赖由 pip 自动解析。

主要组：

| 组 | 依赖 | 用途 |
|---|---|---|
| 运行时 | fastapi, uvicorn, pydantic | API 框架和开发服务器 |
| 持久化 | SQLAlchemy, aiosqlite, alembic | ORM、数据库、迁移 |
| LLM 客户端 | httpx, openai, python-dotenv | HTTP 调用、OpenAI SDK、环境变量读取 |
| IR 序列化 | dataclasses-json, inflection | 旧版需求模型序列化 |
| 图表 | matplotlib | Kano 图表渲染 |
| 平台兼容 | tzdata | Windows zoneinfo 支持 |

## 环境变量

在项目根目录创建 `.env`。该文件包含密钥，不应提交到 Git。

```env
REQUIREMENTSPACE_GENERATION_BACKEND=legacy
LLM_API_URL=https://your-llm-endpoint.example.com
LLM_API_KEY=your_api_key
LLM_MODEL_NAME=your_model_name
LLM_TEMPERATURE=0.2
OPENAI_API_KEY=your_openai_api_key
```

变量说明：

- `REQUIREMENTSPACE_GENERATION_BACKEND`：生成后端模式。可选 `legacy` 或 `skill`，默认 `legacy`。
- `LLM_API_URL`：兼容 OpenAI Chat Completions 的服务地址，不要包含末尾 `/v1/chat/completions`。
- `LLM_API_KEY`：调用统一 LLM 服务的密钥。
- `LLM_MODEL_NAME`：模型名称。
- `LLM_TEMPERATURE`：采样温度，代码会转换为浮点数。
- `OPENAI_API_KEY`：独立运行 `backend/integration/*-skill` CLI 时使用。Workbench 通过 `LLM_*` 变量调用统一 LLM 客户端。

如果缺少 `LLM_*` 配置，AI 调用会返回空结果或生成失败，但非 AI 的手动建模能力仍可使用。

## 本地启动

### 1. 创建并安装后端环境

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

### 2. 启动后端

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

macOS/Linux:

```bash
./.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

后端启动时会执行 `backend.database.database.init_db()`，自动通过 Alembic 初始化或升级根目录的 `requirement_space.db`。

常用地址：

- 健康检查：http://127.0.0.1:8000/api/health
- OpenAPI 文档：http://127.0.0.1:8000/docs

### 3. 安装并启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认监听：

- http://localhost:3000

Vite 会把前端发往 `/api` 的请求代理到：

- http://127.0.0.1:8000

因此前端代码不需要配置后端 URL，也不需要在浏览器侧处理 CORS。

## 常用脚本

后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
```

前端：

```powershell
cd frontend
npm run dev
npm run build
npm run preview
npm run lint
```

注意：`frontend/package.json` 中的 `clean` 脚本使用 `rm -rf dist`，在原生 Windows PowerShell 中可能不可用，可使用 Git Bash、WSL，或手动删除 `frontend/dist`。

## 数据库和迁移

- 默认数据库文件是根目录 `requirement_space.db`。
- 数据库文件属于本地运行数据，已在 `.gitignore` 中忽略。
- 迁移配置在 `alembic.ini`。
- 迁移脚本位于 `alembic/versions/`。
- 应用启动时会自动执行迁移逻辑。

如果需要重建本地数据库，可以停止后端，删除 `requirement_space.db`，再重新启动后端。删除数据库会清空所有本地项目数据。

## 需求空间工作流

### 1. 项目入口

用户可以在首页选择已有项目，也可以用原始需求创建新项目：

- 空白项目：只保存需求和项目基础信息。
- AI 草稿项目：先生成项目名、描述、参与者和功能草稿，用户确认后写入数据库。

### 2. What 阶段

What 阶段关注要做什么：

- 参与者 Actor
- 功能树 Feature Tree
- 功能和参与者之间的关系

该阶段可通过 AI 生成参与者、功能树，也可手动新增、编辑和删除。

### 3. How 阶段

How 阶段关注系统如何运作：

- 场景 Scenario
- 验收标准 Acceptance Criteria
- 业务流程 Flow
- 流程步骤 Flow Step
- 业务对象 Business Object
- 业务对象属性 Business Object Attribute

阶段门禁会检测缺失的场景、验收标准、流程、数据对象等内容，并提供手动修复或 AI 补齐入口。

### 4. Scope 阶段

Scope 阶段关注交付边界：

- `current`：本期交付
- `postponed`：暂缓
- `exclude`：排除

Scope 可以结合 Kano 分析，保存正向/反向摘要、Kano 分类和决策理由。项目也支持跳过或重置 Kano 流程。

### 5. Preview 阶段

Preview 阶段会基于当前需求空间生成可查看的原型预览。Shadow draft 能在不立即污染真实项目数据的情况下生成预览草稿，用户确认后再提交。

## 后端 API 概览

完整接口以 FastAPI 文档为准：http://127.0.0.1:8000/docs

主要路由分组：

- `GET /api/health`：服务健康检查
- `/api/projects`：项目列表、项目详情、更新、删除、导出
- `/api/blank_projects`：创建空白项目
- `/api/project_creation_drafts`：项目创建草稿生成、确认、重生成、丢弃
- `/api/projects/{project_id}/actors`：参与者 CRUD
- `/api/projects/{project_id}/features`：功能 CRUD
- `/api/projects/{project_id}/scenarios`：场景和验收标准 CRUD
- `/api/projects/{project_id}/business_objects`：业务对象和属性 CRUD
- `/api/projects/{project_id}/flows`：业务流程和步骤 CRUD
- `/api/projects/{project_id}/features/{feature_id}/scope`：单个功能范围决策
- `/api/projects/{project_id}/scope`：项目级 Scope/Kano 操作
- `/api/*_generation_drafts`：各类 AI 生成草稿
- `/api/perception_slot_filling_drafts`：缺口感知后的槽位补齐草稿
- `/api/projects/{project_id}/issues`：问题检测和问题解决
- `/api/projects/{project_id}/next-suggestion`：下一步建议
- `/api/projects/{project_id}/prototype-preview`：原型预览生成和读取
- `/api/projects/{project_id}/preview-shadow-drafts`：预览 shadow draft

## AI 生成后端模式

服务注册逻辑位于 `backend/api/services/service_registry.py`。

`legacy` 模式：

- 默认模式。
- 使用 `backend/core/generators`、`backend/core/perceptrons` 中的本地提示词和解析逻辑。
- 通过 `backend/services/LLM_service.py` 调用统一 LLM Chat Completions 兼容接口。

`skill` 模式：

- 通过 `REQUIREMENTSPACE_GENERATION_BACKEND=skill` 启用。
- 项目创建、功能树、场景、验收标准、Scope、原型等能力会切换到 `backend/integration/skill_backed_services`。
- Actor 和 Flow 生成仍使用 legacy 服务，这是当前设计中的正常不对称。
- 集成的 skill 包依赖 `openai>=1.56.0,<2.0`，该依赖已在根目录 `requirements.txt` 中声明。

## 前端架构说明

- `frontend/src/lib/http.ts`：统一封装 fetch，请求自动加 `/api` 前缀。
- `frontend/src/lib/api.ts`：工作台 API 客户端。
- `frontend/src/store/useWorkspaceStore.ts`：项目列表、当前项目、生成状态、错误信息和页面状态。
- `frontend/src/core/schema.ts`：前端需求空间 IR 类型。
- `frontend/src/core/selectors.ts`：阶段健康度、门禁、建议和 UI 派生数据。
- `frontend/src/pages`：业务页面。
- `frontend/src/components/right-panel`：不同对象的右侧编辑面板。
- `frontend/src/components/shared`：草稿弹窗、状态徽章、AI 操作栏、问题卡片等共享组件。

## Git 忽略策略

当前 `.gitignore` 的原则：

- 忽略本地密钥：`.env`、`.env.*`
- 保留可提交示例：`!.env.example`
- 忽略虚拟环境、缓存、构建产物和测试覆盖率文件
- 忽略本地 SQLite 数据库和 journal 文件
- 忽略前端依赖和构建输出
- 不忽略 `docs/`，因为设计记录、实施计划和项目文档应该可以被版本控制

## 常见问题

### 后端启动后提示数据库表已存在

当前启动逻辑会在检测到已有 `projects` 表时执行 Alembic stamp，避免重复建表。如果本地库结构已经损坏，可以备份后删除 `requirement_space.db`，再重新启动服务。

### 前端请求失败或显示网络错误

确认两个服务都已启动：

- 后端：http://127.0.0.1:8000/api/health
- 前端：http://localhost:3000

前端必须通过 Vite dev server 访问，直接打开静态文件不会启用 `/api` 代理。

### AI 生成失败

检查 `.env` 中的 `LLM_API_URL`、`LLM_API_KEY`、`LLM_MODEL_NAME`、`LLM_TEMPERATURE` 是否都存在。`LLM_API_URL` 应该是服务根地址，代码会自动拼接 `/v1/chat/completions`。

### skill 模式导入失败

确认已安装根目录依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果独立运行 integration 下的 skill CLI，还需要设置 `OPENAI_API_KEY`。

### 文本出现乱码

项目中部分历史文件存在编码显示问题。新增和修改文档建议统一保存为 UTF-8。

## 开发建议

- 后端改模型后，优先补 Alembic migration，而不是直接依赖 `Base.metadata.create_all`。
- 前端新增接口时，先在 `frontend/src/lib/api.ts` 封装，再在 store 或页面中调用。
- 新增需求对象时，需要同步更新后端模型、schema、service、route、前端 IR 类型和选择器。
- AI 草稿类能力应保持“生成草稿 -> 用户确认 -> 写入真实项目”的流程，避免未经确认直接污染工作区。
- 本地运行数据和密钥不要提交，文档和迁移脚本应提交。
