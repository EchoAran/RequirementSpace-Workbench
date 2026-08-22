from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import llm_context_manager
from backend.api.dependencies.ownership import require_owned_project
from backend.api.dependencies.project_access import (
    require_project_member,
    require_project_owner,
)
from backend.api.modules.project_lifecycle.ports import get_project_service
from backend.api.modules.project_lifecycle.schemas.project import (
    PerceptionSlotDeleteResponse,
    ProjectDeleteResponse,
    ProjectDetailResponse,
    ProjectListItemResponse,
    ProjectUpdateRequest,
    ProjectUpdateResponse,
    ScopeImpactPreviewRequest,
    ScopeImpactPreviewResponse,
    StageProgressResponse,
    StageTransitionRequest,
    StageTransitionResponse,
)
from backend.core.locale import resolve_effective_locale
from backend.database.model import ProjectModel, UserModel


class LazyProjectServiceProxy:
    def __getattr__(self, name):
        return getattr(get_project_service(), name)

project_service = LazyProjectServiceProxy()
from backend.database.database import get_session


def _spl_attachment_disposition(filename: str) -> str:
    fallback = filename.encode("ascii", "ignore").decode("ascii").strip() or "requirement-space.spl"
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename)}'


router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
)


@router.get(
    "",
    response_model=list[ProjectListItemResponse],
)
async def list_projects(
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await project_service.list_projects(user_id=user.id, session=session)


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
)
async def get_project_detail(
    project_id: str,
    request: Request,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        detail = await project_service.get_project_detail(
            project_id=owned_project.id,
            session=session,
            branch_ref=branch,
            user_id=user.id,
        )
        cache_key = f"project_member:{project_id}:{user.id}"
        cached = getattr(request.state, cache_key, None)
        if cached:
            detail.current_user_role = cached[1].role
        return detail
    except (ValueError, PermissionError) as error:
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)


@router.post(
    "/{project_id}/stage-transition",
    response_model=StageTransitionResponse,
)
async def stage_transition(
    project_id: str,
    request: StageTransitionRequest,
    branch: str | None = Query(None),
    owned_project: ProjectModel = Depends(require_owned_project),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.stage_transition(
            project_id=owned_project.id,
            action=request.action,
            force=request.force,
            operator_id=user.id,
            branch_ref=branch,
            session=session,
        )
    except (ValueError, PermissionError) as error:
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)



@router.delete(
    "/{project_id}/perception-slot",
    response_model=PerceptionSlotDeleteResponse,
)
async def delete_perception_slot(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_owned_project),
    session: AsyncSession = Depends(get_session),
):
    try:
        from backend.api.modules.version_control.public import resolve_branch_context
        _branch, ws_obj, _perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
        return await project_service.delete_perception_slot(
            project_id=owned_project.id,
            session=session,
            workspace_id=ws_obj.id if ws_obj else None,
        )
    except (ValueError, PermissionError) as error:
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)


