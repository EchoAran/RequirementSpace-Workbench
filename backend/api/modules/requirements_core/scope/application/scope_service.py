from sqlalchemy import select
from backend.database.model import (
    ScopeModel,
    FeatureModel,
    AuditLogModel,
    ConfirmationStatus,
)
from backend.services.audit_service import AuditService

audit_service = AuditService()
from backend.api.modules.requirements_core.ports import get_notifier
from backend.api.modules.requirements_core.scope.schemas import (
    ScopeUpdateRequest,
    ScopeResponse,
)
from backend.services.binary_conversion_service import BinaryConversionService


class ScopeService:
    async def update_scope(
        self,
        project_id: int,
        feature_id: int,
        req: ScopeUpdateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.AI_ASSUMPTION.value,
    ) -> ScopeResponse:
        # Verify feature belongs to project
        feature_res = await session.execute(
            select(FeatureModel).where(
                FeatureModel.project_id == project_id,
                FeatureModel.id == feature_id,
            )
        )
        if feature_res.scalar_one_or_none() is None:
            raise ValueError("feature_not_found")

        # Find or create ScopeModel for the Feature
        scope_res = await session.execute(
            select(ScopeModel).where(ScopeModel.feature_id == feature_id)
        )
        scope = scope_res.scalar_one_or_none()

        if scope is not None:
            from backend.api.modules.collaboration.application.task_service import snapshot_service
            await snapshot_service.check_optimistic_lock(session, "scope", scope, req.last_seen_updated_at)

        old_status = scope.status if scope else None
        old_reason = scope.reason if scope else None
        old_positive_summary = scope.positive_summary if scope else None
        old_negative_summary = scope.negative_summary if scope else None

        status_map = {
            "本期": "current",
            "暂缓": "postponed",
            "排除": "exclude",
            "CURRENT": "current",
            "POSTPONED": "postponed",
            "EXCLUDE": "exclude",
        }
        normalized_status = status_map.get(req.status, req.status).lower()

        if scope is None:
            scope = ScopeModel(
                feature_id=feature_id,
                status=normalized_status,
                reason=req.reason,
                positive_summary=req.positive_summary,
                negative_summary=req.negative_summary,
                confirmation_status=confirmation_status,
            )
            session.add(scope)
        else:
            scope.status = normalized_status
            scope.reason = req.reason
            if req.positive_summary is not None:
                scope.positive_summary = req.positive_summary
            if req.negative_summary is not None:
                scope.negative_summary = req.negative_summary

        await session.flush()

        # 审计日志: 更新范围
        diff = {}
        if old_status != scope.status:
            diff["status"] = {"before": old_status, "after": scope.status}
        if old_reason != scope.reason:
            diff["reason"] = {"before": old_reason, "after": scope.reason}
        if old_positive_summary != scope.positive_summary:
            diff["positive_summary"] = {"before": old_positive_summary, "after": scope.positive_summary}
        if old_negative_summary != scope.negative_summary:
            diff["negative_summary"] = {"before": old_negative_summary, "after": scope.negative_summary}

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

        return ScopeResponse(
            scope_id=scope.id,
            feature_id=scope.feature_id,
            status=scope.status,
            reason=scope.reason,
            positive_summary=scope.positive_summary,
            negative_summary=scope.negative_summary,
            positive_picture_base64=(
                BinaryConversionService.bytes_to_base64(scope.positive_picture)
                if scope.positive_picture is not None
                else None
            ),
            negative_picture_base64=(
                BinaryConversionService.bytes_to_base64(scope.negative_picture)
                if scope.negative_picture is not None
                else None
            ),
            kano_category=scope.kano_category,
            kano_category_name=scope.kano_category_name,
            confirmation_status=scope.confirmation_status,
        )

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
