from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database.model import (
    ConfirmationStatus,
    FeatureModel,
    FeatureRelationModel,
)
from backend.services.audit_service import AuditService

audit_service = AuditService()
from backend.api.modules.requirements_core.feature.schemas import (
    FeatureCreateRequest,
    FeatureResponse,
    FeatureUpdateRequest,
)
from backend.core.notifier import get_notifier

from .feature_writer import (
    apply_feature_updates,
    build_feature_update_diff,
    capture_feature_state,
    create_feature_parent_relation,
    ensure_parent_feature_exists,
    load_feature_for_update,
    serialize_created_feature,
    serialize_feature,
)


class FeatureService:
    async def list_features(self, project_id: int, session, workspace_id: int | None = None) -> list[FeatureResponse]:
        stmt = (
            select(FeatureModel)
            .where(FeatureModel.project_id == project_id)
            .options(
                selectinload(FeatureModel.actors),
                selectinload(FeatureModel.parent_relation),
                selectinload(FeatureModel.child_relations),
            )
        )
        if workspace_id is not None:
            stmt = stmt.where(FeatureModel.workspace_id == workspace_id)
        result = await session.execute(stmt)
        features = result.scalars().all()
        return [
            FeatureResponse(
                feature_id=feature.id,
                name=feature.name,
                description=feature.description,
                parent_id=(
                    feature.parent_relation.parent_feature_id
                    if feature.parent_relation
                    else None
                ),
                child_ids=[rel.child_feature_id for rel in feature.child_relations],
                actor_ids=[actor.id for actor in feature.actors],
            )
            for feature in features
        ]

    async def get_features(self, project_id: int, session, workspace_id: int | None = None) -> list[FeatureResponse]:
        """Backward-compatible shim for list_features."""
        return await self.list_features(project_id, session, workspace_id)

    async def create_feature(
        self,
        project_id: int,
        req: FeatureCreateRequest,
        session,
        confirmation_status: str = ConfirmationStatus.NEEDS_CONFIRMATION.value,
        workspace_id: int | None = None,
    ) -> FeatureResponse:
        await ensure_parent_feature_exists(
            session,
            project_id,
            req.parent_id,
        )

        if workspace_id is not None and req.parent_id:
            exec_res = session.execute(select(FeatureModel).where(FeatureModel.id == req.parent_id))
            parent_feat = (await exec_res if hasattr(exec_res, "__await__") else exec_res).scalar_one_or_none()
            if parent_feat and parent_feat.workspace_id != workspace_id:
                raise ValueError("Cross-workspace entity reference rejected: parent feature belongs to a different workspace")

        feature = FeatureModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=req.name,
            description=req.description,
            confirmation_status=confirmation_status,
        )
        session.add(feature)
        flush_res = session.flush()
        if hasattr(flush_res, "__await__"):
            await flush_res

        await create_feature_parent_relation(
            session,
            req.parent_id,
            feature.id,
        )

        # 审计日志: 新增功能
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="create_feature",
            summary=f"手动新增功能: {feature.name}",
            target_type="feature",
            target_id=feature.id,
            diff={"name": feature.name, "description": feature.description, "confirmation_status": confirmation_status},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what", "how", "scope"},
            perception_kinds={
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            },
            session=session,
            workspace_id=workspace_id,
        )

        return serialize_created_feature(feature, req.parent_id)

    async def update_feature(
        self,
        project_id: int,
        feature_id: int,
        req: FeatureUpdateRequest,
        session,
        workspace_id: int | None = None,
    ) -> FeatureResponse:
        feature = await load_feature_for_update(
            session,
            project_id,
            feature_id,
        )
        if workspace_id is not None and feature.workspace_id != workspace_id:
            raise ValueError("feature_not_found_in_workspace")

        parent_id_val = getattr(req, "parent_id", None)
        if workspace_id is not None and parent_id_val:
            exec_res = session.execute(select(FeatureModel).where(FeatureModel.id == parent_id_val))
            parent_feat = (await exec_res if hasattr(exec_res, "__await__") else exec_res).scalar_one_or_none()
            if parent_feat and parent_feat.workspace_id != workspace_id:
                raise ValueError("Cross-workspace entity reference rejected: parent feature belongs to a different workspace")

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.check_optimistic_lock(session, "feature", feature, req.last_seen_updated_at)

        before = capture_feature_state(feature)
        await apply_feature_updates(
            session,
            project_id,
            feature,
            req,
        )

        flush_res = session.flush()
        if hasattr(flush_res, "__await__"):
            await flush_res

        # 审计日志: 更新功能
        diff = build_feature_update_diff(before, feature)

        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_feature",
            summary=f"手动更新功能: {feature.name}",
            target_type="feature",
            target_id=feature.id,
            diff=diff,
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what", "how", "scope"},
            perception_kinds={
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            },
            session=session,
            workspace_id=workspace_id,
        )

        from backend.api.modules.optimistic_lock.public import snapshot_service
        await snapshot_service.supersede_tasks_on_node_update(session, "feature", feature)

        return serialize_feature(feature)

    async def delete_feature(
        self,
        project_id: int,
        feature_id: int,
        session,
        workspace_id: int | None = None,
    ) -> dict:
        stmt = select(FeatureModel).where(
            FeatureModel.project_id == project_id,
            FeatureModel.id == feature_id,
        )
        if workspace_id is not None:
            stmt = stmt.where(FeatureModel.workspace_id == workspace_id)
        exec_res = session.execute(stmt)
        feature = (await exec_res if hasattr(exec_res, "__await__") else exec_res).scalar_one_or_none()

        if feature is None:
            raise ValueError("feature_not_found_in_workspace")

        feature_name = feature.name

        # Recursively delete all children features to maintain logical cascade
        await self._delete_feature_recursive(feature_id, session)

        # 审计日志: 删除功能
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="delete_feature",
            summary=f"手动删除功能: {feature_name}",
            target_type="feature",
            target_id=feature_id,
            diff={"status": "deleted"},
        )

        await get_notifier().mark_stale(
            project_id=project_id,
            stages={"what", "how", "scope"},
            perception_kinds={
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            },
            session=session,
            workspace_id=workspace_id,
        )

        return {
            "feature_id": feature_id,
            "message": "feature_deleted",
        }

    async def _delete_feature_recursive(self, feature_id: int, session) -> None:
        child_relation_result = await session.execute(
            select(FeatureRelationModel.child_feature_id).where(
                FeatureRelationModel.parent_feature_id == feature_id
            )
        )
        child_ids = child_relation_result.scalars().all()

        for child_id in child_ids:
            await self._delete_feature_recursive(child_id, session)

        feature_result = await session.execute(
            select(FeatureModel).where(FeatureModel.id == feature_id)
        )
        feature = feature_result.scalar_one_or_none()
        if feature is not None:
            await session.delete(feature)
        await session.flush()
