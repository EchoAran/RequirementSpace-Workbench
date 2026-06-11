# RequirementSpace Workbench

RequirementSpace Workbench 是一个面向产品需求分析与需求空间建模的本地工作台。它将原始需求逐步整理为参与者、功能树、场景、验收标准、业务流程、业务对象、范围决策和原型预览，并通过 AI 辅助发现缺口、生成草稿和修复问题。

当前版本已经支持多用户登录、用户数据隔离、用户级 LLM 配置和公开项目标识。

## 技术栈

- 后端：FastAPI、SQLAlchemy、SQLite/PostgreSQL、Alembic
- 前端：React 19、TypeScript、Vite、Zustand、Tailwind CSS
- AI：兼容 OpenAI Chat Completions 的 HTTP 接口
- 鉴权：服务端 Session、HttpOnly Cookie、Argon2 密码哈希
- 密钥保护：Fernet 加密普通用户保存的 LLM API Key

## 核心能力

- 从自然语言需求创建项目，或创建空白项目手动建模
- What 阶段：参与者、功能树及其关系
- Flow 阶段：场景、验收标准、业务流程和业务对象
- Scope 阶段：本期、暂缓、排除与 Kano 分析
- AI 感知、槽位补全、单对象新增和解释式编辑
- 多候选 Choice Group 生成与选择
- 问题检测、修复草稿、影响预览和阶段门禁
- 原型预览、Shadow Draft、确认提交和 Markdown/JSON 导出
- 多用户项目、草稿、会话及生成数据隔离

## 用户与 LLM 配置

系统包含两种用户角色：

| 角色 | 注册方式 | LLM 配置来源 |
|---|---|---|
| 普通用户 `user` | 直接注册，不填写邀请码 | 在“账户设置”中配置自己的 API URL、API Key 和 Model |
| 管理员 `admin` | 注册时填写正确的邀请码 | 直接使用服务器 `.env` 中的 `LLM_API_URL`、`LLM_API_KEY` 和 `LLM_MODEL_NAME` |

普通用户的 API Key 会加密后保存到数据库。接口和页面只返回 Key 的末四位，不返回明文。

项目在数据库内部仍使用整数主键维护关系，但浏览器 URL、前端状态和外部 API 使用不可枚举的公开 UUID：

```text
/projects/550e8400-e29b-41d4-a716-446655440000/overview
```

不同用户无法通过公开 ID 读取或修改他人的项目及其关联资源；不存在的项目和无权访问的项目统一返回 `404`。

## 目录结构

```text
.
|-- backend/
|   |-- api/
|   |   |-- dependencies/       # 鉴权、归属校验、请求级 LLM 上下文
|   |   |-- routes/             # HTTP 路由
|   |   |-- schemas/            # Pydantic 请求与响应模型
|   |   `-- services/           # 应用服务
|   |-- core/                   # 生成器、检测器、门禁、安全工具
|   |-- database/               # SQLAlchemy 模型和数据库初始化
|   |-- integration/            # skill-backed 生成服务
|   |-- services/               # 统一 LLM 客户端
|   `-- tests/                  # 后端测试
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |-- pages/
|   |   |-- lib/                # HTTP、鉴权和业务 API
|   |   `-- store/              # 鉴权和工作区状态
|   `-- package.json
|-- alembic/                    # 数据库迁移
|-- docs/                       # 分析、设计和实施计划
|-- .env.example
|-- requirements.txt
|-- requirements-dev.txt
`-- README.md
```

## 环境要求

- Python 3.10+，推荐 Python 3.11
- Node.js 20+
- npm 10+

## 快速开始

### 1. 安装后端依赖

PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

macOS/Linux：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements-dev.txt
```

仅部署运行环境时可安装 `requirements.txt`。

### 2. 创建环境配置

```powershell
Copy-Item .env.example .env
```

macOS/Linux：

```bash
cp .env.example .env
```

必须生成独立的 LLM 配置加密密钥：

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将输出填入 `.env` 的 `LLM_CONFIG_ENCRYPTION_KEY`。该密钥一旦用于保存用户 LLM 配置，就不能随意更换或丢失，否则已有 API Key 将无法解密。

### 3. 配置管理员邀请码

先生成邀请码的 Argon2 哈希：

```powershell
.\.venv\Scripts\python.exe -c "from backend.core.security import hash_password; print(hash_password('your-invite-code'))"
```

将输出完整填入：

```env
ADMIN_INVITE_CODE_HASH=$argon2id$...
```

注册页面填写原始邀请码 `your-invite-code` 时，用户会被创建为管理员。未填写邀请码的注册始终创建普通用户。

### 4. 启动后端

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

- 健康检查：<http://127.0.0.1:8000/api/health>
- OpenAPI：<http://127.0.0.1:8000/docs>

后端启动时会检查数据库结构并执行 Alembic。空数据库会从当前 SQLAlchemy metadata 创建完整结构；旧数据库缺少 `users` 或 `projects.public_id` 时会拒绝启动，必须按下文重置数据库。

### 5. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认地址为 <http://localhost:3000>。开发服务器会把 `/api` 代理到 <http://127.0.0.1:8000>。

## 环境变量

完整模板见 [.env.example](.env.example)。

