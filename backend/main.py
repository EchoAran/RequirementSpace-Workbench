from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

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
    await init_db()
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

