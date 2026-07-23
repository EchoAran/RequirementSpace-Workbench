from contextlib import asynccontextmanager
import logging
import os
import socket

# Set a global default socket timeout of 5.0 seconds to prevent any connection or SSL handshake from hanging.
socket.setdefaulttimeout(5.0)

from backend.core.logging import (
    clear_log_context,
    configure_logging,
    get_logger,
    log_event,
    sanitize_message,
    set_log_context,
)
from backend.core.logging.events import (
    GLOBAL_EXCEPTION_CAUGHT,
    HTTP_EXCEPTION_CAUGHT,
    HTTP_REQUEST_COMPLETED,
)

configure_logging()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.api.dependencies.ownership import require_owned_project
from backend.api.dependencies.project_access import require_project_member

from backend.api.modules.project_lifecycle.routes.creation import (
    router as project_creation_router,
)
from backend.api.modules.project_lifecycle.routes.creation_choice import (
    router as project_creation_choice_router,
)
from backend.api.modules.project_lifecycle.routes.blank import (
    router as blank_project_router,
)
from backend.api.modules.requirements_core.actor.routes import (
    router as actor_router,
    generation_router as actor_generation_router,
)
from backend.api.modules.requirements_core.feature.routes import (
    router as feature_router,
    generation_router as feature_generation_router,
)
from backend.api.modules.requirements_core.scenario.routes import (
    router as scenario_router,
    generation_router as scenario_generation_router,
    ac_generation_router as acceptance_criteria_generation_router,
)
from backend.api.modules.requirements_core.flow.routes import (
    router as flow_router,
    generation_router as flow_generation_router,
)
from backend.api.modules.requirements_core.scope.routes import (
    router as scope_router,
    project_scope_router as project_scope_router,
    generation_router as scope_generation_router,
)
from backend.api.modules.requirements_core.business_object.routes import (
    router as business_object_router,
)
from backend.api.modules.requirements_core.node_status.routes import (
    router as node_status_router,
)
from backend.api.modules.diagnosis_quality.finding.routes import (
    router as finding_router,
)
from backend.api.modules.diagnosis_quality.issue_compat.routes import (
    router as issue_router,
)
from backend.api.modules.diagnosis_quality.issue_repair.routes import (
    router as issue_repair_draft_router,
)
from backend.api.modules.diagnosis_quality.quality_metrics.routes import (
    router as quality_metrics_router,
)
from backend.api.modules.diagnosis_quality.next_suggestion.routes import (
    router as next_suggestion_router,
)
from backend.api.modules.diagnosis_quality.perception.routes import (
    router as perception_slot_filling_router,
)
from backend.api.modules.decision_workflow.choice_group.routes import (
    router as choice_router,
)
from backend.api.modules.project_lifecycle.routes.requirements import (
    router as project_requirements_router,
)
from backend.api.modules.project_lifecycle.routes.project import (
    router as project_router,
)
from backend.api.modules.project_lifecycle.routes.members import (
    router as project_members_router,
)
from backend.api.modules.project_lifecycle.routes.llm_config import (
    router as project_llm_config_router,
)
from backend.api.modules.project_configuration.routes import (
    router as project_configuration_router,
)
from backend.api.modules.preview_convergence.routes.prototype import (
    router as prototype_generation_router,
)
from backend.api.modules.preview_convergence.routes.shadow_preview import (
    router as preview_shadow_router,
)
from backend.api.modules.ai_interaction.ai_add.routes import (
    router as ai_add_session_router,
    draft_router as ai_object_generation_draft_router,
)
from backend.api.modules.ai_interaction.ai_explain.routes import (
    router as ai_explain_router,
)
from backend.api.modules.project_lifecycle.routes.interview import (
    router as project_interview_router,
)
from backend.api.modules.collaboration.routes.tasks import (
    router as collaboration_tasks_router,
    summary_router as collaboration_summary_router,
    me_router as user_tasks_router,
)
from backend.api.modules.collaboration.routes.notifications import (
    router as notifications_router,
)
from backend.api.modules.auth_account.routes.auth import (
    router as auth_router,
)
from backend.api.modules.auth_account.routes.preferences import (
    router as preferences_router,
)
from backend.api.modules.auth_account.routes.llm_config import (
    router as account_router,
)
from backend.api.modules.project_knowledge.routes import (
    router as project_knowledge_router,
    config_router as project_knowledge_config_router,
)

