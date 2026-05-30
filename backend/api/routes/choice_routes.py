from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.choice_schema import (
    ChoiceGroupResponse,
    ChoiceActionResponse,
    GenerationChoiceGroupCreateRequest,
    GenerationAcceptRequest,
)
from backend.api.services.choice_service import ChoiceService
from backend.api.services.generation_choice_service import (
    GenerationChoiceService,
)
from backend.database.database import get_session

router = APIRouter(
    tags=["choices"],
)

choice_service = ChoiceService()
generation_choice_service = GenerationChoiceService()


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
    body: GenerationAcceptRequest = GenerationAcceptRequest(),
    session: AsyncSession = Depends(get_session),
):
    """采纳一个 choice。支持 patch 和 draft_payload 两种模式。
    对 draft_payload 型 choice，默认检查上下文是否过期。
    设置 force=true 可跳过 stale 检查。"""
    try:
        return await choice_service.accept_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=session,
            force=body.force,
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


@router.post(
    "/api/projects/{project_id}/choice_groups/{group_id}/discard",
    response_model=ChoiceGroupResponse,
)
async def discard_choice_group(
    project_id: int,
    group_id: int,
    session: AsyncSession = Depends(get_session),
):
    """丢弃整个 choice group。所有候选标记为 discarded，不写入真实模型。"""
    try:
        return await choice_service.discard_choice_group(
            project_id=project_id,
            group_id=group_id,
            session=session,
        )
    except ValueError as error:
        err_msg = str(error)
        status_code = 400
        if err_msg == "choice_group_not_found":
            status_code = 404
        elif err_msg == "resolved_group_cannot_be_discarded":
            status_code = 409
        raise HTTPException(
            status_code=status_code,
            detail=err_msg,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to discard choice group: {error}",
        )


# ═══════════════════════════════════════════
# Phase 1: Generation Choice Group API
# ═══════════════════════════════════════════

@router.post(
    "/api/generation_choice_groups",
    response_model=ChoiceGroupResponse,
)
async def create_generation_choice_group(
    body: GenerationChoiceGroupCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    创建一个 AI 生成 choice group。
    后端按 candidate_count 并发生成多个候选，保存为 choice group。
    用户稍后可调用 accept、reject、discard 处理。
    """
    try:
        result = await generation_choice_service.create_choice_group(
            project_id=body.project_id,
            generation_type=body.generation_type,
            target=body.target,
            candidate_count=body.candidate_count,
            user_feedback=body.user_feedback,
            session=session,
        )
        return result
    except ValueError as error:
        err_msg = str(error)
        status_code = 400
        if "unsupported_generation_type" in err_msg:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=err_msg)
    except RuntimeError as error:
        # 候选生成失败（全部失败或低于部分成功下限）
        raise HTTPException(status_code=500, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create generation choice group: {error}",
        )


@router.post(
    "/api/projects/{project_id}/choice_groups/{group_id}/regenerate",
    response_model=ChoiceGroupResponse,
)
async def regenerate_choice_group(
    project_id: int,
    group_id: int,
    feedback: str | None = Query(None, description="User feedback for regeneration"),
    session: AsyncSession = Depends(get_session),
):
    """重新生成整个 choice group。旧 group 标记为 discarded，新建一个。"""
    try:
        return await generation_choice_service.regenerate_choice_group(
            project_id=project_id,
            group_id=group_id,
            user_feedback=feedback,
            session=session,
        )
    except ValueError as error:
        err_msg = str(error)
        status_code = 400
        if err_msg == "choice_group_not_found":
            status_code = 404
        elif err_msg == "choice_group_already_resolved":
            status_code = 409
        raise HTTPException(status_code=status_code, detail=err_msg)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate choice group: {error}",
        )


@router.post(
    "/api/projects/{project_id}/choices/{choice_id}/regenerate",
    response_model=ChoiceGroupResponse,
)
async def regenerate_choice(
    project_id: int,
    choice_id: int,
    feedback: str | None = Query(None, description="User feedback for regeneration"),
    session: AsyncSession = Depends(get_session),
):
    """重新生成单个 choice，替代原候选。"""
    try:
        return await generation_choice_service.regenerate_choice(
            project_id=project_id,
            choice_id=choice_id,
            user_feedback=feedback,
            session=session,
        )
    except ValueError as error:
        err_msg = str(error)
        status_code = 400
        if err_msg == "choice_not_found":
            status_code = 404
        elif err_msg == "choice_group_already_resolved":
            status_code = 409
        raise HTTPException(status_code=status_code, detail=err_msg)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate choice: {error}",
        )
