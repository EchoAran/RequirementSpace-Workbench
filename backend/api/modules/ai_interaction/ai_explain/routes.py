"""API routes for AI-powered Q&A explanation."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import UserModel
from backend.api.modules.ai_interaction.ai_explain.schemas import (
    ExplainRequest,
    ExplainResponse,
    ExplainContextSummary,
)
from backend.api.modules.ai_interaction.ai_explain.application.explain import AIExplainService
from backend.database.database import get_session
from backend.api.dependencies.llm import get_llm_context

router = APIRouter(
    prefix="/api/ai",
    tags=["ai_explain"],
)

EXPLAIN_ERRORS = {
    "empty_question",
    "project_not_found",
    "invalid_node_scope",
    "unsupported_scope_kind",
}

_service: AIExplainService | None = None


def _get_service() -> AIExplainService:
    global _service
    if _service is None:
        _service = AIExplainService()
    return _service


@router.post("/explain", response_model=ExplainResponse)
async def explain(
    request: ExplainRequest,
    user: UserModel = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    """Answer a question about the project within the given scope."""
    owned_project = await require_owned_project(request.project_id, user, db_session)
    try:
        service = _get_service()
        return await service.explain(
            project_id=owned_project.id,
            scope=request.scope.model_dump(),
            question=request.question,
            db_session=db_session,
        )
    except ValueError as error:
        error_str = str(error)
        if error_str == "project_not_found":
            raise HTTPException(status_code=404, detail=error_str)
        if error_str == "target_not_found":
            raise HTTPException(status_code=404, detail=error_str)
        if error_str in EXPLAIN_ERRORS or error_str.startswith("unsupported_target_type"):
            raise HTTPException(status_code=400, detail=error_str)
        logger.exception("Unexpected ValueError in explain: %s", error_str)
        raise HTTPException(status_code=500, detail="internal_error")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in explain")
        raise HTTPException(status_code=500, detail="internal_error")
