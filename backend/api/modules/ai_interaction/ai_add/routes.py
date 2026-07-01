from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_ai_add_session, require_owned_generative_draft
from backend.database.model import UserModel, AIAddSessionModel, GenerativeDraftModel
from backend.api.modules.ai_interaction.ai_add.schemas import (
    AIAddSessionCreateRequest,
    AIAddSessionResponse,
    AIAddSessionMessagesResponse,
    AIAddMessageItem,
    AIAddMessageRequest,
    AIAddMessageResponse,
    AIAddGenerateDraftResponse,
    AIAddConfirmDraftResponse,
    AIAddDiscardDraftResponse,
    AIAddSessionErrorResponse,
)
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService
from backend.database.database import get_session
from backend.api.dependencies.llm import get_llm_context

router = APIRouter(
    prefix="/api/ai_add_sessions",
    tags=["ai_add_session"],
)

AI_ADD_SESSION_ERRORS = {
    "unsupported_target_type",
    "project_not_found",
    "session_not_found",
    "session_not_active",
    "session_invalid_status",
    "session_not_ready",
    "anchor_reference_not_found",
    "draft_not_found",
    "generator_output_parse_failed",
    "empty_actor_name",
    "duplicate_actor_name",
    "empty_feature_name",
    "invalid_feature_kind",
    "invalid_actor_reference",
    "empty_flow_name",
    "empty_flow_feature_ids",
    "invalid_feature_reference",
    "empty_business_object_name",
    "duplicate_business_object_name",
    "duplicate_feature_name_under_same_parent",
    "duplicate_flow_name",
    "empty_summary_payload",
    "invalid_draft_payload",
    "target_not_found",
    "field_not_editable",
    "edit_diff_empty",
    "edit_diff_validation_failed",
    "invalid_edit_anchor",
}

_service: AIAddSessionService | None = None


def _get_service() -> AIAddSessionService:
    global _service
    if _service is None:
        _service = AIAddSessionService()
    return _service


def _is_known_error(error_str: str) -> bool:
    """Check if an error string matches a known error code (exact or prefix)."""
    if error_str in AI_ADD_SESSION_ERRORS:
        return True
    # Many error codes carry a colon-suffixed detail, e.g. "invalid_actor_reference: 999"
    base = error_str.split(":")[0].strip()
    return base in AI_ADD_SESSION_ERRORS


@router.post("", response_model=AIAddSessionResponse)
async def create_ai_add_session(
    request: AIAddSessionCreateRequest,
    user: UserModel = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    """Create a new AI add session for a given target_type (actor, feature_leaf, etc.)."""
    try:
        service = _get_service()
        return await service.create_session(
            project_id=request.project_id,
            target_type=request.target_type,
            anchor=request.anchor,
            owner_user_id=user.id,
            session=db_session,
        )
    except ValueError as error:
        error_str = str(error)
        if error_str == "project_not_found" or error_str.startswith("project_not_found:"):
            raise HTTPException(status_code=404, detail="project_not_found")
        if error_str == "insufficient_project_role":
            raise HTTPException(status_code=403, detail="insufficient_project_role")
        if _is_known_error(error_str):
            raise HTTPException(status_code=400, detail=error_str)
        raise


@router.get("/{session_id}", response_model=AIAddSessionResponse)
async def get_ai_add_session(
    ai_session: AIAddSessionModel = Depends(require_owned_ai_add_session),
    db_session: AsyncSession = Depends(get_session),
):
    """Get session details by ID."""
    try:
        service = _get_service()
        return await service.get_session(
            session_id=ai_session.id,
            session=db_session,
        )
    except ValueError as error:
        if str(error) == "session_not_found":
            raise HTTPException(status_code=404, detail="session_not_found")
        raise


@router.get("/{session_id}/messages", response_model=AIAddSessionMessagesResponse)
async def get_ai_add_session_messages(
    ai_session: AIAddSessionModel = Depends(require_owned_ai_add_session),
    db_session: AsyncSession = Depends(get_session),
):
    """Get all messages for a session."""
    try:
        service = _get_service()
        messages = await service.get_session_messages(
            session_id=ai_session.id,
            session=db_session,
        )
        return {"session_id": ai_session.id, "messages": messages}
    except ValueError as error:
        if str(error) == "session_not_found":
            raise HTTPException(status_code=404, detail="session_not_found")
        raise


@router.post("/{session_id}/messages", response_model=AIAddMessageResponse)
async def send_ai_add_message(
    request: AIAddMessageRequest,
    ai_session: AIAddSessionModel = Depends(require_owned_ai_add_session),
    db_session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    """Send a user message in an AI add session and get the assistant's reply."""
    try:
        service = _get_service()
        return await service.append_user_message(
            session_id=ai_session.id,
            content=request.content,
            db_session=db_session,
        )
    except ValueError as error:
        error_str = str(error)
        if error_str == "session_not_found":
            raise HTTPException(status_code=404, detail="session_not_found")
        if _is_known_error(error_str):
            raise HTTPException(status_code=400, detail=error_str)
        raise


@router.post("/{session_id}/generate_draft", response_model=AIAddGenerateDraftResponse)
async def generate_ai_add_draft(
    user: UserModel = Depends(get_current_user),
    ai_session: AIAddSessionModel = Depends(require_owned_ai_add_session),
    db_session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    """Generate a draft from the interview summary (when session is ready)."""
    try:
        service = _get_service()
        return await service.generate_draft(
            session_id=ai_session.id,
            owner_user_id=user.id,
            db_session=db_session,
        )
    except ValueError as error:
        error_str = str(error)
        if error_str.startswith("session_not_found"):
            raise HTTPException(status_code=404, detail=error_str)
        if _is_known_error(error_str):
            raise HTTPException(status_code=400, detail=error_str)
        raise


# NOTE: confirm and discard use the draft store routes prefix for consistency
# with existing generation draft patterns.

draft_router = APIRouter(
    prefix="/api/ai_object_generation_drafts",
    tags=["ai_add_session"],
)


@draft_router.post("/{draft_id}/confirm", response_model=AIAddConfirmDraftResponse)
async def confirm_ai_add_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    db_session: AsyncSession = Depends(get_session),
):
    """Confirm and persist a generated draft."""
    try:
        service = _get_service()
        return await service.confirm_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            db_session=db_session,
        )
    except ValueError as error:
        error_str = str(error)
        if error_str == "draft_not_found":
            raise HTTPException(status_code=404, detail="draft_not_found")
        if _is_known_error(error_str):
            raise HTTPException(status_code=400, detail=error_str)
        raise


@draft_router.delete("/{draft_id}", response_model=AIAddDiscardDraftResponse)
async def discard_ai_add_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    db_session: AsyncSession = Depends(get_session),
):
    """Discard a draft without persisting it."""
    try:
        service = _get_service()
        return await service.discard_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            db_session=db_session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(status_code=404, detail="draft_not_found")
        raise