@router.delete(
    "/{project_id}",
    response_model=ProjectDeleteResponse,
)
async def delete_project(
    project_id: str,
    owned_project: ProjectModel = Depends(require_project_owner),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.delete_project(
            project_id=owned_project.id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.put(
    "/{project_id}",
    response_model=ProjectUpdateResponse,
)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    owned_project: ProjectModel = Depends(require_owned_project),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.update_project(
            project_id=owned_project.id,
            name=request.name,
            description=request.description,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.get(
    "/{project_id}/export/json",
    response_model=ProjectDetailResponse,
)
async def export_project_json(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_member),
):
    import re

    from fastapi.responses import JSONResponse

    from backend.api.modules.version_control.application.branch_service import (
        resolve_branch_context,
    )
    branch_obj, _ws_obj, _perms = await session.run_sync(
        lambda s: resolve_branch_context(s, project.id, branch, user.id)
    )
    try:
        detail = await project_service.get_project_detail(
            project_id=project.id,
            session=session,
            branch_ref=branch_obj.name if branch_obj else None,
            user_id=user.id,
        )
        safe_name = re.sub(r'[\\/*?:"<>|]', "", project.name or "").strip() or "requirement-space"
        safe_branch = re.sub(r'[\\/*?:"<>|]', "_", branch_obj.name if branch_obj else "main")
        commit_short = branch_obj.head_commit.public_id[:7] if (branch_obj and branch_obj.head_commit) else "head"
        filename = f"{safe_name}_{safe_branch}_{commit_short}.json"

        return JSONResponse(
            content=detail.model_dump(),
            headers={"Content-Disposition": _spl_attachment_disposition(filename)}
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.get(
    "/{project_id}/export/markdown",
    response_class=PlainTextResponse,
)
async def export_project_markdown(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_member),
):
    import re

    from backend.api.modules.version_control.application.branch_service import (
        resolve_branch_context,
    )
    branch_obj, _ws_obj, _perms = await session.run_sync(
        lambda s: resolve_branch_context(s, project.id, branch, user.id)
    )
    try:
        async with llm_context_manager(user, session, project_id=project.id):
            md_text = await project_service.export_project_markdown(
                project_id=project.id,
                session=session,
                branch_ref=branch_obj.name if branch_obj else None,
                user_id=user.id,
            )
        safe_name = re.sub(r'[\\/*?:"<>|]', "", project.name or "").strip() or "requirement-space"
        safe_branch = re.sub(r'[\\/*?:"<>|]', "_", branch_obj.name if branch_obj else "main")
        commit_short = branch_obj.head_commit.public_id[:7] if (branch_obj and branch_obj.head_commit) else "head"
        filename = f"{safe_name}_{safe_branch}_{commit_short}.md"

        return PlainTextResponse(
            content=md_text,
            headers={"Content-Disposition": _spl_attachment_disposition(filename)}
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.get(
    "/{project_id}/export/spl/syntax",
    response_class=PlainTextResponse,
)
async def export_project_spl_syntax(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_member),
):
    import re

    from backend.api.modules.version_control.application.branch_service import (
        resolve_branch_context,
    )
    branch_obj, _ws_obj, _perms = await session.run_sync(
        lambda s: resolve_branch_context(s, project.id, branch, user.id)
    )
    try:
        spl_text = await project_service.export_project_spl_syntax(
            project_id=project.id,
            session=session,
            content_locale=resolve_effective_locale(
                project.content_locale,
                user.preferred_locale,
            )[0],
            branch_ref=branch_obj.name if branch_obj else None,
            user_id=user.id,
        )
        safe_name = re.sub(r'[\\/*?:"<>|]', "", project.name or "").strip() or "requirement-space"
        safe_branch = re.sub(r'[\\/*?:"<>|]', "_", branch_obj.name if branch_obj else "main")
        commit_short = branch_obj.head_commit.public_id[:7] if (branch_obj and branch_obj.head_commit) else "head"
        filename = f"{safe_name}_{safe_branch}_{commit_short}-syntax.spl"
        return PlainTextResponse(
            content=spl_text,
            headers={
                "Content-Disposition": _spl_attachment_disposition(filename)
            }
        )
    except ValueError as error:
        err_msg = str(error)
        if err_msg == "project_not_found":
            raise HTTPException(status_code=404, detail="project_not_found")
        if err_msg == "spl_export_skill_unavailable":
            raise HTTPException(status_code=503, detail="spl_export_skill_unavailable")
        if err_msg == "spl_export_invalid_skill_output":
            raise HTTPException(status_code=500, detail="spl_export_invalid_skill_output")
        raise

@router.get(
    "/{project_id}/export/spl/semantic",
    response_class=PlainTextResponse,
)
async def export_project_spl_semantic(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_member),
):
    import os
    import re
    if os.getenv("SPL_SEMANTIC_EXPORT_ENABLED", "true").lower() == "false":
        raise HTTPException(status_code=400, detail="spl_export_semantic_disabled")

    from backend.api.modules.version_control.application.branch_service import (
        resolve_branch_context,
    )
    branch_obj, _ws_obj, _perms = await session.run_sync(
        lambda s: resolve_branch_context(s, project.id, branch, user.id)
    )

    try:
        async with llm_context_manager(user, session, project_id=project.id) as llm_ctx:
            spl_text = await project_service.export_project_spl_semantic(
                project_id=project.id,
                session=session,
                llm_ctx=llm_ctx,
                branch_ref=branch_obj.name if branch_obj else None,
                user_id=user.id,
            )
        safe_name = re.sub(r'[\\/*?:"<>|]', "", project.name or "").strip() or "requirement-space"
        safe_branch = re.sub(r'[\\/*?:"<>|]', "_", branch_obj.name if branch_obj else "main")
        commit_short = branch_obj.head_commit.public_id[:7] if (branch_obj and branch_obj.head_commit) else "head"
        filename = f"{safe_name}_{safe_branch}_{commit_short}-semantic.spl"
        return PlainTextResponse(
            content=spl_text,
            headers={
                "Content-Disposition": _spl_attachment_disposition(filename)
            }
        )
    except ValueError as error:
        err_msg = str(error)
        if err_msg == "project_not_found":
            raise HTTPException(status_code=404, detail="project_not_found")
        if err_msg == "spl_export_skill_unavailable":
            raise HTTPException(status_code=503, detail="spl_export_skill_unavailable")
        if err_msg == "spl_export_invalid_skill_output":
            raise HTTPException(status_code=500, detail="spl_export_invalid_skill_output")
        if err_msg == "spl_export_timeout":
            raise HTTPException(status_code=504, detail="spl_export_timeout")
        if err_msg == "spl_export_semantic_disabled":
            raise HTTPException(status_code=400, detail="spl_export_semantic_disabled")
        raise

@router.post(
    "/{project_id}/impact-preview",
    response_model=ScopeImpactPreviewResponse,
)
async def preview_scope_impact(
    project_id: str,
    request: ScopeImpactPreviewRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.preview_scope_impact(
            project_id=owned_project.id,
            feature_id=request.feature_id,
            next_status=request.next_status,
            session=session,
            branch_ref=branch,
            user_id=user.id,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) == "feature_not_found":
            raise HTTPException(
                status_code=404,
                detail="feature_not_found",
            )
        raise


@router.get(
    "/{project_id}/stage-progress",
    response_model=StageProgressResponse,
)
async def get_stage_progress(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.get_stage_progress(
            project_id=owned_project.id,
            public_project_id=project_id,
            session=session,
            branch_ref=branch,
            user_id=user.id,
        )
    except (ValueError, PermissionError) as error:
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)
