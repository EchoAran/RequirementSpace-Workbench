from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from backend.database.database import get_session

from backend.api.modules.requirements_core.business_object.schemas import (
    BusinessObjectCreateRequest,
    BusinessObjectUpdateRequest,
    BusinessObjectResponse,
    BusinessObjectAttributeCreateRequest,
    BusinessObjectAttributeUpdateRequest,
    BusinessObjectAttributeResponse,
)
from backend.api.modules.requirements_core.business_object.application.business_object_service import BusinessObjectService

router = APIRouter(
    prefix="/api/projects/{project_id}/business_objects",
    tags=["business_objects"],
)

bo_service = BusinessObjectService()


@router.post("", response_model=BusinessObjectResponse)
async def create_business_object(
    project_id: str,
    request: BusinessObjectCreateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await bo_service.create_business_object(
            project_id=owned_project.id,
            req=request,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create business object: {error}",
        )


@router.put("/{bo_id}", response_model=BusinessObjectResponse)
async def update_business_object(
    project_id: str,
    bo_id: int,
    request: BusinessObjectUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await bo_service.update_business_object(
            project_id=owned_project.id,
            bo_id=bo_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "business_object_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update business object: {error}",
        )


@router.delete("/{bo_id}")
async def delete_business_object(
    project_id: str,
    bo_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await bo_service.delete_business_object(
            project_id=owned_project.id,
            bo_id=bo_id,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete business object: {error}",
        )


@router.post("/{bo_id}/attributes", response_model=BusinessObjectAttributeResponse)
async def create_business_object_attribute(
    project_id: str,
    bo_id: int,
    request: BusinessObjectAttributeCreateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await bo_service.create_business_object_attribute(
            project_id=owned_project.id,
            bo_id=bo_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create business object attribute: {error}",
        )


@router.put("/{bo_id}/attributes/{attr_id}", response_model=BusinessObjectAttributeResponse)
async def update_business_object_attribute(
    project_id: str,
    bo_id: int,
    attr_id: int,
    request: BusinessObjectAttributeUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await bo_service.update_business_object_attribute(
            project_id=owned_project.id,
            bo_id=bo_id,
            attr_id=attr_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update business object attribute: {error}",
        )


@router.delete("/{bo_id}/attributes/{attr_id}")
async def delete_business_object_attribute(
    project_id: str,
    bo_id: int,
    attr_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await bo_service.delete_business_object_attribute(
            project_id=owned_project.id,
            bo_id=bo_id,
            attr_id=attr_id,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete business object attribute: {error}",
        )

