from sqlalchemy import select

from backend.api.modules.requirements_core.scope.schemas import ScopeResponse
from backend.database.model import FeatureModel, ScopeModel
from backend.services.binary_conversion_service import BinaryConversionService


async def load_existing_scope(
    session,
    project_id: int,
    feature_id: int,
    workspace_id: int,
):
    feature_stmt = select(FeatureModel).where(
        FeatureModel.project_id == project_id,
        FeatureModel.id == feature_id,
    )
    feature_stmt = feature_stmt.where(
        FeatureModel.workspace_id == workspace_id
    )
    feature_result = await session.execute(feature_stmt)
    if feature_result.scalar_one_or_none() is None:
        raise ValueError("feature_not_found")
    scope_result = await session.execute(
        select(ScopeModel).where(ScopeModel.feature_id == feature_id, ScopeModel.workspace_id == workspace_id)
    )
    return scope_result.scalar_one_or_none()


def capture_scope_state(scope) -> dict:
    return {
        "status": scope.status if scope else None,
        "reason": scope.reason if scope else None,
        "positive_summary": scope.positive_summary if scope else None,
        "negative_summary": scope.negative_summary if scope else None,
    }


def normalize_scope_status(status: str) -> str:
    aliases = {
        "本期": "current",
        "暂缓": "postponed",
        "排除": "exclude",
        "CURRENT": "current",
        "POSTPONED": "postponed",
        "EXCLUDE": "exclude",
    }
    return aliases.get(status, status).lower()


def upsert_scope(
    session,
    *,
    feature_id: int,
    scope,
    request,
    confirmation_status: str,
    workspace_id: int,
):
    normalized_status = normalize_scope_status(request.status)
    if scope is None:
        scope = ScopeModel(
            feature_id=feature_id,
            workspace_id=workspace_id,
            status=normalized_status,
            reason=request.reason,
            positive_summary=request.positive_summary,
            negative_summary=request.negative_summary,
            confirmation_status=confirmation_status,
        )
        session.add(scope)
        return scope
    scope.status = normalized_status
    scope.reason = request.reason
    if request.positive_summary is not None:
        scope.positive_summary = request.positive_summary
    if request.negative_summary is not None:
        scope.negative_summary = request.negative_summary
    return scope


def build_scope_update_diff(before: dict, scope) -> dict:
    after = capture_scope_state(scope)
    return {
        field: {"before": before[field], "after": value}
        for field, value in after.items()
        if before[field] != value
    }


def serialize_scope(scope) -> ScopeResponse:
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
