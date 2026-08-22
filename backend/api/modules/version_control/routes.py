"""
Version Control Branch REST API Routes.
定义分支生命周期管理与工作区切换的 HTTP 路由。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.api.dependencies.project_access import require_project_writer
from backend.api.modules.version_control.application import branch_service
from backend.api.modules.version_control.audit import record_vc_event
from backend.api.modules.version_control.schemas import (
    BranchCreateRequest,
    BranchDetailResponse,
    BranchSummaryResponse,
    BranchUpdateRequest,
)
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

router = APIRouter(
    prefix="/api/projects/{project_id}/branches",
    tags=["branches"],
)


@router.get("", response_model=list[BranchSummaryResponse])
async def list_branches(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """列表获取项目下的所有活跃分支。"""
    try:
        return await session.run_sync(
            lambda s: branch_service.list_branches(
                db=s,
                project_id=owned_project.id,
                user_id=user.id,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{branch_ref}", response_model=BranchDetailResponse)
async def get_branch_detail(
    project_id: str,
    branch_ref: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """获取指定分支的详细数据。"""
    try:
        return await session.run_sync(
            lambda s: branch_service.get_branch_detail(
                db=s,
                project_id=owned_project.id,
                branch_ref=branch_ref,
                user_id=user.id,
            )
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", response_model=BranchDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    project_id: str,
    request: BranchCreateRequest,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_writer),
    session: AsyncSession = Depends(get_session),
):
    """从指定 Commit 或源分支创建新分支。"""
    try:
        res = await session.run_sync(
            lambda s: branch_service.create_branch(
                db=s,
                project_id=owned_project.id,
                req=request,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="create_branch",
            summary=f"创建分支: {request.name}",
            target_type="branch",
            target_id=res.public_id,
        )
        await session.commit()
        return res
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{branch_ref}", response_model=BranchDetailResponse)
async def rename_branch(
    project_id: str,
    branch_ref: str,
    request: BranchUpdateRequest,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """重命名非受保护分支。"""
    try:
        res = await session.run_sync(
            lambda s: branch_service.rename_branch(
                db=s,
                project_id=owned_project.id,
                branch_ref=branch_ref,
                req=request,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="rename_branch",
            summary=f"重命名分支: {branch_ref} → {request.name}",
            target_type="branch",
            target_id=res.public_id,
        )
        await session.commit()
        return res
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        if "cannot rename protected" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{branch_ref}")
async def delete_branch(
    project_id: str,
    branch_ref: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """删除非受保护分支。"""
    try:
        res = await session.run_sync(
            lambda s: branch_service.delete_branch(
                db=s,
                project_id=owned_project.id,
                branch_ref=branch_ref,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="delete_branch",
            summary=f"删除分支: {branch_ref}",
            target_type="branch",
            target_id=branch_ref,
        )
        await session.commit()
        return res
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        if "cannot delete protected" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/active/preference")
@router.get("/active")
async def get_active_branch_preference(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户在项目中的活跃分支偏好。"""
    active_branch = await session.run_sync(
        lambda s: branch_service.get_active_branch_preference(
            db=s,
            project_id=owned_project.id,
            user_id=user.id,
        )
    )
    return {"project_id": owned_project.id, "active_branch": active_branch}


@router.put("/active/preference")
@router.put("/active")
async def set_active_branch_preference(
    project_id: str,
    branch_name: str = Query(...),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """更新当前用户在项目中的活跃分支偏好。"""
    try:
        active_branch = await session.run_sync(
            lambda s: branch_service.set_active_branch_preference(
                db=s,
                project_id=owned_project.id,
                user_id=user.id,
                branch_name=branch_name,
            )
        )
        await session.commit()
        return {"project_id": owned_project.id, "active_branch": active_branch}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
