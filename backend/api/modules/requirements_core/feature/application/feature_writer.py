from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.api.modules.requirements_core.feature.schemas import (
    FeatureResponse,
)
from backend.database.model import (
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
)


async def ensure_parent_feature_exists(
    session,
    project_id: int,
    parent_id: int | None,
) -> None:
    if parent_id is None:
        return
    result = await session.execute(select(FeatureModel).where(
            FeatureModel.project_id == project_id,
            FeatureModel.id == parent_id,
        ))
    if result.scalar_one_or_none() is None:
        raise ValueError("parent_feature_not_found")


async def create_feature_parent_relation(
    session,
    parent_id: int | None,
    child_id: int,
    workspace_id: int,
) -> None:
    if parent_id is None:
        return
    result = await session.execute(select(func.max(FeatureRelationModel.position)).where(
            FeatureRelationModel.parent_feature_id == parent_id
        ))
    maximum = result.scalar()
    session.add(
        FeatureRelationModel(
            workspace_id=workspace_id,
            parent_feature_id=parent_id,
            child_feature_id=child_id,
            position=0 if maximum is None else maximum + 1,
        )
    )
    await session.flush()


async def load_feature_for_update(
    session,
    project_id: int,
    feature_id: int,
):
    result = await session.execute(select(FeatureModel)
        .where(
            FeatureModel.project_id == project_id,
            FeatureModel.id == feature_id,
        )
        .options(
            selectinload(FeatureModel.actors),
            selectinload(FeatureModel.parent_relation),
            selectinload(FeatureModel.child_relations),
        ))
    feature = result.scalar_one_or_none()
    if feature is None:
        raise ValueError("feature_not_found")
    return feature


def capture_feature_state(feature) -> dict:
    return {
        "name": feature.name,
        "description": feature.description,
        "actor_ids": [actor.id for actor in feature.actors],
    }


async def apply_feature_updates(
    session,
    project_id: int,
    feature,
    request,
) -> None:
    if request.name is not None:
        feature.name = request.name
    if request.description is not None:
        feature.description = request.description
    if request.actor_ids is None:
        return
    if not request.actor_ids:
        feature.actors = []
        return
    result = await session.execute(select(ActorModel).where(
            ActorModel.project_id == project_id,
            ActorModel.workspace_id == feature.workspace_id,
            ActorModel.id.in_(request.actor_ids),
        ))
    actors = result.scalars().all()
    if len(actors) != len(request.actor_ids):
        raise ValueError("invalid_actor_reference")
    feature.actors = actors


def build_feature_update_diff(before: dict, feature) -> dict:
    after = capture_feature_state(feature)
    return {
        field: {"before": before[field], "after": value}
        for field, value in after.items()
        if before[field] != value
    }


def serialize_feature(feature) -> FeatureResponse:
    return FeatureResponse(
        feature_id=feature.id,
        name=feature.name,
        description=feature.description,
        parent_id=(
            feature.parent_relation.parent_feature_id
            if feature.parent_relation
            else None
        ),
        child_ids=[
            relation.child_feature_id
            for relation in feature.child_relations
        ],
        actor_ids=[actor.id for actor in feature.actors],
        confirmation_status=feature.confirmation_status,
    )


def serialize_created_feature(
    feature,
    parent_id: int | None,
) -> FeatureResponse:
    return FeatureResponse(
        feature_id=feature.id,
        name=feature.name,
        description=feature.description,
        parent_id=parent_id,
        child_ids=[],
        actor_ids=[],
        confirmation_status=feature.confirmation_status,
    )
