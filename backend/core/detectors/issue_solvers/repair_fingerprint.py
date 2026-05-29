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
    from backend.database.model import (
        ActorModel,
        FeatureModel,
        ScenarioModel,
        BusinessObjectModel,
        FlowModel,
        ScopeModel,
        feature_actor_table,
    )

    base = {"project_id": project_id, "target_type": target_type, "target_id": target_id}

    if target_type == "scope":
        from backend.database.model import FeatureModel
        res = await session.execute(
            select(ScopeModel).join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
            .where(ScopeModel.id == target_id, FeatureModel.project_id == project_id)
        )
        scope = res.scalar_one_or_none()
        if scope:
            base["reason"] = scope.reason
            base["status"] = scope.status
        return base

    if target_type == "feature":
        res = await session.execute(
            select(FeatureModel).where(FeatureModel.id == target_id, FeatureModel.project_id == project_id)
        )
        feature = res.scalar_one_or_none()
        if feature:
            base["name"] = feature.name
            base["description"] = feature.description
            actor_res = await session.execute(
                select(feature_actor_table.c.actor_id).where(
                    feature_actor_table.c.feature_id == feature.id
                )
            )
            base["actor_ids"] = [row[0] for row in actor_res.fetchall()]
        return base

    if target_type == "actor":
        res = await session.execute(
            select(ActorModel).where(ActorModel.id == target_id, ActorModel.project_id == project_id)
        )
        actor = res.scalar_one_or_none()
        if actor:
            base["name"] = actor.name
            base["description"] = actor.description
        return base

    if target_type == "scenario":
        res = await session.execute(
            select(ScenarioModel).where(ScenarioModel.id == target_id, ScenarioModel.project_id == project_id)
        )
        scenario = res.scalar_one_or_none()
        if scenario:
            base["name"] = scenario.name
            base["feature_id"] = scenario.feature_id
            base["actor_id"] = scenario.actor_id
        return base

    if target_type == "business_object":
        res = await session.execute(
            select(BusinessObjectModel).where(BusinessObjectModel.id == target_id, BusinessObjectModel.project_id == project_id)
        )
        bo = res.scalar_one_or_none()
        if bo:
            base["name"] = bo.name
        return base

    if target_type == "flow":
        res = await session.execute(
            select(FlowModel).where(FlowModel.id == target_id, FlowModel.project_id == project_id)
        )
        flow = res.scalar_one_or_none()
        if flow:
            base["name"] = flow.name
            base["description"] = flow.description
        return base

    # Fallback: return whatever we have
    return base
