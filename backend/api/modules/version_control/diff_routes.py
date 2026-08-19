"""
Version Control Semantic Diff REST API Routes.
提供任意 commit/branch/workspace 两两比较的语义差异、实体详情、分页与筛选。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel
from backend.api.modules.version_control.schemas import DiffResult, EntityDiffResponse
from backend.api.modules.version_control.application import diff_service
from backend.api.modules.version_control.application.errors import (
    BranchNotFoundError,
    CommitNotFoundError,
    InvalidDiffRefError,
)
from backend.api.modules.version_control.audit import record_vc_failure_event

router = APIRouter(
    prefix="/api/projects/{project_id}/diff",
    tags=["diff"],
)


@router.get("", response_model=DiffResult)
async def get_diff(
    project_id: str,
    base_ref: str | None = Query(None),
    target_ref: str | None = Query(None),
    branch: str | None = Query(None),
    entity_type: str | None = Query(None),
    change_type: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """计算两 ref 的语义差异；缺省比较分支 head 与当前工作区（未提交变更）。"""
    try:
        return await session.run_sync(
            lambda s: diff_service.get_diff(
                db=s,
                project_id=owned_project.id,
                base_ref=base_ref,
                target_ref=target_ref,
                branch_ref=branch,
                entity_type=entity_type,
                change_type=change_type,
                limit=limit,
                offset=offset,
            )
        )
    except (BranchNotFoundError, CommitNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error))
    except InvalidDiffRefError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        # 只读路径内部失败：记录审计以便可观测，再抛出 400 明确失败。
        await record_vc_failure_event(
            project_id=owned_project.id,
            action_type="diff_failed",
            summary=f"Diff 计算失败: {type(error).__name__}",
            target_type="project",
            target_id=owned_project.public_id,
        )
        raise HTTPException(status_code=400, detail=f"diff_computation_failed: {type(error).__name__}")


@router.get("/entities/{entity_uuid}", response_model=EntityDiffResponse)
async def get_entity_diff(
    project_id: str,
    entity_uuid: str,
    base_ref: str | None = Query(None),
    target_ref: str | None = Query(None),
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """返回单个对象的差异详情：自身及子对象变更，以及 base/target 的完整值。"""
    try:
        return await session.run_sync(
            lambda s: diff_service.get_entity_diff(
                db=s,
                project_id=owned_project.id,
                entity_uuid=entity_uuid,
                base_ref=base_ref,
                target_ref=target_ref,
                branch_ref=branch,
            )
        )
    except (BranchNotFoundError, CommitNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error))
    except InvalidDiffRefError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        await record_vc_failure_event(
            project_id=owned_project.id,
            action_type="diff_failed",
            summary=f"Diff 计算失败: {type(error).__name__}",
            target_type="project",
            target_id=owned_project.public_id,
        )
        raise HTTPException(status_code=400, detail=f"diff_computation_failed: {type(error).__name__}")
