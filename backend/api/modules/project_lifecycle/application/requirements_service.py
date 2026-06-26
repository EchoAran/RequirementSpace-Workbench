from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database.model import ProjectModel, AuditLogModel
from backend.api.modules.project_lifecycle.schemas.audit import (
    AuditLogResponse,
    UserRequirementsResponse,
)
from backend.services.LLM_service import LLMHandler


class ProjectRequirementsService:
    def __init__(self):
        self._llm_handler = LLMHandler()

    async def list_audit_logs(
        self,
        project_id: int,
        session,
    ) -> list[AuditLogResponse]:
        """获取项目的全部审计日志，按创建时间降序排列"""
        result = await session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.project_id == project_id)
            .order_by(AuditLogModel.created_at.desc())
        )
        logs = result.scalars().all()
        return [
            AuditLogResponse(
                id=log.id,
                project_id=log.project_id,
                action_type=log.action_type,
                summary=log.summary,
                target_type=log.target_type,
                target_id=log.target_id,
                payload=log.payload,
                created_at=log.created_at,
                updated_at=log.updated_at,
            )
            for log in logs
        ]

    async def update_user_requirements(
        self,
        project_id: int,
        user_requirements: str,
        session,
    ) -> UserRequirementsResponse:
        """直接更新项目的用户需求文本"""
        result = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = result.scalar_one_or_none()

        if project is None:
            raise ValueError("project_not_found")

        project.user_requirements = user_requirements
        await session.flush()

        # 审计日志: 更新用户需求
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_user_requirements",
            summary="手动更新用户需求文档",
            target_type="project",
            target_id=str(project_id),
            payload={},
        ))
        await session.flush()

        return UserRequirementsResponse(
            project_id=project.id,
            user_requirements=project.user_requirements,
        )

    async def refine_user_requirements(
        self,
        project_id: int,
        user_feedback: str | None,
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
        audit_summary = "\n".join(audit_summary_lines) if audit_summary_lines else "暂无变更记录"

        # 4. 构建LLM提示词
        prompt = (
            "你是一位专业的产品需求分析师。请根据以下信息，对产品需求文档（PRD）进行精炼和优化。\n\n"
            "## 当前需求文档\n"
            f"{current_requirements}\n\n"
            "## 最近的变更记录（审计日志）\n"
            f"{audit_summary}\n\n"
            "## 要求\n"
            "1. 综合考虑当前需求文档和变更记录，生成更新后的需求文档\n"
            "2. 确保变更记录中反映的修改都被纳入需求文档\n"
            "3. 保持需求文档的结构化和可读性\n"
            "4. 使用中文输出\n"
            "5. 直接输出优化后的需求文档内容，不要加额外的说明或包裹标记\n"
        )

        query = user_feedback or "请根据以上信息优化需求文档。"

        # 5. 调用LLM
        llm_result = await self._llm_handler.call_llm(
            prompt=prompt,
            query=query,
        )

        if llm_result is None:
            raise ValueError("llm_refinement_failed")

        # 6. 更新项目需求
        project.user_requirements = llm_result
        await session.flush()

        # 7. 插入审计日志
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="refine_user_requirements",
            summary="通过LLM精炼优化用户需求文档",
            target_type="project",
            target_id=str(project_id),
            payload={},
        ))
        await session.flush()

        return UserRequirementsResponse(
            project_id=project.id,
            user_requirements=project.user_requirements,
        )
