from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database.model import ProjectModel, AuditLogModel
from backend.api.modules.project_lifecycle.schemas.audit import (
    AuditLogResponse,
    UserRequirementsResponse,
)
from backend.services.llm_handler_service import LLMHandler
from backend.core.actor_context import ActorContext
from backend.core.prompt_resolver import get_content_locale, resolve_prompt
from backend.services.audit_service import AuditService

audit_service = AuditService()


class ProjectRequirementsService:
    def __init__(self):
        self._llm_handler = LLMHandler()

    async def list_audit_logs(
        self,
        project_id: int,
        session,
        actor_user_id: int | None = None,
        actor_type: str | None = None,
        action_type: str | None = None,
        target_type: str | None = None,
        task_id: int | None = None,
    ) -> list[AuditLogResponse]:
        """获取项目的全部审计日志，按创建时间降序排列，支持可选过滤"""
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.project_id == project_id)
            .options(selectinload(AuditLogModel.actor_user))
        )
        if actor_user_id is not None:
            stmt = stmt.where(AuditLogModel.actor_user_id == actor_user_id)
        if actor_type is not None:
            stmt = stmt.where(AuditLogModel.actor_type == actor_type)
        if action_type is not None:
            stmt = stmt.where(AuditLogModel.action_type == action_type)
        if target_type is not None:
            stmt = stmt.where(AuditLogModel.target_type == target_type)
        if task_id is not None:
            stmt = stmt.where(AuditLogModel.task_id == task_id)

        stmt = stmt.order_by(AuditLogModel.created_at.desc())
        result = await session.execute(stmt)
        logs = result.scalars().all()
        return [
            AuditLogResponse(
                id=log.id,
                project_id=str(log.project_id),
                action_type=log.action_type,
                summary=log.summary,
                target_type=log.target_type,
                target_id=log.target_id,
                payload=log.payload,
                created_at=log.created_at,
                updated_at=log.updated_at,
                actor_user_id=log.actor_user_id,
                actor_type=log.actor_type,
                actor_email=log.actor_user.email if log.actor_user else None,
                diff=log.diff,
                request_id=log.request_id,
                task_id=log.task_id,
            )
            for log in logs
        ]

    async def update_user_requirements(
        self,
        project_id: int,
        user_requirements: str,
        actor: ActorContext,
        session,
    ) -> UserRequirementsResponse:
        """直接更新项目的用户需求文本"""
        result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        old_requirements = project.user_requirements or ""
        project.user_requirements = user_requirements
        await session.flush()

        # 审计日志: 更新用户需求
        diff = {"user_requirements": {"before": old_requirements, "after": user_requirements}}
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_user_requirements",
            summary="手动更新用户需求文档",
            target_type="project",
            target_id=str(project_id),
            actor=actor,
            diff=diff,
        )

        return UserRequirementsResponse(
            project_id=str(project.public_id),
            user_requirements=project.user_requirements,
        )

    async def refine_user_requirements(
        self,
        project_id: int,
        user_feedback: str | None,
        actor: ActorContext,
        session,
    ) -> UserRequirementsResponse:
        """基于审计日志 and 用户反馈，使用LLM对需求文档进行精炼优化"""
        # 1. 加载当前项目的 user_requirements
        project_result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        current_requirements = project.user_requirements or ""

        # 2. 加载最近30条审计日志
        audit_result = await session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.project_id == project_id)
            .order_by(AuditLogModel.created_at.desc())
            .limit(30)
        )
        recent_logs = audit_result.scalars().all()

        # 3. 构建审计日志摘要
        audit_summary_lines = []
        for log in reversed(recent_logs):
            audit_summary_lines.append(
                f"- [{log.action_type}] {log.summary} (target: {log.target_type}#{log.target_id})"
            )
        locale = get_content_locale()
        audit_summary = "\n".join(audit_summary_lines) if audit_summary_lines else (
            "(none)" if locale == "en-US" else "（无）"
        )

        # 4. 构建LLM提示词
        prompt = resolve_prompt("requirements_refinement", locale).replace(
            "{{current_requirements}}", current_requirements
        ).replace("{{audit_summary}}", audit_summary)

        query = user_feedback or ""

        # 5. 调用LLM
        llm_result = await self._llm_handler.call_llm(
            prompt=prompt,
            query=query,
            protected_inputs=(current_requirements, user_feedback or ""),
        )

        if llm_result is None:
            raise ValueError("llm_refinement_failed")

        # 6. 更新项目需求
        project.user_requirements = llm_result
        await session.flush()

        # 7. 插入审计日志
        diff = {"user_requirements": {"before": current_requirements, "after": llm_result}}
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="refine_user_requirements",
            summary="通过LLM精炼优化用户需求文档",
            target_type="project",
            target_id=project_id,
            actor=actor,
            diff=diff,
        )

        return UserRequirementsResponse(
            project_id=str(project.public_id),
            user_requirements=project.user_requirements,
        )
