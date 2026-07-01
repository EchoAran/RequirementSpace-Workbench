from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from backend.api.dependencies.auth import get_current_user
from backend.database.model import UserModel
from backend.api.modules.auth_account.public import LLMConfigService
from backend.database.database import get_session
from backend.core.llm_context import current_llm_context, LLMRequestContext

llm_config_service = LLMConfigService()


@asynccontextmanager
async def llm_context_manager(user: UserModel, session: AsyncSession, project_id: int | None = None):
    """Context manager to resolve user LLM configuration and set request context."""
    try:
        config_data = await llm_config_service.resolve_for_user(user.id, session, project_id=project_id)
    except ValueError as e:
        err_msg = str(e)
        if err_msg in ("llm_config_required", "server_llm_config_not_configured"):
            raise HTTPException(status_code=409, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

    api_url = config_data.get("api_url")
    api_key = config_data.get("api_key")
    model_name = config_data.get("model_name")

    if not api_url or not api_key or not model_name:
        raise HTTPException(status_code=409, detail="llm_config_required")

    ctx = LLMRequestContext(
        api_url=api_url,
        api_key=api_key,
        model_name=model_name
    )

    token = current_llm_context.set(ctx)
    try:
        yield ctx
    finally:
        current_llm_context.reset(token)


async def get_llm_context(
    request: Request = None,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> LLMRequestContext:
    """FastAPI dependency to resolve the current user's LLM configuration and set request context."""
    project_id_int = None
    if request is not None:
        project_id_str = request.path_params.get("project_id")
        if project_id_str:
            from backend.database.model import ProjectModel
            from sqlalchemy import select
            stmt = select(ProjectModel.id).where(ProjectModel.public_id == project_id_str)
            res = await session.execute(stmt)
            project_id_int = res.scalar_one_or_none()

        if not project_id_int:
            session_id = request.path_params.get("session_id")
            if session_id:
                from backend.database.model import AIAddSessionModel
                from sqlalchemy import select
                stmt = select(AIAddSessionModel.project_id).where(AIAddSessionModel.session_id == session_id)
                res = await session.execute(stmt)
                project_id_int = res.scalar_one_or_none()

        if not project_id_int:
            choice_group_id = request.path_params.get("choice_group_id")
            if choice_group_id:
                try:
                    choice_group_id_int = int(choice_group_id)
                    from backend.database.model import ChoiceGroupModel
                    from sqlalchemy import select
                    stmt = select(ChoiceGroupModel.project_id).where(ChoiceGroupModel.id == choice_group_id_int)
                    res = await session.execute(stmt)
                    project_id_int = res.scalar_one_or_none()
                except ValueError:
                    pass

        if not project_id_int:
            draft_id = request.path_params.get("draft_id")
            if draft_id:
                from backend.database.model import GenerativeDraftModel
                from sqlalchemy import select
                stmt = select(GenerativeDraftModel.project_id).where(GenerativeDraftModel.draft_id == draft_id)
                res = await session.execute(stmt)
                project_id_int = res.scalar_one_or_none()

    async with llm_context_manager(user, session, project_id=project_id_int) as ctx:
        yield ctx
