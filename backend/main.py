from contextlib import asynccontextmanager
import logging
import os
import socket

# Set a global default socket timeout of 5.0 seconds to prevent any connection or SSL handshake from hanging.
socket.setdefaulttimeout(5.0)

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.api.dependencies.ownership import require_owned_project

from backend.api.routes.project_creation_routes import (
    router as project_creation_router,
)
from backend.api.routes.project_creation_choice_routes import (
    router as project_creation_choice_router,
)
from backend.api.routes.blank_project_routes import (
    router as blank_project_router,
)
from backend.api.routes.actor_generation_routes import (
    router as actor_generation_router,
)
from backend.api.routes.feature_generation_routes import (
    router as feature_generation_router,
)
from backend.api.routes.flow_generation_routes import (
    router as flow_generation_router,
)
from backend.api.routes.scenario_generation_routes import (
    router as scenario_generation_router,
)
from backend.api.routes.acceptance_criteria_generation_routes import (
    router as acceptance_criteria_generation_router,
)
from backend.api.routes.scope_generation_routes import (
    router as scope_generation_router,
)
from backend.api.routes.issue_routes import (
    router as issue_router,
)
from backend.api.routes.issue_repair_draft_routes import (
    router as issue_repair_draft_router,
)
from backend.api.routes.quality_metrics_routes import (
    router as quality_metrics_router,
)
from backend.api.routes.next_suggestion_routes import (
    router as next_suggestion_router,
)
from backend.api.routes.perception_slot_filling_routes import (
    router as perception_slot_filling_router,
)
from backend.api.routes.actor_routes import (
    router as actor_router,
)
from backend.api.routes.feature_routes import (
    router as feature_router,
)
from backend.api.routes.scenario_routes import (
    router as scenario_router,
)
from backend.api.routes.business_object_routes import (
    router as business_object_router,
)
from backend.api.routes.flow_routes import (
    router as flow_router,
)
from backend.api.routes.scope_routes import (
    router as scope_router,
)
from backend.api.routes.choice_routes import (
    router as choice_router,
)
from backend.api.routes.project_requirements_routes import (
    router as project_requirements_router,
)
from backend.api.routes.project_routes import (
    router as project_router,
)
from backend.api.routes.prototype_generation_routes import (
    router as prototype_generation_router,
)
from backend.api.routes.project_scope_routes import (
    router as project_scope_router,
)
from backend.api.routes.preview_shadow_routes import (
    router as preview_shadow_router,
)
from backend.api.routes.ai_add_session_routes import (
    router as ai_add_session_router,
    draft_router as ai_object_generation_draft_router,
)
from backend.api.routes.ai_explain_routes import (
    router as ai_explain_router,
)
from backend.api.routes.project_interview_routes import (
    router as project_interview_router,
)
from backend.api.routes.node_status_routes import (
    router as node_status_router,
)
from backend.api.routes.auth_routes import (
    router as auth_router,
)
from backend.api.routes.account_routes import (
    router as account_router,
)

from backend.database.database import init_db
from backend.api.services import service_registry


logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(fast_api: FastAPI):
    try:
        logger.info("Starting database initialization...")
        await init_db()
        logger.info("Database initialization completed successfully.")
    except Exception as e:
        logger.exception("CRITICAL: Database initialization failed during lifespan startup!")
        raise e

    logger.info(
        "RequirementSpace generation backend: %s; scope service: %s.%s",
        service_registry.generation_backend,
        type(service_registry.scope_generation_service).__module__,
        type(service_registry.scope_generation_service).__name__,
    )
    yield
    # 【应用关闭时执行】（可选）
    # await close_db()

app = FastAPI(
    title="Requirement Space Workbench API",
    lifespan=lifespan  # 绑定生命周期
)

# CORS 跨域配置
from backend.core.config import ENV

allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "").strip()
if allowed_origins_str:
    # 自动剔除末尾的斜杠，防止由于格式不一致导致浏览器 CORS 拦截
    origins = [origin.strip().rstrip("/") for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    if ENV == "production":
        origins = []
    else:
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

if ENV == "production":
    if not origins or "*" in origins:
        raise ValueError(
            "CRITICAL CONFIG ERROR: ALLOWED_ORIGINS must be configured explicitly in production "
            "and cannot contain '*' when cookies are used for credentials."
        )
    allow_credentials = True
else:
    allow_credentials = True
    if "*" in origins:
        allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request
from fastapi.responses import JSONResponse
import traceback
from backend.core.llm_context import is_web_request_ctx

@app.middleware("http")
async def web_request_context_middleware(request: Request, call_next):
    token = is_web_request_ctx.set(True)
    try:
        return await call_next(request)
    finally:
        is_web_request_ctx.reset(token)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import uuid
    import traceback
    from backend.core.security import sanitize_message
    
    request_id = str(uuid.uuid4())
    
    # Format raw traceback into string
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    # Sanitize traceback to prevent secrets from entering logs
    sanitized_tb = sanitize_message(tb_str)
    
    logger.error(
        f"[GLOBAL EXCEPTION] Request ID: {request_id}. Unhandled error ({type(exc).__name__}) caught by global handler:\n{sanitized_tb}"
    )

    # Get request origin to echo it back in CORS headers
    origin = request.headers.get("origin", "*")
    if origins and "*" not in origins and origin not in origins:
        origin = origins[0] if origins else "*"

    response = JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "request_id": request_id,
            "message": "An unhandled exception occurred in the backend."
        }
    )

    # Force inject CORS headers to bypass browser blocks on 500 errors
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true" if allow_credentials else "false"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    import uuid
    from backend.core.security import sanitize_message

    if exc.status_code >= 500:
        request_id = str(uuid.uuid4())
        
        # Log the sanitized detail server-side for diagnostics
        logger.error(
            f"[GLOBAL EXCEPTION] Request ID: {request_id}. "
            f"HTTP {exc.status_code} detail: {sanitize_message(str(exc.detail))}"
        )
        
        # Get request origin to echo it back in CORS headers
        origin = request.headers.get("origin", "*")
        if origins and "*" not in origins and origin not in origins:
            origin = origins[0] if origins else "*"

        # Return a fixed public error response
        response = JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": "Internal Server Error",
                "request_id": request_id,
                "message": "An unhandled exception occurred in the backend."
            }
        )
        
        # Force inject CORS headers to bypass browser blocks on 500 errors
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true" if allow_credentials else "false"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        
        return response
        
    # For < 500 errors, preserve original stable detail and headers
    headers = dict(exc.headers) if exc.headers else {}
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={"detail": exc.detail}
    )



