"""API routes for project interview (chat-based requirements gathering)."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.modules.project_lifecycle.application.interview_service import ProjectInterviewService
from backend.database.database import get_session
from backend.api.dependencies.llm import get_llm_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/project_interview",
    tags=["project_interview"],
)

_service: ProjectInterviewService | None = None


def _get_service() -> ProjectInterviewService:
    global _service
    if _service is None:
        _service = ProjectInterviewService()
    return _service


class InterviewChatRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)


class InterviewChatResponse(BaseModel):
    reply: str
    is_ready: bool = False
    summary: str = ""


class InterviewCompleteRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    user_requirements: str = Field(..., min_length=1)


class InterviewCompleteResponse(BaseModel):
    draft_id: str
    project_preview: dict = Field(default_factory=dict)
    actors: list = Field(default_factory=list)
    features: list = Field(default_factory=list)
    message: str = "draft_created"


@router.post("/chat", response_model=InterviewChatResponse)
async def interview_chat(
    request: InterviewChatRequest,
    user=Depends(get_current_user),
    llm_ctx=Depends(get_llm_context),
):
    """Send conversation history and get the AI interviewer's next response."""
    try:
        service = _get_service()
        return await service.chat(request.messages)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Project interview chat failed")
        raise HTTPException(status_code=500, detail="interview_error")


@router.post("/complete", response_model=InterviewCompleteResponse)
async def interview_complete(
    request: InterviewCompleteRequest,
    user=Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    """Complete the interview and trigger AI project draft generation.

    Steps:
    1. Create the project with the gathered requirements.
    2. Call ProjectCreationService.create_draft() to generate actors + features.
    3. Return the draft so the frontend can show DraftPreviewModal.
    """
    from backend.database.model import ProjectModel
    from backend.api.modules.project_lifecycle.application.creation_service import ProjectCreationService

    try:
        project = ProjectModel(
            name=request.name,
            description=request.description or "",
            user_requirements=request.user_requirements,
            owner_user_id=user.id,
        )
        db_session.add(project)
        await db_session.flush()

        logger.info(
            "Project created via interview  project_id=%s  name=%s",
            project.id, project.name,
        )

        # Trigger AI draft generation (same as "生成AI项目草稿")
        creation_service = ProjectCreationService()
        draft_response = await creation_service.create_draft(
            user_requirements=request.user_requirements,
            owner_user_id=user.id,
            session=db_session,
            project_name=request.name,
            project_description=request.description,
        )

        logger.info(
            "AI draft generated from interview  project_id=%s  draft_id=%s",
            project.id, draft_response.get("draft_id"),
        )

        return {
            "draft_id": draft_response.get("draft_id", ""),
            "project_preview": draft_response.get("project_preview", {}),
            "actors": draft_response.get("actors", []),
            "features": draft_response.get("features", []),
            "message": "draft_created",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Project interview complete failed")
        raise HTTPException(status_code=500, detail="project_creation_failed")
