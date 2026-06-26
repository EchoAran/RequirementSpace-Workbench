from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.database.model import UserModel
from backend.api.modules.project_lifecycle.schemas.blank import (
    BlankProjectCreateRequest,
    BlankProjectCreateResponse,
)
from backend.api.modules.project_lifecycle.application.blank_service import BlankProjectService
from backend.database.database import get_session
from backend.api.dependencies.llm import llm_context_manager


router = APIRouter(
    prefix="/api/blank_projects",
    tags=["blank_project"],
)

blank_project_service = BlankProjectService()


@router.post(
    "",
    response_model=BlankProjectCreateResponse,
)
async def create_blank_project(
    request: BlankProjectCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        normalized_name = blank_project_service._normalize_optional_text(request.project_name)
        normalized_description = blank_project_service._normalize_optional_text(request.project_description)
        if normalized_name is None or normalized_description is None:
            async with llm_context_manager(user, session):
                return await blank_project_service.create_project(
                    user_requirements=request.user_requirements,
                    project_name=request.project_name,
                    project_description=request.project_description,
                    owner_user_id=user.id,
                    session=session,
                )
        else:
            return await blank_project_service.create_project(
                user_requirements=request.user_requirements,
                project_name=request.project_name,
                project_description=request.project_description,
                owner_user_id=user.id,
                session=session,
            )
    except ValueError as error:
        if str(error) == "invalid_project_payload":
            raise HTTPException(
                status_code=502,
                detail="invalid_project_payload",
            )
        raise