from backend.api.dependencies.auth import get_current_user, require_admin
from backend.api.dependencies.llm import get_llm_context
from backend.core.llm_context import LLMRequestContext

@app.get("/api/llm_test")
async def llm_test(
    user=Depends(require_admin),
    llm_ctx: LLMRequestContext = Depends(get_llm_context),
):
    import socket
    import httpx
    import traceback
    from urllib.parse import urlparse

    # Use request-scoped credentials resolved by get_llm_context
    api_url = llm_ctx.api_url.rstrip("/")
    api_key = llm_ctx.api_key
    model = llm_ctx.model_name

    diagnostic_info = {}

    # 1. Config source indicator (no secrets exposed)
    diagnostic_info["config"] = {
        "api_url_configured": bool(api_url),
        "api_key_configured": bool(api_key),
        "model_configured": bool(model),
    }

    # 2. DNS Resolution Test
    try:
        domain = urlparse(api_url).netloc
        if ":" in domain:
            domain = domain.split(":", 1)[0]
        diagnostic_info["dns_host"] = domain
        ips = socket.gethostbyname_ex(domain)
        diagnostic_info["dns_ips"] = ips[2]
        diagnostic_info["dns_status"] = "success"
    except Exception as e:
        diagnostic_info["dns_status"] = "failed"
        diagnostic_info["dns_error"] = str(e)

    # 3. HTTP connection test to main URL
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            res = await client.get(api_url)
        diagnostic_info["root_conn_status"] = "success"
        diagnostic_info["root_conn_code"] = res.status_code
    except Exception as e:
        diagnostic_info["root_conn_status"] = "failed"
        diagnostic_info["root_conn_error"] = f"{type(e).__name__}"

    # 4. Chat Completions Test
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        req_data = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": 0.0,
        }
        completions_url = f"{api_url}/v1/chat/completions"

        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            res = await client.post(completions_url, json=req_data, headers=headers)

        diagnostic_info["chat_status"] = "success"
        diagnostic_info["chat_code"] = res.status_code
    except Exception as e:
        diagnostic_info["chat_status"] = "failed"
        diagnostic_info["chat_error"] = f"{type(e).__name__}"

    return diagnostic_info


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Requirement Space Workbench API is running"}


# 注册路由
app.include_router(project_creation_router)
app.include_router(project_creation_choice_router)
app.include_router(blank_project_router)
app.include_router(actor_generation_router)
app.include_router(feature_generation_router)
app.include_router(flow_generation_router)
app.include_router(scenario_generation_router)
app.include_router(acceptance_criteria_generation_router)
app.include_router(scope_generation_router)
app.include_router(issue_router, dependencies=[Depends(require_owned_project)])
app.include_router(issue_repair_draft_router, dependencies=[Depends(require_owned_project)])
app.include_router(quality_metrics_router, dependencies=[Depends(require_owned_project)])
app.include_router(next_suggestion_router, dependencies=[Depends(require_owned_project)])
app.include_router(perception_slot_filling_router)
app.include_router(actor_router, dependencies=[Depends(require_owned_project)])
app.include_router(feature_router, dependencies=[Depends(require_owned_project)])
app.include_router(scenario_router, dependencies=[Depends(require_owned_project)])
app.include_router(business_object_router, dependencies=[Depends(require_owned_project)])
app.include_router(flow_router, dependencies=[Depends(require_owned_project)])
app.include_router(scope_router, dependencies=[Depends(require_owned_project)])
app.include_router(project_scope_router, dependencies=[Depends(require_owned_project)])
app.include_router(choice_router)
app.include_router(project_requirements_router, dependencies=[Depends(require_owned_project)])
app.include_router(project_router)
app.include_router(prototype_generation_router, dependencies=[Depends(require_owned_project)])
app.include_router(preview_shadow_router, dependencies=[Depends(require_owned_project)])
app.include_router(ai_add_session_router)
app.include_router(ai_object_generation_draft_router)
app.include_router(ai_explain_router)
app.include_router(project_interview_router)
app.include_router(node_status_router, dependencies=[Depends(require_owned_project)])
app.include_router(auth_router)
app.include_router(account_router)
