from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.blank_project_schema import (
    BlankProjectCreateRequest,
    BlankProjectCreateResponse,
)
from backend.api.services.blank_project_service import BlankProjectService
from backend.database.database import get_session


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
    session: AsyncSession = Depends(get_session),
):
    try:
        return await blank_project_service.create_project(
            user_requirements=request.user_requirements,
            project_name=request.project_name,
            project_description=request.project_description,
            session=session,
        )
    except ValueError as error:
        if str(error) == "invalid_project_payload":
            raise HTTPException(
                status_code=502,
                detail="invalid_project_payload",
            )
        raise
