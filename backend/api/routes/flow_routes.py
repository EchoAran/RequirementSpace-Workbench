from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.crud_schema import (
    FlowCreateRequest,
    FlowUpdateRequest,
    FlowResponse,
    FlowStepCreateRequest,
    FlowStepUpdateRequest,
    FlowStepResponse,
)
from backend.api.services.flow_service import FlowService
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/projects/{project_id}/flows",
    tags=["flows"],
)

flow_service = FlowService()


@router.post("", response_model=FlowResponse)
async def create_flow(
    project_id: int,
    request: FlowCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_service.create_flow(
            project_id=project_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create flow: {error}",
        )


@router.put("/{flow_id}", response_model=FlowResponse)
async def update_flow(
    project_id: int,
    flow_id: int,
    request: FlowUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_service.update_flow(
            project_id=project_id,
            flow_id=flow_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "flow_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update flow: {error}",
        )


@router.delete("/{flow_id}")
async def delete_flow(
    project_id: int,
    flow_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_service.delete_flow(
            project_id=project_id,
            flow_id=flow_id,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete flow: {error}",
        )


@router.post("/{flow_id}/steps", response_model=FlowStepResponse)
async def create_flow_step(
    project_id: int,
    flow_id: int,
    request: FlowStepCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_service.create_flow_step(
            project_id=project_id,
            flow_id=flow_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create flow step: {error}",
        )


@router.put("/{flow_id}/steps/{step_id}", response_model=FlowStepResponse)
async def update_flow_step(
    project_id: int,
    flow_id: int,
    step_id: int,
    request: FlowStepUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_service.update_flow_step(
            project_id=project_id,
            flow_id=flow_id,
            step_id=step_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update flow step: {error}",
        )


@router.delete("/{flow_id}/steps/{step_id}")
async def delete_flow_step(
    project_id: int,
    flow_id: int,
    step_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_service.delete_flow_step(
            project_id=project_id,
            flow_id=flow_id,
            step_id=step_id,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete flow step: {error}",
        )
