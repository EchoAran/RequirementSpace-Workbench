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

因此在本地开发环境下，前端代码会默认使用相对路径 `/api` 调用接口，不需要在浏览器侧配置 CORS。

> 💡 **本地与云端部署版的区别**：
> - **本地开发**：前端不设置 `VITE_API_URL` 环境变量，API 请求自动使用默认值 `/api` 并通过 Vite 代理转发。
> - **云端部署**：前端打包时可以通过 `VITE_API_URL` 环境变量指定后端 API 服务的公网 URL。此时，前端请求将直接发送至指定的后端，需要后端配置跨域（CORS）。

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

### 数据库重置与清除 (Database Reset Drill)

#### SQLite 重置
在本地开发或测试环境下，如需完全重置 SQLite 数据库，请执行：
1. 停止后端服务。
2. 删除项目根目录下的 SQLite 数据库文件及临时文件（包括 `requirement_space.db`、`requirement_space.db-wal` 和 `requirement_space.db-shm`，如果存在）。
3. 重新启动后端服务，系统会在启动时自动执行数据表初始化和 schema 重建。

#### PostgreSQL 重置 (生产环境)
在生产环境中使用 PostgreSQL 数据库时，如需重置：
1. 停止所有连接至该数据库的后端服务实例。
2. 登录 PostgreSQL 并清空 schema 或直接重建数据库：
   ```sql
   DROP DATABASE requirement_space;
   CREATE DATABASE requirement_space;
   ```
3. 重新部署并启动后端。检测到空库后，服务会通过 SQLAlchemy metadata 一次性创建完整 schema，再将 Alembic 版本标记为 `head`；已有完整 schema 的数据库启动时则执行常规 `alembic upgrade head`。

> ⚠️ **警告**：数据库重置属于高风险操作，在执行前请确保已完成备份。


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

## 安全与运维配置 (Security & Operations)

### 1. 管理员邀请码配置 (`ADMIN_INVITE_CODE_HASH`)
本系统通过注册机制区分管理员和普通用户。管理员在注册时必须填写正确的邀请码（Invite Code）。
为了安全，`.env` 中保存的是邀请码的 **Argon2 散列哈希值**。你可以使用如下命令在本地生成该哈希：
```powershell
.\.venv\Scripts\python.exe -c "from backend.core.security import hash_password; print(hash_password('您的明文邀请码'))"
```
生成后，将哈希字符串填入 `.env` 中的 `ADMIN_INVITE_CODE_HASH` 即可。

### 2. 用户 LLM 密钥加密与轮转 (`LLM_CONFIG_ENCRYPTION_KEY`)
普通用户填写的个人 LLM API Key 以加密形式（使用 Fernet 对称加密）保存在数据库中。
* **密钥设置**：需要一个 32 字节的 URL 安全 base64 编码的密钥，可通过以下命令生成：
  ```powershell
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
* **轮转注意事项**：
  * **一旦投入使用，请勿随意修改或遗失该密钥**。
  * 如果直接修改已有数据库的 `LLM_CONFIG_ENCRYPTION_KEY`，解密旧用户 API Key 时会引发 `InvalidToken` 解密失败错误。
  * 若必须要轮转密钥，需在轮转前引导用户导出/暂存配置，或在轮转后重置其个人 LLM 设置。

### 3. 生产环境 CORS 安全限制
当部署为生产模式（`ENV=production`）时，后端将对 CORS 跨域配置进行强制性安全校验：
* **禁止通配符**：由于应用启用了 Cookie 凭证（Credentials），在 production 下，若 `ALLOWED_ORIGINS` 包含通配符 `*` 或为空，后端在服务启动时会直接触发 `ValueError` 异常并退出。
* **显式指定前端来源**：请在 `.env` 中通过 `ALLOWED_ORIGINS` 显式设置允许访问的前端公网 URL（如 `https://workbench.mydomain.com`）。如果有多个，使用英文逗号分隔。

### 4. 过期 Session 清理命令与定时任务
为了保持数据库性能，系统提供了专门的 API 用于清理过期和已注销的 Session 会话数据。
* **清理接口**：`POST /api/auth/cleanup-sessions`
* **权限要求**：必须以管理员身份调用此接口。
* **定时任务设置 (Cron Job)**：
  可以在生产环境中使用 `cron` 等工具定期执行清理。例如，每天凌晨 3 点使用 `curl` 自动发送清理请求：
  ```bash
  0 3 * * * curl -X POST https://api.yourdomain.com/api/auth/cleanup-sessions -H "Cookie: auth_session=YOUR_ADMIN_SESSION_TOKEN" -H "Content-Length: 0"
  ```
  或者在后端宿主机上配置脚本自动调用。

### 5. HTTPS 与 Cookie 安全部署说明
在生产环境中发布时，必须确保全站启用 HTTPS，并严格配置 Cookie 相关的安全标志以防止 CSRF 或 Session 劫持：
* **`AUTH_COOKIE_SECURE=true`**：在 `.env` 中必须设置为 `true`。这将指示浏览器仅通过加密的 HTTPS 连接传输会话 Cookie。如果通过 HTTP 访问，Cookie 将不会被发送。
* **`AUTH_COOKIE_DOMAIN`**：如有需要可显式配置为您的业务主域名（如 `yourdomain.com`），支持子域间共享登录态。
* **`AUTH_COOKIE_SAMESITE=lax`**（推荐）或 `strict`：限制跨站请求携带 Cookie。
* **`HttpOnly` 标志**：系统内核强制为所有登录 Cookie 设置 `HttpOnly`，以防止通过 XSS 漏洞被前端 JavaScript 读取。

### 6. 版本回滚与灾备方案 (Rollback & Backup)
在系统升级或发布新版本出现异常时，应按如下步骤执行回退：
1. **数据备份**：在任何版本升级/数据重置前，请先备份数据库：
   - 对于 SQLite：备份根目录下的 `requirement_space.db` 文件。
   - 对于 PostgreSQL：使用 `pg_dump` 备份整个数据库。
2. **代码回退**：通过 Git 将应用程序代码回退至上一个稳定版本：
   ```bash
   git checkout <last_stable_tag>
   ```
3. **数据库回退与还原**：
   - 如果新版本涉及 schema 迁移（Alembic），可以执行回滚命令：
     ```bash
     .\.venv\Scripts\python.exe -m alembic downgrade -1
     ```
     或者回退到指定版本：
     ```bash
     .\.venv\Scripts\python.exe -m alembic downgrade <previous_revision_id>
     ```
   - 若回滚失败，应将升级前备份的数据库文件进行还原覆盖。

## 长耗时原型生成部署配置

原型生成为同步 HTTP 接口，在大型项目中并发执行多路 LLM 页面生成可能持续数分钟。若在生产环境下部署，请注意对整个请求链路上的反向代理及网关调整超时时间限制（推荐配置 10 分钟 / 600 秒）。

### 1. Nginx 代理配置

```nginx
location /api/ {
    proxy_connect_timeout 30s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    proxy_pass http://127.0.0.1:8000;
}
```

### 2. Gunicorn 启动超时配置

若使用 Gunicorn 托管 FastAPI，请在命令行中显式增大 `--timeout` 参数：

```bash
gunicorn backend.main:app \
  -k uvicorn.workers.UvicornWorker \
  --timeout 600 \
  --bind 127.0.0.1:8000
```

### 3. Vite 本地开发代理超时

本地开发环境下，前端 Vite 配置 (`frontend/vite.config.ts`) 已经自动调大了开发代理的超时时间 (`timeout: 600_000`, `proxyTimeout: 600_000`)。

---

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
