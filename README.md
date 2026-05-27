# RequirementSpace Workbench - 需求空间数字化协作工作台

这是一个基于 FastAPI (后端 SQLite 驱动) 和 React + Vite (前端) 的需求空间协作建模工作台。系统支持对产品需求进行角色 (Who)、功能能力树 (What)、业务步骤流与数据实体 (How) 以及交付范围决策 (Scope) 的高一致性建模。

---

## 🛠️ 本地开发启动指南

### 1. 后端服务启动

我们使用 Python 虚拟环境运行 FastAPI 服务，默认绑定端口为 `8000`。

```powershell
# 1. 激活虚拟环境并启动 Uvicorn 开发服务器
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

* 后端健康检查地址: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
* 后端 API 交互式文档: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. 前端服务启动

前端是一个 Vite 开发服务器，默认绑定端口为 `3000`。

```powershell
# 进入前端文件夹
cd frontend

# 安装依赖（若有更新）
npm install

# 启动 Vite 开发服务器
npm run dev
```

* 前端本地访问地址: [http://localhost:3000](http://localhost:3000)

---

## 🌐 跨端请求路由设计 (Vite Proxy 方案)

为规避本地开发环境的跨域 CORS 阻碍并维持环境一致性，项目统一采用 **Vite proxy** 方案：

1. **同源请求**: 前端所有请求均使用相对路径 `/api/...` 发起，无需在代码中硬编码任何后端端口或 IP。
2. **反向代理**: Vite dev server (端口 `3000`) 会自动拦截 `/api` 前缀的请求，并反向代理转发至本地 FastAPI 后端 (端口 `8000`)。
3. **安全整洁**: 后端无需配置并加载任何 `CORSMiddleware`，保证生产环境接口的安全边界与整洁性。

> ⚠️ **生产部署提示**: 本地开发期反向代理由 Vite dev server 驱动。在生产或部署环境，应由 Nginx、API Gateway、CDN 同源部署或正式网关提供等价的 `/api` 转发路由。

---

## 🔍 P0 联调前置与工程卫生检查清单

在正式进行前后端业务接口联调前，请确保执行以下前置检查：

### 📋 检查步骤

1. **编译及类型检查**:
   在 `frontend` 目录下运行 TypeScript 校验，确保无类型错误：
   ```powershell
   npm run lint
   ```
   *(期望输出: 编译成功，无任何 Error)*

2. **后端可用性检查**:
   运行以下命令确保后端能成功加载并注册了所有 82 个核心路由：
   ```powershell
   .venv\Scripts\python.exe -c "from backend.main import app; print('ok', len(app.routes))"
   ```
   *(期望输出: `ok 82`)*

3. **Vite Proxy 转发及连贯性测试**:
   * 依次启动后端服务和前端开发服务器。
   * 打开浏览器控制台 (F12) 并切换到 **Network (网络)** 面板。
   * 刷新前端页面，访问或触发一次请求（或直接在控制台调用 `fetch('/api/health')`）。
   * 确认该请求同源发往 Vite 开发服务器 (`http://localhost:3000/api/health`) 并且状态码为 `200 OK`，返回值如下：
     ```json
     {
       "status": "ok",
       "message": "Requirement Space Workbench API is running"
     }
     ```
   * 确认后端终端没有输出 CORS 警告，网络面板中无跨域拦截现象。
