from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.api.modules.requirements_core.business_object.application.business_object_service import (
    BusinessObjectService,
)
from backend.api.modules.requirements_core.business_object.schemas import (
    BusinessObjectAttributeCreateRequest,
    BusinessObjectAttributeResponse,
    BusinessObjectAttributeUpdateRequest,
    BusinessObjectCreateRequest,
    BusinessObjectResponse,
    BusinessObjectUpdateRequest,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.api.modules.version_control.public import map_branch_error, resolve_branch_context
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

router = APIRouter(
    prefix="/api/projects/{project_id}/business_objects",
    tags=["business_objects"],
)

bo_service = BusinessObjectService()


@router.post("", response_model=BusinessObjectResponse)
async def create_business_object(
    project_id: str,
    request: BusinessObjectCreateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id if ws_obj else None
        return await bo_service.create_business_object(
            project_id=owned_project.id,
            req=request,
            session=session,
            workspace_id=ws_id,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id if ws_obj else None
        return await bo_service.update_business_object(
            project_id=owned_project.id,
            bo_id=bo_id,
            req=request,
            session=session,
            workspace_id=ws_id,
        )
    except ValueError as error:
        err_msg = str(error)
        if "optimistic_lock" in err_msg or "stale" in err_msg or "version_conflict" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        status = 404 if "not_found" in err_msg else 400
        raise HTTPException(
            status_code=status,
            detail=err_msg,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id if ws_obj else None
        return await bo_service.delete_business_object(
            project_id=owned_project.id,
            bo_id=bo_id,
            session=session,
            workspace_id=ws_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404 if "not_found" in str(error) else 400,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id if ws_obj else None
        return await bo_service.create_business_object_attribute(
            project_id=owned_project.id,
            bo_id=bo_id,
            req=request,
            session=session,
            workspace_id=ws_id,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id if ws_obj else None
        return await bo_service.update_business_object_attribute(
            project_id=owned_project.id,
            bo_id=bo_id,
            attr_id=attr_id,
            req=request,
            session=session,
            workspace_id=ws_id,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id if ws_obj else None
        return await bo_service.delete_business_object_attribute(
            project_id=owned_project.id,
            bo_id=bo_id,
            attr_id=attr_id,
            session=session,
            workspace_id=ws_id,
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