from backend.database.database import init_db


from backend.api.modules.requirements_core.ports import set_notifier

class PerceptionStaleNotifier:
    async def mark_stale(
        self,
        project_id: int,
        stages: set[str],
        session,
        perception_kinds: set[str] | None = None,
        clear_active_slot: bool = True,
    ) -> None:
        from backend.api.modules.diagnosis_quality.public import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
            project_id=project_id,
            stages=stages,
            session=session,
            perception_kinds=perception_kinds,
            clear_active_slot=clear_active_slot,
        )


logger = get_logger("backend.main")


class ConcreteGenerationDraftCreator:
    async def create_scenario_draft(
        self,
        project_id: int,
        feature_id: int,
        actor_id: int,
        session,
    ) -> dict:
        from backend.api.modules.requirements_core.public import ScenarioGenerationService
        return await ScenarioGenerationService().create_pair_draft(
            project_id=project_id,
            feature_id=feature_id,
            actor_id=actor_id,
            session=session,
        )

    async def create_ac_draft(
        self,
        project_id: int,
        scenario_id: int,
        session,
    ) -> dict:
        from backend.api.modules.requirements_core.public import AcceptanceCriteriaGenerationService
        return await AcceptanceCriteriaGenerationService().create_single_draft(
            project_id=project_id,
            scenario_id=scenario_id,
            session=session,
        )

    async def create_scope_draft(
        self,
        project_id: int,
        session,
    ) -> dict:
        from backend.api.modules.requirements_core.public import ScopeGenerationService
        return await ScopeGenerationService().create_draft(
            project_id=project_id,
            session=session,
        )


@asynccontextmanager
async def lifespan(fast_api: FastAPI):
    from backend.api.bootstrap import bootstrap_services
    registry = bootstrap_services()
    try:
        logger.info("Starting database initialization...")
        await init_db()
        logger.info("Database initialization completed successfully.")
    except Exception as e:
        logger.exception("CRITICAL: Database initialization failed during lifespan startup!")
        raise e

    set_notifier(PerceptionStaleNotifier())

    from backend.api.modules.decision_workflow.ports.ports import ChoiceAdapterRegistry
    from backend.api.bootstrap import register_choice_adapters
    register_choice_adapters(ChoiceAdapterRegistry())

    # Blocker 2: Register ports
    from backend.api.modules.decision_workflow.public import GenerationChoiceService
    from backend.core.issue_resolution.ports import (
        set_choice_group_creator,
        set_choice_group_settings,
        set_generation_draft_creator,
    )
    choice_service = GenerationChoiceService()
    set_choice_group_creator(choice_service)
    set_choice_group_settings(choice_service.settings)
    set_generation_draft_creator(ConcreteGenerationDraftCreator())

    logger.info(
        "RequirementSpace generation backend: %s; scope service: %s.%s",
        registry.generation_backend,
        type(registry.scope_generation_service).__module__,
        type(registry.scope_generation_service).__name__,
    )
    yield
    # 【应用关闭时执行】（可选）
    # await close_db()

from backend.api.dependencies.actor_context import get_actor_context

