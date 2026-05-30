"""API routes for AI-powered Q&A explanation."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.api.schemas.ai_explain_schema import (
    ExplainRequest,
    ExplainResponse,
    ExplainContextSummary,
)
from backend.api.services.ai_explain_service import AIExplainService
from backend.database.database import get_session

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
    db_session: AsyncSession = Depends(get_session),
):
    """Answer a question about the project within the given scope."""
    try:
        service = _get_service()
        return await service.explain(
            project_id=request.project_id,
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
    except Exception:
        logger.exception("Unexpected error in explain")
        raise HTTPException(status_code=500, detail="internal_error")
