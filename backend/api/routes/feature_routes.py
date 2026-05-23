from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.crud_schema import (
    FeatureCreateRequest,
    FeatureUpdateRequest,
    FeatureResponse,
)
from backend.api.services.feature_service import FeatureService
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/projects/{project_id}/features",
    tags=["features"],
)

feature_service = FeatureService()


@router.get("", response_model=list[FeatureResponse])
async def list_features(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await feature_service.get_features(
            project_id=project_id,
            session=session,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch features: {error}",
        )


@router.post("", response_model=FeatureResponse)
async def create_feature(
    project_id: int,
    request: FeatureCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await feature_service.create_feature(
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
            detail=f"Failed to create feature: {error}",
        )


@router.put("/{feature_id}", response_model=FeatureResponse)
async def update_feature(
    project_id: int,
    feature_id: int,
    request: FeatureUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await feature_service.update_feature(
            project_id=project_id,
            feature_id=feature_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "feature_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update feature: {error}",
        )


@router.delete("/{feature_id}")
async def delete_feature(
    project_id: int,
    feature_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await feature_service.delete_feature(
            project_id=project_id,
            feature_id=feature_id,
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
            detail=f"Failed to delete feature: {error}",
        )
