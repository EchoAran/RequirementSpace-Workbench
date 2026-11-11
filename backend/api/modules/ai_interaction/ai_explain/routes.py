"""API routes for AI-powered Q&A explanation."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import llm_context_manager
from backend.api.modules.ai_interaction.ai_explain.application.explain import AIExplainService
from backend.api.modules.ai_interaction.ai_explain.schemas import (
    ExplainRequest,
    ExplainResponse,
)
from backend.database.database import get_session
from backend.database.model import UserModel

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
    branch: str | None = Query(None),
):
    """Answer a question about the project within the given scope."""
    from backend.api.dependencies.project_access import require_project_member
    owned_project = await require_project_member(request.project_id, user, db_session)
    async with llm_context_manager(user, db_session, project_id=owned_project.id):
        try:
            service = _get_service()
            return await service.explain(
                project_id=owned_project.id,
                scope=request.scope.model_dump(),
                question=request.question,
                db_session=db_session,
                branch_name=branch,
            )
        except ValueError as error:
            error_str = str(error)
            if error_str == "project_not_found":
                raise HTTPException(status_code=404, detail=error_str)
            if error_str == "target_not_found":
                raise HTTPException(status_code=404, detail=error_str)
            if error_str in EXPLAIN_ERRORS or error_str.startswith("unsupported_target_type"):
                raise HTTPException(status_code=400, detail=error_str)
            from backend.api.modules.version_control.public import map_branch_error
            if "branch" in error_str.lower() or "workspace" in error_str.lower():
                raise map_branch_error(error)
            logger.exception("Unexpected ValueError in explain: %s", error_str)
            raise HTTPException(status_code=500, detail="internal_error")
        except HTTPException:
            raise
        except Exception:
            logger.exception("Unexpected error in explain")
            raise HTTPException(status_code=500, detail="internal_error")
