from sqlalchemy import select
from backend.database.model import (
    ScopeModel,
    FeatureModel,
    AuditLogModel,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.api.schemas.crud_schema import (
    ScopeUpdateRequest,
    ScopeResponse,
)


class ScopeService:
    async def update_scope(
        self,
        project_id: int,
        feature_id: int,
        req: ScopeUpdateRequest,
        session,
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

        if scope is None:
            scope = ScopeModel(
                feature_id=feature_id,
                status=req.status,
                reason=req.reason,
                positive_summary=req.positive_summary,
                negative_summary=req.negative_summary,
            )
            session.add(scope)
        else:
            scope.status = req.status
            scope.reason = req.reason
            if req.positive_summary is not None:
                scope.positive_summary = req.positive_summary
            if req.negative_summary is not None:
                scope.negative_summary = req.negative_summary

        await session.flush()

        # 审计日志: 更新范围
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_scope",
            summary=f"手动更新功能范围: feature_id={feature_id}, status={scope.status}",
            target_type="scope",
            target_id=str(scope.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"scope"},
            session=session,
        )

        return ScopeResponse(
            scope_id=scope.id,
            feature_id=scope.feature_id,
            status=scope.status,
            reason=scope.reason,
            positive_summary=scope.positive_summary,
            negative_summary=scope.negative_summary,
        )
