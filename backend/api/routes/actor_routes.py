from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.crud_schema import (
    ActorCreateRequest,
    ActorUpdateRequest,
    ActorResponse,
)
from backend.api.services.actor_service import ActorService
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/projects/{project_id}/actors",
    tags=["actors"],
)

actor_service = ActorService()


@router.get("", response_model=list[ActorResponse])
async def list_actors(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await actor_service.get_actors(
            project_id=project_id,
            session=session,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch actors: {error}",
        )


@router.post("", response_model=ActorResponse)
async def create_actor(
    project_id: int,
    request: ActorCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await actor_service.create_actor(
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
            detail=f"Failed to create actor: {error}",
        )


@router.put("/{actor_id}", response_model=ActorResponse)
async def update_actor(
    project_id: int,
    actor_id: int,
    request: ActorUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await actor_service.update_actor(
            project_id=project_id,
            actor_id=actor_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "actor_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update actor: {error}",
        )


@router.delete("/{actor_id}")
async def delete_actor(
    project_id: int,
    actor_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await actor_service.delete_actor(
            project_id=project_id,
            actor_id=actor_id,
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
            detail=f"Failed to delete actor: {error}",
        )
