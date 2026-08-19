"""
Version Control Merge Request REST API Routes.
MR 创建、列表、详情、评论、审批、关闭。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.project_access import require_project_member
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel
from backend.api.modules.version_control.schemas import (
    MergeRequestCreateRequest,
    MergeReviewRequest,
    MergeCommentCreateRequest,
    MergeRequestDetailResponse,
    MergeReviewResponse,
    MergeCommentResponse,
    MergeRequestPreviewRequest,
    MergeRequestPreviewResponse,
    MergeRequestListResponse,
    MergePreviewResponse,
    MergeRequestPayload,
    MergeResponse,
)
from backend.api.modules.version_control.application import merge_service
from backend.api.modules.version_control.application import merge_execution
from backend.api.modules.version_control.application.errors import (
    HeadChangedError,
    MergeBlockedError,
    MergeConflictError,
)
from backend.api.modules.version_control.audit import record_vc_event
from backend.api.modules.version_control.observability import audit_vc_failure

router = APIRouter(
    prefix="/api/projects/{project_id}/merge-requests",
    tags=["merge_requests"],
)

MR_NOT_FOUND = "merge_request_not_found"


@router.post("", response_model=MergeRequestDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_merge_request(
    project_id: str,
    request: MergeRequestCreateRequest,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.run_sync(
            lambda s: merge_service.create_merge_request(
                db=s,
                project_id=owned_project.id,
                req=request,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="merge_request_created",
            summary=f"创建 MR: {request.title}",
            target_type="merge_request",
            target_id=result.public_id,
        )
        await session.commit()
        return result
    except ValueError as e:
        err = str(e)
        status_code_map = {
            MR_NOT_FOUND: 404,
            "source_branch_not_found": 404,
            "target_branch_not_found": 404,
            "source_branch_empty": 400,
            "source_target_same": 400,
            "duplicate_open_mr": 409,
            "author_cannot_review_own_mr": 403,
            "only_admin_or_owner_can_review": 403,
            "duplicate_review_not_allowed": 409,
            "invalid_review_decision": 400,
            "mr_already_closed": 400,
            "only_author_or_admin_can_close": 403,
        }
        code = status_code_map.get(err, 400)
        raise HTTPException(status_code=code, detail=err)


@router.get("", response_model=MergeRequestListResponse)
async def list_merge_requests(
    project_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await session.run_sync(
            lambda s: merge_service.list_merge_requests(
                db=s,
                project_id=owned_project.id,
                status=status,
                limit=limit,
                offset=offset,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preview", response_model=MergeRequestPreviewResponse)
async def preview_merge_request(
    project_id: str,
    request: MergeRequestPreviewRequest,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """预计算 MR 变更摘要（merge_base → source_head），与创建后一致。"""
    try:
        return await session.run_sync(
            lambda s: merge_service.compute_mr_preview(
                db=s,
                project_id=owned_project.id,
                source_branch_public_id=request.source_branch_public_id,
                target_branch_public_id=request.target_branch_public_id,
            )
        )
    except ValueError as e:
        code = {"source_branch_not_found": 404, "target_branch_not_found": 404}.get(str(e), 400)
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/{mr_ref}", response_model=MergeRequestDetailResponse)
async def get_merge_request_detail(
    project_id: str,
    mr_ref: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await session.run_sync(
            lambda s: merge_service.get_mr_detail(
                db=s,
                project_id=owned_project.id,
                mr_ref=mr_ref,
                user_id=user.id,
            )
        )
    except ValueError as e:
        code = 404 if MR_NOT_FOUND in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/{mr_ref}/comments", response_model=MergeCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_mr_comment(
    project_id: str,
    mr_ref: str,
    request: MergeCommentCreateRequest,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.run_sync(
            lambda s: merge_service.add_mr_comment(
                db=s,
                project_id=owned_project.id,
                mr_ref=mr_ref,
                req=request,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="merge_request_comment_added",
            summary=f"评论 MR: {request.comment[:50]}",
            target_type="merge_comment",
            target_id=result.id,
        )
        await session.commit()
        return result
    except ValueError as e:
        code = 404 if MR_NOT_FOUND in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/{mr_ref}/review", response_model=MergeReviewResponse)
async def review_merge_request(
    project_id: str,
    mr_ref: str,
    request: MergeReviewRequest,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.run_sync(
            lambda s: merge_service.review_mr(
                db=s,
                project_id=owned_project.id,
                mr_ref=mr_ref,
                req=request,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="merge_request_reviewed",
            summary=f"审阅 MR: {request.decision}",
            target_type="merge_review",
            target_id=mr_ref,
        )
        await session.commit()
        return result
    except ValueError as e:
        err = str(e)
        code = {
            MR_NOT_FOUND: 404,
            "author_cannot_review_own_mr": 403,
            "only_admin_or_owner_can_review": 403,
            "duplicate_review_not_allowed": 409,
            "invalid_review_decision": 400,
            "mr_already_closed": 400,
        }.get(err, 400)
        raise HTTPException(status_code=code, detail=err)


@router.post("/{mr_ref}/comments/{comment_id}/resolve", response_model=MergeCommentResponse)
async def resolve_mr_comment(
    project_id: str,
    mr_ref: str,
    comment_id: int,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.run_sync(
            lambda s: merge_service.resolve_mr_comment(
                db=s, project_id=owned_project.id, mr_ref=mr_ref,
                comment_id=comment_id, user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="merge_request_comment_resolved",
            summary=f"解决 MR 评论 #{comment_id}",
            target_type="merge_comment",
            target_id=comment_id,
        )
        await session.commit()
        return result
    except ValueError as e:
        code = {"comment_not_found": 404, "comment_not_active": 400, "only_author_or_admin_can_resolve": 403}.get(str(e), 400)
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/{mr_ref}/comments/{comment_id}/reopen", response_model=MergeCommentResponse)
async def reopen_mr_comment(
    project_id: str,
    mr_ref: str,
    comment_id: int,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.run_sync(
            lambda s: merge_service.reopen_mr_comment(
                db=s, project_id=owned_project.id, mr_ref=mr_ref,
                comment_id=comment_id, user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="merge_request_comment_reopened",
            summary=f"重开 MR 评论 #{comment_id}",
            target_type="merge_comment",
            target_id=comment_id,
        )
        await session.commit()
        return result
    except ValueError as e:
        code = {"comment_not_found": 404, "comment_not_resolved": 400, "only_author_or_admin_can_reopen": 403}.get(str(e), 400)
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/{mr_ref}/close")
async def close_merge_request(
    project_id: str,
    mr_ref: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.run_sync(
            lambda s: merge_service.close_mr(
                db=s,
                project_id=owned_project.id,
                mr_ref=mr_ref,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="merge_request_closed",
            summary="关闭 MR",
            target_type="merge_request",
            target_id=mr_ref,
        )
        await session.commit()
        return result
    except ValueError as e:
        err = str(e)
        code = {
            MR_NOT_FOUND: 404,
            "only_author_or_admin_can_close": 403,
            "mr_already_closed": 400,
        }.get(err, 400)
        raise HTTPException(status_code=code, detail=err)


@router.get("/{mr_ref}/merge-preview", response_model=MergePreviewResponse)
async def get_mr_merge_preview(
    project_id: str,
    mr_ref: str,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """计算 MR 的三方合并预览（只读，可重建）：列出待解决冲突与自动合并统计。"""
    try:
        return await session.run_sync(
            lambda s: merge_execution.get_merge_preview(
                db=s,
                project_id=owned_project.id,
                mr_ref=mr_ref,
            )
        )
    except ValueError as e:
        code = 404 if MR_NOT_FOUND in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/{mr_ref}/merge", response_model=MergeResponse)
async def perform_mr_merge(
    project_id: str,
    mr_ref: str,
    request: MergeRequestPayload,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """执行三方语义合并并创建 merge commit；合并前必须满足审批且无未解决冲突。"""
    import time
    started = time.perf_counter()
    try:
        result = await session.run_sync(
            lambda s: merge_execution.perform_merge(
                db=s,
                project_id=owned_project.id,
                mr_ref=mr_ref,
                req=request,
                user_id=user.id,
            )
        )
        await record_vc_event(
            session=session,
            project_id=owned_project.id,
            action_type="merge_request_merged",
            summary=f"合并 MR: {mr_ref}",
            target_type="merge_request",
            target_id=mr_ref,
            payload={
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "resolution_count": len(request.resolutions or []),
            },
        )
        await session.commit()
        return result
    except MergeConflictError as e:
        await audit_vc_failure(
            project_id=owned_project.id,
            action_type="merge_conflict",
            summary=f"合并冲突: {mr_ref}",
            target_type="merge_request",
            target_id=mr_ref,
            error_type="MergeConflictError",
            conflict_ids=e.conflict_ids,
            structure_errors_count=len(e.structure_errors or []),
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "merge_conflict",
                "message": str(e),
                "conflict_ids": e.conflict_ids,
                "structure_errors": e.structure_errors,
            },
        )
    except HeadChangedError as e:
        await audit_vc_failure(
            project_id=owned_project.id,
            action_type="merge_head_changed",
            summary=f"合并 head 变化: {mr_ref}",
            target_type="merge_request",
            target_id=mr_ref,
            error_type="HeadChangedError",
            latest_head_public_id=e.current_head_public_id,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "head_changed",
                "message": str(e),
                "latest_head_commit_id": e.current_head_commit_id,
                "latest_head_public_id": e.current_head_public_id,
                "compare_ref": f"commit:{e.current_head_public_id}"
                if e.current_head_public_id
                else None,
            },
        )
    except MergeBlockedError as e:
        await audit_vc_failure(
            project_id=owned_project.id,
            action_type="merge_blocked",
            summary=f"合并被阻塞: {mr_ref}",
            target_type="merge_request",
            target_id=mr_ref,
            error_type="MergeBlockedError",
            reasons=e.reasons,
        )
        raise HTTPException(
            status_code=400,
            detail={"code": "merge_blocked", "message": str(e), "reasons": e.reasons},
        )
    except ValueError as e:
        code = 404 if MR_NOT_FOUND in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))