| 变量 | 必需 | 说明 |
|---|---|---|
| `DATABASE_URL` | 否 | 默认 `sqlite+aiosqlite:///./requirement_space.db`，也支持 PostgreSQL |
| `ENV` | 是 | `development` 或 `production` |
| `LLM_CONFIG_ENCRYPTION_KEY` | 是 | 加密普通用户 API Key 的 Fernet 密钥 |
| `ADMIN_INVITE_CODE_HASH` | 否 | 管理员邀请码的 Argon2 哈希；为空时不能注册管理员 |
| `AUTH_SESSION_EXPIRE_DAYS` | 否 | Session 有效天数，默认 30 |
| `AUTH_COOKIE_SECURE` | 生产必需 | 生产环境必须为 `true`，并配合 HTTPS |
| `AUTH_COOKIE_SAMESITE` | 否 | Cookie 的 SameSite 属性，默认 `lax`，跨域部署时需设为 `none` |
| `AUTH_COOKIE_DOMAIN` | 否 | Cookie 作用域名限制，默认无限制 |
| `ALLOWED_ORIGINS` | 是 | 允许携带 Cookie 的前端来源，逗号分隔 |
| `LLM_API_URL` | 管理员 AI 必需 | 管理员使用的 OpenAI 兼容服务根地址，不含 `/v1/chat/completions` |
| `LLM_API_KEY` | 管理员 AI 必需 | 管理员使用的服务器 API Key |
| `LLM_MODEL_NAME` | 管理员 AI 必需 | 管理员使用的模型名 |
| `LLM_TEMPERATURE` | 否 | LLM 采样温度 |
| `REQUIREMENTSPACE_GENERATION_BACKEND` | 否 | `legacy` 或 `skill` |

普通用户不读取服务器的 `LLM_API_*`。如果普通用户尚未在账户设置中保存完整配置，AI 接口会返回 `409 llm_config_required`。

## 数据库

### 本地 SQLite

默认运行文件：

```text
requirement_space.db
requirement_space.db-wal
requirement_space.db-shm
```

这些文件包含用户、项目和加密凭据，已被 Git 忽略。

当前用户鉴权与公开项目 ID 版本不提供旧数据兼容迁移。遇到旧 schema 时：

1. 停止后端。
2. 备份需要保留的数据。
3. 删除上述三个 SQLite 文件。
4. 重新启动后端。

PowerShell：

```powershell
Remove-Item requirement_space.db, requirement_space.db-wal, requirement_space.db-shm -ErrorAction SilentlyContinue
```

### PostgreSQL

通过 `DATABASE_URL` 配置连接。全新部署应使用空数据库或空 schema，启动时会创建完整结构并标记 Alembic 版本。

重置生产数据库属于破坏性操作，执行前必须备份，并确认所有应用实例已经停止。在云端 PostgreSQL 数据库（如 Neon）中，可以通过重建 `public` 架构（Schema）来进行快速重置：

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO public;
```

重置完成后重新启动应用，系统检测到空数据库将自动创建最新版本的完整表结构。

## 安全配置

- 密码使用 Argon2 哈希，不保存明文。
- Session Token 仅以哈希形式存入数据库。
- 登录 Cookie 为 `HttpOnly`；生产环境强制要求 `AUTH_COOKIE_SECURE=true`。
- 生产环境 `ALLOWED_ORIGINS` 必须显式配置，不能使用 `*`。
- 普通用户 LLM API Key 使用 Fernet 加密。
- 500 响应不会向客户端暴露内部异常详情，服务端日志会进行凭据脱敏。
- 项目及关联数据通过 `owner_user_id` 和当前 Session 执行归属校验。

生产环境示例：

```env
ENV=production
AUTH_COOKIE_SECURE=true
ALLOWED_ORIGINS=https://workbench.example.com
```

生产环境必须通过 HTTPS 提供前后端服务。

## 常用命令

后端：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm run dev
npm run lint
npm test
npm run build
npm run preview
npm run clean
```

## API 概览

- `/api/auth/register`：注册并创建 Session
- `/api/auth/login`：登录
- `/api/auth/logout`：注销并撤销 Session
- `/api/auth/me`：当前用户
- `/api/account/llm-config`：普通用户 LLM 配置查询、保存和删除
- `/api/account/llm-config/test`：测试当前或待保存的 LLM 配置
- `/api/projects`：当前用户的项目列表与项目操作
- `/api/projects/{project_id}/...`：使用公开 UUID 的项目资源接口
- `/api/*_generation_drafts`：AI 生成草稿
- `/api/projects/{project_id}/issues`：问题检测与修复
- `/api/projects/{project_id}/prototype-preview`：原型预览
- `/api/projects/{project_id}/preview-shadow-drafts`：Shadow Draft 生成与提交

以运行中的 FastAPI OpenAPI 文档为完整接口准则。

## 长耗时请求

原型和多候选生成可能持续数分钟。生产反向代理建议为 `/api` 配置至少 600 秒读取超时：

```nginx
location /api/ {
    proxy_connect_timeout 30s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    proxy_pass http://127.0.0.1:8000;
}
```

Vite 本地代理已配置 `600_000` 毫秒超时。

## 文档

设计分析和分阶段实施记录位于 [docs/implementation_plan](docs/implementation_plan)。其中用户鉴权、数据隔离、用户级 LLM 配置和公开项目 ID 的完整设计位于：

```text
docs/implementation_plan/user_auth_and_api_key/
```
