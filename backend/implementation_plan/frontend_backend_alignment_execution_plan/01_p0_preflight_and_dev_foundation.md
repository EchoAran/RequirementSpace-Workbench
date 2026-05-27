# P0：联调前置基础与工程卫生

## 一、阶段目标

清除前后端联调的基础阻断，让工程具备稳定的本地开发、类型检查、后端启动和 HTTP 请求能力。

本阶段不解决业务功能完整性，只解决“能不能可靠启动、请求、构建、定位错误”的问题。

## 二、背景问题

来自差异报告的关键事实：

- `frontend/src/lib/api.ts` 当前是 localStorage Mock，没有真实 HTTP client。
- `npm run lint` 当前仍失败，错误来自真实 `frontend/src` 源码。
- 后端在项目 `.venv\Scripts\python.exe` 中可以成功导入 `backend.main`，输出 `ok 81`。
- `backend/main.py` 没有 CORS 配置。
- `frontend/vite.config.ts` 没有 `/api` proxy。

## 三、范围

### 本阶段必须做

1. 修复前端类型检查阻断。
2. 明确前后端本地启动方式。
3. 配置 Vite proxy 作为唯一默认请求转发方式。
4. 建立真实 HTTP client 基础封装。
5. 保留 Mock 能力时必须标注为 dev fallback，不能默认作为事实源。

### 本阶段不做

- 不迁移所有 API。
- 不重构页面。
- 不实现项目聚合路由。
- 不处理 Issue/Choice/Perception 生命周期。

## 四、任务拆解

### 任务 1：修复前端类型检查

处理以下错误：

- `@/types` 缺失：
  - 将 `ChoiceCard.tsx`、`ChoiceGroupPanel.tsx`、`ChoicePanel.tsx`、`ProposalPanel.tsx` 的 import 改为 `@/core/schema`。
  - 或新增 `frontend/src/types.ts` 作为统一 re-export，但推荐直接迁移到 `@/core/schema`，避免多源类型。

- `LeftNav.tsx` 状态字符串比较错误：
  - 梳理 `buildPageHealth` 返回值的 `status` union。
  - 统一页面健康状态枚举，不要在 UI 中比较不存在的字符串，如 `已就绪`、`可生成`、`存在阻塞`、`待优化`。

- `RightObjectPanel.tsx` ErrorBoundary 类型错误：
  - 为类组件显式声明 props/state。
  - 或改为函数式错误边界替代方案。

- `React.MouseEvent` 命名空间缺失：
  - 在 `ScopedAIBar.tsx` 和 `HowItWorks.tsx` 中改为 `import type { MouseEvent } from 'react'`。
  - 或显式 `import React`。

### 任务 2：确认后端启动命令

标准启动命令建议：

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

补充检查命令：

```powershell
.venv\Scripts\python.exe -c "from backend.main import app; print('ok', len(app.routes))"
```

### 任务 3：配置跨端请求（采用 Vite Proxy 代理方案）

为避免浏览器的跨域 CORS 阻碍，并保障本地请求同源，**统一采用 Vite proxy 方案**。前端直接请求同源相对路径（如 `/api/...`），由 Vite 开发服务器代理转发至 FastAPI 后端。

在 `frontend/vite.config.ts` 中配置代理：

```ts
server: {
  hmr: process.env.DISABLE_HMR !== 'true',
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
}
```

后端无须引入 `CORSMiddleware`，确保后端接口的安全边界和整洁性。

说明：Vite proxy 是本地开发期的唯一标准转发方案。生产或部署环境不依赖 Vite dev server，需要由 Nginx、API Gateway、同源部署或其他正式网关提供等价的 `/api` 转发能力。

### 任务 4：建立 HTTP client

在 `frontend/src/lib/api.ts` 或 `frontend/src/lib/http.ts` 中建立：

- `API_BASE_URL`
- `request<T>()`
- JSON body 处理。
- HTTP error -> 前端 error message 处理。
- 后端 `detail` 字段透传。

建议保留方法签名，但实现改为可逐步替换：

```ts
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API === 'true';
```

默认必须是真实 API，Mock 只能显式开启。

### 任务 5：建立联调检查清单

新增或更新 README/计划文件中的本地联调步骤：

1. 启动后端。
2. 启动前端。
3. 打开浏览器。
4. 调用一个 `/api` 健康或 docs 地址。
5. 确认浏览器 Network 面板有真实 `/api` 请求。

## 五、验收标准

P0 验收必须全部满足：

1. `frontend/backup` 不存在或不被 TypeScript 扫描。
2. `npm run lint` 通过。
3. `.venv\Scripts\python.exe -c "from backend.main import app; print('ok', len(app.routes))"` 成功。
4. 后端可以通过标准命令启动。
5. 前端 dev server 可以启动。
6. 浏览器中访问前端页面时，Network 面板中的 `/api/...` 请求应同源发往 Vite dev server，并由 Vite proxy 成功转发到 FastAPI；后端无须配置 CORS。
7. `frontend/src/lib/api.ts` 已具备真实 HTTP client 基础封装。
8. Mock 开关如果存在，默认值不是 Mock。

## 六、交付物

- 修复后的前端 TypeScript。
- Vite proxy 配置。
- HTTP client 基础封装。
- 本地启动说明。

## 七、风险与处理

| 风险 | 处理 |
| --- | --- |
| 前端类型错误牵扯过多 | 只修编译阻断，不做 UI 重构 |
| 误引入 CORS 或绕过 Vite proxy 造成环境不一致 | 本地开发仅使用 Vite proxy；后端不引入 CORSMiddleware；前端禁止直接硬编码后端端口 |
| Mock 被继续误用 | 通过 env 显式控制，默认真实 API |

## 八、进入 P1 的条件

P0 通过后，进入 P1 前需确认：

- 前端能够向后端发起真实请求。
- 后端服务可稳定启动。
- 前端类型检查干净。
- 团队已确认项目聚合读取接口的字段风格：后端直接返回前端 CamelCase IR，或返回 snake_case 后由前端 mapper 转换。
