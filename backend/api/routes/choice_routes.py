from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.choice_schema import (
    ChoiceGroupResponse,
    ChoiceActionResponse,
)
from backend.api.services.choice_service import ChoiceService
from backend.database.database import get_session

router = APIRouter(
    tags=["choices"],
)

choice_service = ChoiceService()


@router.get(
    "/api/projects/{project_id}/choice_groups",
    response_model=list[ChoiceGroupResponse],
)
async def list_choice_groups(
    project_id: int,
    status: str | None = Query(None, description="Filter by ChoiceGroup status (e.g. 'open', 'resolved')"),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await choice_service.list_choice_groups(
            project_id=project_id,
            status=status,
            session=session,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch choice groups: {error}",
        )


@router.post(
    "/api/projects/{project_id}/choices/{choice_id}/accept",
    response_model=ChoiceActionResponse,
)
async def accept_choice(
    project_id: int,
    choice_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await choice_service.accept_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=session,
        )
    except ValueError as error:
        err_msg = str(error)
        status_code = 400
        if err_msg in ["choice_not_found", "choice_group_not_found"]:
            status_code = 404
        elif err_msg == "choice_group_already_resolved":
            status_code = 409
        raise HTTPException(
            status_code=status_code,
            detail=err_msg,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to accept choice: {error}",
        )


@router.post(
    "/api/projects/{project_id}/choices/{choice_id}/reject",
    response_model=ChoiceActionResponse,
)
async def reject_choice(
    project_id: int,
    choice_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await choice_service.reject_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=session,
        )
    except ValueError as error:
        err_msg = str(error)
        status_code = 404 if err_msg in ["choice_not_found", "choice_group_not_found"] else 400
        raise HTTPException(
            status_code=status_code,
            detail=err_msg,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject choice: {error}",
        )
