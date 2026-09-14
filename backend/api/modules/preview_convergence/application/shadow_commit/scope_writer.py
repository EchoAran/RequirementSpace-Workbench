from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
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
