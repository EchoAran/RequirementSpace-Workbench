"""
Version Control Commit REST API Routes.
提供提交创建（含 head compare-and-swap 409）、提交图分页查询与历史只读详情。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.api.modules.version_control.application import commit_service
from backend.api.modules.version_control.application.errors import (
    BranchNotFoundError,
    CommitNotFoundError,
    HeadChangedError,
    ProtectedBranchError,
)
from backend.api.modules.version_control.audit import record_vc_event
from backend.api.modules.version_control.observability import audit_vc_failure
from backend.api.modules.version_control.schemas import (
    CommitCreateRequest,
    CommitDetailResponse,
    CommitListResponse,
    CommitRevertRequest,
)
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

router = APIRouter(
    prefix="/api/projects/{project_id}/commits",
    tags=["commits"],
)


@router.post("", response_model=CommitDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_commit(
    project_id: str,
    request: CommitCreateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """把指定分支工作区固化为不可变提交；main 受保护禁止直接提交，预期 head 变化返回 409。"""
    try:
        result = await session.run_sync(
            lambda s: commit_service.create_commit(
                db=s,
                project_id=owned_project.id,
                branch_ref=branch,
                req=request,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="create_commit",
            summary=f"提交: {request.message[:80]}",
            target_type="commit",
            target_id=result.public_id,
        )
        # 分支提交后刷新关联 MR（失效审批、更新 head），与 commit 同事务。
        # 同步失败时整笔事务回滚，确保"提交已落地但审批仍有效"的不一致状态不会出现。
        from backend.api.modules.version_control.application.branch_service import (
            resolve_branch_context,
        )
        from backend.api.modules.version_control.application.merge_service import (
            sync_mrs_on_branch_commit,
        )
        branch_obj, _, _ = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
        if branch_obj and branch_obj.id:
            await session.run_sync(
                lambda s: sync_mrs_on_branch_commit(s, owned_project.id, branch_obj.id)
            )
        await session.commit()
        return result
    except HeadChangedError as error:
        # 提交冲突（409 高频）：记录失败审计供监控按 action_type=commit_head_changed 聚合。
        await audit_vc_failure(
            project_id=owned_project.id,
            action_type="commit_head_changed",
            summary="提交冲突：分支 head 已推进",
            target_type="commit",
            target_id=error.current_head_public_id or "head",
            error_type="HeadChangedError",
            latest_head_public_id=error.current_head_public_id,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "head_changed",
                "message": str(error),
                "latest_head_commit_id": error.current_head_commit_id,
                "latest_head_public_id": error.current_head_public_id,
                "compare_ref": f"commit:{error.current_head_public_id}"
                if error.current_head_public_id
                else None,
            },
        )
    except ProtectedBranchError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except (BranchNotFoundError, CommitNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("", response_model=CommitListResponse)
async def list_commits(
    project_id: str,
    branch: str | None = Query(None),
    all: bool = Query(False, description="返回全项目提交图，忽略 branch 过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """分页列出项目内或指定分支可达的提交图。"""
    try:
        return await session.run_sync(
            lambda s: commit_service.list_commits(
                db=s,
                project_id=owned_project.id,
                branch_ref=branch,
                all=all,
                limit=limit,
                offset=offset,
            )
        )
    except (ValueError, PermissionError) as error:
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)


@router.get("/{commit_ref}", response_model=CommitDetailResponse)
async def get_commit_detail(
    project_id: str,
    commit_ref: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """获取提交详情并从 state_json 重建历史只读视图。"""
    try:
        return await session.run_sync(
            lambda s: commit_service.get_commit_detail(
                db=s,
                project_id=owned_project.id,
                commit_ref=commit_ref,
            )
        )
    except CommitNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/{commit_ref}/revert", response_model=CommitDetailResponse, status_code=status.HTTP_201_CREATED)
async def revert_commit(
    project_id: str,
    commit_ref: str,
    request: CommitRevertRequest | None = None,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """将指定分支的工作区与需求模型回滚到该提交快照，并生成一条新的 Revert 提交。"""
    branch_ref = (request.branch_ref if request and request.branch_ref else None) or branch
    if not branch_ref:
        raise HTTPException(status_code=400, detail="branch_required")

    custom_message = request.message if request else None

    try:
        result = await session.run_sync(
            lambda s: commit_service.revert_commit(
                db=s,
                project_id=owned_project.id,
                branch_ref=branch_ref,
                target_commit_ref=commit_ref,
                user_id=user.id,
                custom_message=custom_message,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="commit_reverted",
            summary=f"回滚提交到: {commit_ref[:8]}",
            target_type="commit",
            target_id=result.public_id,
            payload={"branch": branch_ref, "reverted_to_commit": commit_ref},
        )
        await session.commit()
        return result
    except CommitNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(error))
    except BranchNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(error))
    except ProtectedBranchError as error:
        await session.rollback()
        raise HTTPException(status_code=403, detail=str(error))
    except (ValueError, PermissionError) as error:
        await session.rollback()
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)
    except Exception as error:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(error))
