from contextlib import asynccontextmanager
import logging
import os
import socket

# Set a global default socket timeout of 5.0 seconds to prevent any connection or SSL handshake from hanging.
socket.setdefaulttimeout(5.0)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    # 自动剔除末尾的斜杠，防止由于格式不一致导致浏览器 CORS 拦截
    origins = [origin.strip().rstrip("/") for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    origins = ["*"]

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

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("[GLOBAL EXCEPTION] Unhandled error caught by global handler:")
    
    # Get request origin to echo it back in CORS headers
    origin = request.headers.get("origin", "*")
    if origins and "*" not in origins and origin not in origins:
        origin = origins[0] if origins else "*"
        
    response = JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "message": "An unhandled exception occurred in the backend."
        }
    )
    
    # Force inject CORS headers to bypass browser blocks on 500 errors
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true" if allow_credentials else "false"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


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
app.include_router(issue_router)
app.include_router(issue_repair_draft_router)
app.include_router(quality_metrics_router)
app.include_router(next_suggestion_router)
app.include_router(perception_slot_filling_router)
app.include_router(actor_router)
app.include_router(feature_router)
app.include_router(scenario_router)
app.include_router(business_object_router)
app.include_router(flow_router)
app.include_router(scope_router)
app.include_router(project_scope_router)
app.include_router(choice_router)
app.include_router(project_requirements_router)
app.include_router(project_router)
app.include_router(prototype_generation_router)
app.include_router(preview_shadow_router)
app.include_router(ai_add_session_router)
app.include_router(ai_object_generation_draft_router)
app.include_router(ai_explain_router)
app.include_router(project_interview_router)
app.include_router(node_status_router)

