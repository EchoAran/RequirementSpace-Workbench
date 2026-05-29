from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from backend.database.model import (
    FeatureModel,
    FeatureRelationModel,
    ActorModel,
    AuditLogModel,
)
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.api.schemas.crud_schema import (
    FeatureCreateRequest,
    FeatureUpdateRequest,
    FeatureResponse,
)


class FeatureService:
    async def get_features(self, project_id: int, session) -> list[FeatureResponse]:
        result = await session.execute(
            select(FeatureModel)
            .where(FeatureModel.project_id == project_id)
            .options(
                selectinload(FeatureModel.actors),
                selectinload(FeatureModel.parent_relation),
                selectinload(FeatureModel.child_relations),
            )
        )
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

    async def create_feature(
        self,
        project_id: int,
        req: FeatureCreateRequest,
        session,
    ) -> FeatureResponse:
        # If parent_id is provided, verify parent exists
        if req.parent_id is not None:
            parent_result = await session.execute(
                select(FeatureModel).where(
                    FeatureModel.project_id == project_id,
                    FeatureModel.id == req.parent_id,
                )
            )
            if parent_result.scalar_one_or_none() is None:
                raise ValueError("parent_feature_not_found")

        feature = FeatureModel(
            project_id=project_id,
            name=req.name,
            description=req.description,
        )
        session.add(feature)
        await session.flush()

        # Insert relation if parent is provided
        if req.parent_id is not None:
            pos_result = await session.execute(
                select(func.count(FeatureRelationModel.id)).where(
                    FeatureRelationModel.parent_feature_id == req.parent_id
                )
            )
            position = pos_result.scalar() or 0

            relation = FeatureRelationModel(
                parent_feature_id=req.parent_id,
                child_feature_id=feature.id,
                position=position,
            )
            session.add(relation)
            await session.flush()

        # 审计日志: 新增功能
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="create_feature",
            summary=f"手动新增功能: {feature.name}",
            target_type="feature",
            target_id=str(feature.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what", "how", "scope"},
            perception_kinds={
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            },
            session=session,
        )

        # Reload with relations to build Response
        reload_result = await session.execute(
            select(FeatureModel)
            .where(FeatureModel.id == feature.id)
            .options(
                selectinload(FeatureModel.actors),
                selectinload(FeatureModel.parent_relation),
                selectinload(FeatureModel.child_relations),
            )
        )
        loaded = reload_result.scalar_one()

        return FeatureResponse(
            feature_id=loaded.id,
            name=loaded.name,
            description=loaded.description,
            parent_id=(
                loaded.parent_relation.parent_feature_id
                if loaded.parent_relation
                else None
            ),
            child_ids=[rel.child_feature_id for rel in loaded.child_relations],
            actor_ids=[actor.id for actor in loaded.actors],
        )

    async def update_feature(
        self,
        project_id: int,
        feature_id: int,
        req: FeatureUpdateRequest,
        session,
    ) -> FeatureResponse:
        result = await session.execute(
            select(FeatureModel)
            .where(
                FeatureModel.project_id == project_id,
                FeatureModel.id == feature_id,
            )
            .options(
                selectinload(FeatureModel.actors),
                selectinload(FeatureModel.parent_relation),
                selectinload(FeatureModel.child_relations),
            )
        )
        feature = result.scalar_one_or_none()

        if feature is None:
            raise ValueError("feature_not_found")

        if req.name is not None:
            feature.name = req.name
        if req.description is not None:
            feature.description = req.description

        if req.actor_ids is not None:
            if req.actor_ids:
                actors_result = await session.execute(
                    select(ActorModel).where(
                        ActorModel.project_id == project_id,
                        ActorModel.id.in_(req.actor_ids),
                    )
                )
                actor_models = actors_result.scalars().all()
                if len(actor_models) != len(req.actor_ids):
                    raise ValueError("invalid_actor_reference")
                feature.actors = actor_models
            else:
                feature.actors = []

        await session.flush()

        # 审计日志: 更新功能
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="update_feature",
            summary=f"手动更新功能: {feature.name}",
            target_type="feature",
            target_id=str(feature.id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what", "how", "scope"},
            perception_kinds={
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            },
            session=session,
        )

        return FeatureResponse(
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

    async def delete_feature(
        self,
        project_id: int,
        feature_id: int,
        session,
    ) -> dict:
        result = await session.execute(
            select(FeatureModel).where(
                FeatureModel.project_id == project_id,
                FeatureModel.id == feature_id,
            )
        )
        feature = result.scalar_one_or_none()

        if feature is None:
            raise ValueError("feature_not_found")

        feature_name = feature.name

        # Recursively delete all children features to maintain logical cascade
        await self._delete_feature_recursive(feature_id, session)

        # 审计日志: 删除功能
        session.add(AuditLogModel(
            project_id=project_id,
            action_type="delete_feature",
            summary=f"手动删除功能: {feature_name}",
            target_type="feature",
            target_id=str(feature_id),
            payload={},
        ))

        await mark_perception_jobs_stale(
            project_id=project_id,
            stages={"what", "how", "scope"},
            perception_kinds={
                "FEATURE",
                "SCENARIO",
                "ACCEPTANCE_CRITERION",
                "FLOW",
            },
            session=session,
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
