from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
    FeatureModel,
    FeatureRelationModel,
    ScopeModel,
)

from .common import _CommitIdMaps


def _decode_scope_pictures(scope_data: dict) -> tuple[bytes | None, bytes | None]:
    from backend.services.binary_conversion_service import (
        BinaryConversionService,
    )

    positive_picture = (
        BinaryConversionService.base64_to_bytes(
            scope_data.get("positive_picture_base64")
        )
        if scope_data.get("positive_picture_base64")
        else None
    )
    negative_picture = (
        BinaryConversionService.base64_to_bytes(
            scope_data.get("negative_picture_base64")
        )
        if scope_data.get("negative_picture_base64")
        else None
    )
    return positive_picture, negative_picture

def _update_scope(
    scope: ScopeModel,
    scope_data: dict,
    positive_picture: bytes | None,
    negative_picture: bytes | None,
) -> None:
    scope.status = scope_data["status"]
    scope.reason = scope_data["reason"]
    scope.kano_category = scope_data.get("kano_category")
    scope.kano_category_name = scope_data.get("kano_category_name")
    scope.positive_summary = scope_data.get("positive_summary")
    scope.negative_summary = scope_data.get("negative_summary")
    if positive_picture is not None:
        scope.positive_picture = positive_picture
    if negative_picture is not None:
        scope.negative_picture = negative_picture

async def _upsert_scopes(
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for scope_data in patch.get("scopes_added", []):
        feature_id = id_maps.resolve_feature(scope_data["feature_ref"])
        result = await session.execute(
            select(ScopeModel).where(ScopeModel.feature_id == feature_id)
        )
        existing_scope = result.scalar_one_or_none()
        positive_picture, negative_picture = _decode_scope_pictures(
            scope_data
        )
        if existing_scope:
            _update_scope(
                existing_scope,
                scope_data,
                positive_picture,
                negative_picture,
            )
            continue
        session.add(
            ScopeModel(
                feature_id=feature_id,
                status=scope_data["status"],
                reason=scope_data["reason"],
                kano_category=scope_data.get("kano_category"),
                kano_category_name=scope_data.get("kano_category_name"),
                positive_summary=scope_data.get("positive_summary"),
                negative_summary=scope_data.get("negative_summary"),
                positive_picture=positive_picture,
                negative_picture=negative_picture,
            )
        )
        await session.flush()

async def _load_missing_leaf_ids(
    project_id: int,
    session: AsyncSession,
) -> list[int]:
    feature_result = await session.execute(
        select(FeatureModel).where(FeatureModel.project_id == project_id)
    )
    features = feature_result.scalars().all()
    feature_ids = [feature.id for feature in features]
    if not feature_ids:
        return []
    relation_result = await session.execute(
        select(FeatureRelationModel).where(
            FeatureRelationModel.parent_feature_id.in_(feature_ids)
        )
    )
    relations = relation_result.scalars().all()
    parent_ids = {relation.parent_feature_id for relation in relations}
    leaf_features = [
        feature for feature in features if feature.id not in parent_ids
    ]
    scope_result = await session.execute(
        select(ScopeModel).where(ScopeModel.feature_id.in_(feature_ids))
    )
    existing_scopes = scope_result.scalars().all()
    scoped_feature_ids = {scope.feature_id for scope in existing_scopes}
    return [
        feature.id
        for feature in leaf_features
        if feature.id not in scoped_feature_ids
    ]

def _create_generated_scope(scope_data: dict) -> ScopeModel:
    positive_picture, negative_picture = _decode_scope_pictures(scope_data)
    return ScopeModel(
        feature_id=scope_data.get("feature_id"),
        status=scope_data.get("scope_status", "current").upper(),
        reason=scope_data.get("reason", "AI影子收敛补充"),
        kano_category=scope_data.get("kano_category"),
        kano_category_name=scope_data.get("kano_category_name"),
        positive_summary=scope_data.get("positive_summary"),
        negative_summary=scope_data.get("negative_summary"),
        positive_picture=positive_picture,
        negative_picture=negative_picture,
    )

async def _ensure_leaf_scopes(
    project_id: int,
    session: AsyncSession,
) -> None:
    missing_leaf_ids = await _load_missing_leaf_ids(project_id, session)
    if not missing_leaf_ids:
        return
    from backend.api.modules.requirements_core.ports import (
        get_scope_generation_service,
    )

    scope_generation_service = get_scope_generation_service()
    draft_payload, _ = await scope_generation_service._generate_preview(
        project_id=project_id,
        user_feedback=None,
        session=session,
    )
    for scope_data in draft_payload.get("scopes", []):
        feature_id = scope_data.get("feature_id")
        if feature_id in missing_leaf_ids:
            session.add(_create_generated_scope(scope_data))
            missing_leaf_ids.remove(feature_id)
    for feature_id in missing_leaf_ids:
        session.add(
            ScopeModel(
                feature_id=feature_id,
                status="CURRENT",
                reason="AI影子收敛补充",
                kano_category="M",
                kano_category_name="Must-be",
            )
        )
    await session.flush()
