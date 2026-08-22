"""Shared utilities for issue fingerprint and context hash computation.

Used by:
- IssueRepairService.resolve() to generate fingerprint/hash at resolve time.
- IssueRepairDraftService.confirm_draft() to recompute hash and detect staleness.
"""

import hashlib
import json

from sqlalchemy import select


def build_issue_fingerprint(
    stage: str,
    issue_code: str,
    target_type: str | None,
    target_id: int | str | None,
    parent_type: str | None = None,
    parent_id: int | str | None = None,
) -> str:
    """Deterministic identifier for an issue instance.

    Does not include context-dependent data (entity names, descriptions, etc.)
    so two identical structural problems produce the same fingerprint.
    """
    parts = [stage, issue_code, target_type or "none", str(target_id) if target_id is not None else "none"]
    if parent_type is not None:
        parts.extend([parent_type, str(parent_id) if parent_id is not None else "none"])
    return ":".join(parts)


def compute_context_hash(snapshot: dict) -> str:
    """SHA256 of the canonical JSON representation of a context snapshot.

    The snapshot must be a dict of entity data that, given the same project
    state, serializes to the same JSON.  Keys are sorted to ensure
    cross-platform determinism.
    """
    raw = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def load_target_entity_snapshot(
    project_id: int,
    target_type: str,
    target_id: int,
    session,
) -> dict:
    """Load relevant fields from the target entity for context hashing.

    Only the fields that matter for staleness detection are included:
    - For scope: reason, status
    - For feature: name, actor_ids
    - For scenario: name, feature_id, actor_id
    - etc.
    """
    base = {"project_id": project_id, "target_type": target_type, "target_id": target_id}
    loader = {
        "scope": _load_scope_snapshot,
        "feature": _load_feature_snapshot,
        "actor": _load_actor_snapshot,
        "scenario": _load_scenario_snapshot,
        "business_object": _load_business_object_snapshot,
        "flow": _load_flow_snapshot,
    }.get(target_type)
    if loader is not None:
        await loader(project_id, target_id, base, session)
    return base


async def _load_scope_snapshot(
    project_id: int,
    target_id: int,
    snapshot: dict,
    session,
) -> None:
    from backend.database.model import FeatureModel, ScopeModel

    result = await session.execute(
        select(ScopeModel).join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
        .where(ScopeModel.id == target_id, FeatureModel.project_id == project_id)
    )
    scope = result.scalar_one_or_none()
    if scope:
        snapshot["reason"] = scope.reason
        snapshot["status"] = scope.status


async def _load_feature_snapshot(
    project_id: int,
    target_id: int,
    snapshot: dict,
    session,
) -> None:
    from backend.database.model import FeatureModel, feature_actor_table

    result = await session.execute(
        select(FeatureModel).where(
            FeatureModel.id == target_id,
            FeatureModel.project_id == project_id,
        )
    )
    feature = result.scalar_one_or_none()
    if not feature:
        return
    snapshot["name"] = feature.name
    snapshot["description"] = feature.description
    actor_result = await session.execute(
        select(feature_actor_table.c.actor_id).where(
            feature_actor_table.c.feature_id == feature.id
        )
    )
    snapshot["actor_ids"] = [row[0] for row in actor_result.fetchall()]


async def _load_actor_snapshot(
    project_id: int,
    target_id: int,
    snapshot: dict,
    session,
) -> None:
    from backend.database.model import ActorModel

    result = await session.execute(
        select(ActorModel).where(
            ActorModel.id == target_id,
            ActorModel.project_id == project_id,
        )
    )
    actor = result.scalar_one_or_none()
    if actor:
        snapshot["name"] = actor.name
        snapshot["description"] = actor.description


async def _load_scenario_snapshot(
    project_id: int,
    target_id: int,
    snapshot: dict,
    session,
) -> None:
    from backend.database.model import ScenarioModel

    result = await session.execute(
        select(ScenarioModel).where(
            ScenarioModel.id == target_id,
            ScenarioModel.project_id == project_id,
        )
    )
    scenario = result.scalar_one_or_none()
    if scenario:
        snapshot["name"] = scenario.name
        snapshot["feature_id"] = scenario.feature_id
        snapshot["actor_id"] = scenario.actor_id


async def _load_business_object_snapshot(
    project_id: int,
    target_id: int,
    snapshot: dict,
    session,
) -> None:
    from backend.database.model import BusinessObjectModel

    result = await session.execute(
        select(BusinessObjectModel).where(
            BusinessObjectModel.id == target_id,
            BusinessObjectModel.project_id == project_id,
        )
    )
    business_object = result.scalar_one_or_none()
    if business_object:
        snapshot["name"] = business_object.name


async def _load_flow_snapshot(
    project_id: int,
    target_id: int,
    snapshot: dict,
    session,
) -> None:
    from backend.database.model import FlowModel

    result = await session.execute(
        select(FlowModel).where(
            FlowModel.id == target_id,
            FlowModel.project_id == project_id,
        )
    )
    flow = result.scalar_one_or_none()
    if flow:
        snapshot["name"] = flow.name
        snapshot["description"] = flow.description
