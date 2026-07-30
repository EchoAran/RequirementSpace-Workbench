from sqlalchemy import select
from backend.database.model import (
    ScopeModel,
    FeatureModel,
    ConfirmationStatus,
)
from backend.services.audit_service import AuditService

audit_service = AuditService()
from backend.core.notifier import get_notifier
from backend.api.modules.requirements_core.scope.schemas import (
    ScopeUpdateRequest,
    ScopeResponse,
)
from .scope_writer import (
    build_scope_update_diff,
    capture_scope_state,
    load_existing_scope,
    serialize_scope,
    upsert_scope,
)


class ScopeService:
    async def update_scope(
        self,
        project_id: int,
        feature_id: int,
        req: ScopeUpdateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.AI_ASSUMPTION.value,
    ) -> ScopeResponse:
        scope = await load_existing_scope(
            session,
            project_id,
            feature_id,
        )

        if scope is not None:
            from backend.api.modules.collaboration.application.task_service import snapshot_service
            await snapshot_service.check_optimistic_lock(session, "scope", scope, req.last_seen_updated_at)

        before = capture_scope_state(scope)
        scope = upsert_scope(
            session,
            feature_id=feature_id,
            scope=scope,
            request=req,
            confirmation_status=confirmation_status,
        )

        await session.flush()

        # 审计日志: 更新范围
        diff = build_scope_update_diff(before, scope)

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_scope",
            summary=f"手动更新功能范围: feature_id={feature_id}, status={scope.status}",
            target_type="scope",
            target_id=scope.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"scope"},
            session=session,
        )

        from backend.api.modules.collaboration.application.task_service import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "scope", scope)

        return serialize_scope(scope)

    async def set_kano_status(
        self,
        project_id: int,
        status: str,
        session,
    ) -> dict:
        from backend.database.model import ProjectModel, ScopeModel, FeatureModel
        # Verify project exists
        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()
        if project is None:
            raise ValueError("project_not_found")

        project.kano_status = status

        if status == "missing":
            # Clear Kano-specific metrics and chart records but KEEP manual decisions status and reason
            feature_res = await session.execute(
                select(FeatureModel.id).where(FeatureModel.project_id == project_id)
            )
            feature_ids = feature_res.scalars().all()
            if feature_ids:
                scopes_res = await session.execute(
                    select(ScopeModel).where(ScopeModel.feature_id.in_(feature_ids))
                )
                scopes = scopes_res.scalars().all()
                for scope in scopes:
                    scope.kano_category = None
                    scope.kano_category_name = None
                    scope.positive_summary = None
                    scope.negative_summary = None
                    scope.positive_picture = None
                    scope.negative_picture = None

        await session.flush()

        # Audit Log
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="set_kano_status",
            summary=f"更新项目 Kano 分析状态为: {status}",
            target_type="project",
            target_id=project_id,
            diff={"kano_status": status},
            payload={"kano_status": status},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"scope"},
            session=session,
        )

        return {
            "project_id": project_id,
            "kano_status": status,
            "message": "kano_status_updated",
        }