app = FastAPI(
    title="Requirement Space Workbench API",
    lifespan=lifespan,  # 绑定生命周期
    dependencies=[Depends(get_actor_context)]
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
from backend.core.llm_locale_validation import LLMContentLocaleMismatchError


def _request_log_path(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return route_path
    return request.url.path


@app.middleware("http")
async def web_request_context_middleware(request: Request, call_next):
    import uuid
    import time
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    set_log_context(request_id=request_id)
    token = is_web_request_ctx.set(True)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log_event(
            logger,
            logging.INFO,
            "request",
            HTTP_REQUEST_COMPLETED,
            "HTTP request completed",
            method=request.method,
            path=_request_log_path(request),
            status_code=response.status_code,
            duration_ms=int((time.perf_counter() - started) * 1000),
            client_host=request.client.host if request.client else None,
        )
        return response
    finally:
        is_web_request_ctx.reset(token)
        clear_log_context()

@app.exception_handler(LLMContentLocaleMismatchError)
async def llm_content_locale_mismatch_handler(
    request: Request,
    exc: LLMContentLocaleMismatchError,
):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import uuid
    
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    set_log_context(request_id=request_id)
    
    # Format raw traceback into string
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    # Sanitize traceback to prevent secrets from entering logs
    sanitized_tb = sanitize_message(tb_str)
    
    log_event(
        logger,
        logging.ERROR,
        "request",
        GLOBAL_EXCEPTION_CAUGHT,
        "Unhandled exception caught by global handler",
        method=request.method,
        path=_request_log_path(request),
        status_code=500,
        error_type=type(exc).__name__,
        sanitized_traceback=sanitized_tb,
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
    response.headers["X-Request-ID"] = request_id
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true" if allow_credentials else "false"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    import uuid

    if exc.status_code >= 500:
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        set_log_context(request_id=request_id)
        
        # Log the sanitized detail server-side for diagnostics
        log_event(
            logger,
            logging.ERROR,
            "request",
            HTTP_EXCEPTION_CAUGHT,
            "HTTP exception caught",
            method=request.method,
            path=_request_log_path(request),
            status_code=exc.status_code,
            error_type=type(exc).__name__,
            error_detail=sanitize_message(str(exc.detail)),
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
        response.headers["X-Request-ID"] = request_id
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
app.include_router(finding_router, dependencies=[Depends(require_project_member)])
app.include_router(issue_router, dependencies=[Depends(require_project_member)])
app.include_router(issue_repair_draft_router, dependencies=[Depends(require_project_member)])
app.include_router(quality_metrics_router, dependencies=[Depends(require_project_member)])
app.include_router(next_suggestion_router, dependencies=[Depends(require_project_member)])
app.include_router(perception_slot_filling_router)
app.include_router(actor_router, dependencies=[Depends(require_project_member)])
app.include_router(feature_router, dependencies=[Depends(require_project_member)])
app.include_router(scenario_router, dependencies=[Depends(require_project_member)])
app.include_router(business_object_router, dependencies=[Depends(require_project_member)])
app.include_router(flow_router, dependencies=[Depends(require_project_member)])
app.include_router(scope_router, dependencies=[Depends(require_project_member)])
app.include_router(project_scope_router, dependencies=[Depends(require_project_member)])
app.include_router(choice_router)
app.include_router(project_requirements_router, dependencies=[Depends(require_project_member)])
app.include_router(project_router)
app.include_router(project_members_router)
app.include_router(project_llm_config_router)
app.include_router(project_configuration_router)
app.include_router(prototype_generation_router, dependencies=[Depends(require_project_member)])
app.include_router(preview_shadow_router, dependencies=[Depends(require_project_member)])
app.include_router(ai_add_session_router)
app.include_router(ai_object_generation_draft_router)
app.include_router(ai_explain_router)
app.include_router(project_interview_router)
app.include_router(node_status_router, dependencies=[Depends(require_owned_project)])
app.include_router(collaboration_summary_router, dependencies=[Depends(require_project_member)])
app.include_router(collaboration_tasks_router, dependencies=[Depends(require_project_member)])
app.include_router(user_tasks_router)
app.include_router(notifications_router)
app.include_router(auth_router)
app.include_router(preferences_router)
app.include_router(account_router)
app.include_router(project_knowledge_config_router)
app.include_router(project_knowledge_router)
