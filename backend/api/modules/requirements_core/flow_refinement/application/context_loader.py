"""Scoped context loader for bounded flow refinement."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.modules.requirements_core.flow.application.path_projection_service import (
    PathProjectionService,
)
from backend.core.findings.how_finding_policy import HowFindingPolicy
from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    DomainRuleModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
    ScenarioModel,
)


@dataclass
class FlowRefinementContext:
    """Scoped refinement context describing the anchor flow and related evidence."""
    project_id: int
    workspace_id: int
    target_flow_id: int
    target_flow_logical_uuid: str
    target_flow_name: str
    target_flow_description: str
    anchor_kind: str
    anchor_id: int
    anchor_step: dict[str, Any] | None
    existing_steps: list[dict[str, Any]]
    existing_transitions: list[dict[str, Any]]
    path_projection: dict[str, Any]
    linked_requirements: dict[str, Any]
    applicable_rules: list[dict[str, Any]]
    business_objects: list[dict[str, Any]]
    actors: list[dict[str, Any]]
    allowed_step_positions: set[int] | None
    allowed_step_uuids: set[str] | None
    allowed_transition_uuids: set[str] | None
    allowed_actor_ids: set[int]
    allowed_bo_ids: set[int]
    allowed_bo_numbers: set[str] | None = None
    context_feature_uuids: set[str] = field(default_factory=set)
    context_scenario_uuids: set[str] = field(default_factory=set)
    context_knowledge_uuids: set[str] = field(default_factory=set)
    finding_context: str | None = None
    focus_text: str | None = None
    context_hash: str = ""
    knowledge_fragments: list[dict[str, Any]] = field(default_factory=list)


def compute_refinement_context_hash(
    flow_uuid: str,
    flow_name: str,
    steps: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    *,
    flow_description: str = "",
    features: list[dict[str, Any]] | None = None,
    actors: list[dict[str, Any]] | None = None,
    business_objects: list[dict[str, Any]] | None = None,
    finding_context: str | None = None,
    knowledge_fragments: list[dict[str, Any]] | None = None,
) -> str:
    """Compute deterministic hash representing current flow state and all applicable context."""
    data = {
        "flow_uuid": str(flow_uuid or ""),
        "flow_name": (flow_name or "").strip(),
        "flow_description": (flow_description or "").strip(),
        "steps": sorted(
            [
                {
                    "pos": s.get("position"),
                    "name": (s.get("name") or "").strip(),
                    "desc": (s.get("description") or "").strip(),
                    "type": s.get("step_type"),
                    "status": s.get("confirmation_status", "ai_assumption"),
                    "actor_ids": sorted(s.get("actor_ids") or []),
                    "input_bo_ids": sorted(s.get("input_business_object_ids") or []),
                    "output_bo_ids": sorted(s.get("output_business_object_ids") or []),
                }
                for s in steps
            ],
            key=lambda x: str(x.get("pos")),
        ),
        "transitions": sorted(
            [
                {
                    "uuid": str(t.get("logical_uuid") or ""),
                    "src": t.get("source_step_position"),
                    "tgt": t.get("target_step_position"),
                    "label": (t.get("label") or "").strip(),
                    "cond": (t.get("condition_text") or "").strip(),
                    "is_default": bool(t.get("is_default", False)),
                    "tags": sorted(t.get("semantic_tags") or []),
                    "rule_refs": sorted(t.get("rule_refs") or []),
                }
                for t in transitions
            ],
            key=lambda x: str(x.get("uuid")),
        ),
        "rules": sorted(
            [
                {
                    "uuid": str(r.get("logical_uuid") or ""),
                    "title": (r.get("title") or "").strip(),
                    "statement": (r.get("statement") or "").strip(),
                    "parent_uuid": str(r.get("parent_rule_uuid") or ""),
                    "status": str(r.get("confirmation_status") or "ai_assumption"),
                    "origin": str(r.get("origin") or "manual"),
                    "links": sorted([
                        f"{link.get('target_kind')}:{link.get('target_logical_uuid')}:{link.get('link_purpose')}"
                        for link in r.get("links", [])
                    ]),
                }
                for r in rules
            ],
            key=lambda x: str(x.get("uuid")),
        ),
        "scenarios": sorted(
            [
                {
                    "uuid": str(sc.get("logical_uuid") or ""),
                    "name": (sc.get("name") or "").strip(),
                    "description": (sc.get("description") or "").strip(),
                    "content": (sc.get("content") or "").strip(),
                    "ac": sorted([
                        (a.get("content") if isinstance(a, dict) else str(a) or "").strip()
                        for a in sc.get("acceptance_criteria", [])
                    ]),
                }
                for sc in scenarios
            ],
            key=lambda x: str(x.get("uuid")),
        ),
        "features": sorted(
            [
                {
                    "id": f.get("id"),
                    "uuid": str(f.get("logical_uuid") or ""),
                    "name": (f.get("name") or "").strip(),
                    "desc": (f.get("description") or "").strip(),
                }
                for f in (features or [])
            ],
            key=lambda x: str(x.get("id")),
        ),
        "actors": sorted(
            [
                {
                    "id": a.get("id"),
                    "uuid": str(a.get("logical_uuid") or ""),
                    "name": (a.get("name") or "").strip(),
                    "desc": (a.get("description") or "").strip(),
                }
                for a in (actors or [])
            ],
            key=lambda x: str(x.get("id")),
        ),
        "business_objects": sorted(
            [
                {
                    "id": b.get("id"),
                    "number": str(b.get("number") or ""),
                    "uuid": str(b.get("logical_uuid") or ""),
                    "name": (b.get("name") or "").strip(),
                    "desc": (b.get("description") or "").strip(),
                    "attributes": sorted(
                        [
                            {
                                "name": (attribute.get("name") or "").strip(),
                                "data_type": (attribute.get("data_type") or "").strip(),
                                "description": (attribute.get("description") or "").strip(),
                            }
                            for attribute in b.get("attributes", [])
                        ],
                        key=lambda attribute: (attribute["name"], attribute["data_type"], attribute["description"]),
                    ),
                }
                for b in (business_objects or [])
            ],
            key=lambda x: str(x.get("id")),
        ),
        "finding_context": (finding_context or "").strip(),
        "knowledge": sorted(
            [
                {
                    "id": str(k.get("fragment_id") or k.get("logical_uuid") or ""),
                    "content": (k.get("content") or "").strip(),
                }
                for k in (knowledge_fragments or [])
            ],
            key=lambda x: str(x.get("id")),
        ),
    }
    raw_bytes = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


async def load_flow_refinement_context(
    session: AsyncSession,
    project_id: int,
    target_kind: str,
    target_id: int,
    workspace_id: int,
    focus_text: str | None = None,
    source_finding_id: str | int | None = None,
) -> FlowRefinementContext:
    """Load tightly scoped context for target flow or step."""
    # The target flow defines the outer refinement boundary.
    anchor_step_data = None
    if target_kind == "flow_step":
        step_stmt = select(FlowStepModel).where(
            FlowStepModel.id == target_id,
            FlowStepModel.workspace_id == workspace_id,
        )
        step_res = await session.execute(step_stmt)
        step = step_res.scalar_one_or_none()
        if not step:
            raise ValueError("flow_step_not_found")
        target_flow_id = step.flow_id
        anchor_step_data = {
            "step_id": step.id,
            "logical_uuid": step.logical_uuid,
            "position": step.position,
            "name": step.name,
            "description": step.description,
            "step_type": step.step_type,
        }
    elif target_kind == "flow":
        target_flow_id = target_id
    else:
        raise ValueError(f"unsupported_target_kind: {target_kind}")

    flow_stmt = select(FlowModel).where(
        FlowModel.id == target_flow_id,
        FlowModel.project_id == project_id,
        FlowModel.workspace_id == workspace_id,
    ).options(selectinload(FlowModel.features))
    flow_res = await session.execute(flow_stmt)
    flow = flow_res.scalar_one_or_none()
    if not flow:
        raise ValueError("flow_not_found")

    # Step context includes only its bound actors and business objects.
    steps_stmt = select(FlowStepModel).where(
        FlowStepModel.flow_id == flow.id,
        FlowStepModel.workspace_id == workspace_id,
    ).options(
        selectinload(FlowStepModel.actors),
        selectinload(FlowStepModel.input_business_objects),
        selectinload(FlowStepModel.output_business_objects),
    ).order_by(FlowStepModel.position.asc())
    steps_rows = (await session.execute(steps_stmt)).scalars().all()

    existing_steps = [
        {
            "step_id": s.id,
            "logical_uuid": s.logical_uuid,
            "position": s.position,
            "name": s.name,
            "description": s.description,
            "step_type": s.step_type,
            "confirmation_status": s.confirmation_status,
            "actor_ids": [a.id for a in s.actors],
            "actor_names": [a.name for a in s.actors],
            "input_business_object_ids": [bo.id for bo in s.input_business_objects],
            "input_business_object_names": [bo.name for bo in s.input_business_objects],
            "output_business_object_ids": [bo.id for bo in s.output_business_objects],
            "output_business_object_names": [bo.name for bo in s.output_business_objects],
        }
        for s in steps_rows
    ]

    # Transitions preserve the semantic topology supplied to refinement.
    transitions_stmt = select(FlowTransitionModel).where(
        FlowTransitionModel.flow_id == flow.id,
        FlowTransitionModel.project_id == project_id,
        FlowTransitionModel.workspace_id == workspace_id,
    ).options(
        selectinload(FlowTransitionModel.source_step),
        selectinload(FlowTransitionModel.target_step),
    )
    trans_rows = (await session.execute(transitions_stmt)).scalars().all()

    existing_transitions = [
        {
            "transition_id": t.id,
            "logical_uuid": t.logical_uuid,
            "source_step_id": t.source_step_id,
            "target_step_id": t.target_step_id,
            "source_step_position": t.source_step.position if t.source_step else None,
            "target_step_position": t.target_step.position if t.target_step else None,
            "label": t.label,
            "condition_text": t.condition_text,
            "is_default": t.is_default,
            "semantic_tags": t.semantic_tags or [],
        }
        for t in trans_rows
    ]

    # Derived paths make branching and truncation visible to the generator.
    proj_svc = PathProjectionService()
    proj_resp = await proj_svc.get_path_projections(
        project_id=project_id,
        flow_id=flow.id,
        session=session,
        workspace_id=workspace_id,
    )
    path_projection = {
        "paths": [
            {
                "path_id": p.path_id,
                "step_ids": p.step_ids,
                "transition_ids": p.transition_ids,
                "name": p.name,
                "is_main": p.is_main,
                "status": p.status,
            }
            for p in proj_resp.paths
        ]
    }

    # Linked requirement evidence grounds the local flow context.
    feature_ids = [f.id for f in flow.features]
    scenarios_data = []
    ac_data = []
    context_feature_uuids = {f.logical_uuid for f in flow.features}
    context_scenario_uuids = set()

    if feature_ids:
        sc_stmt = select(ScenarioModel).where(
            ScenarioModel.project_id == project_id,
            ScenarioModel.workspace_id == workspace_id,
            ScenarioModel.feature_id.in_(feature_ids),
        ).options(selectinload(ScenarioModel.acceptance_criteria))
        sc_rows = (await session.execute(sc_stmt)).scalars().all()
        for sc in sc_rows:
            context_scenario_uuids.add(sc.logical_uuid)
            ac_list = []
            for ac in sc.acceptance_criteria:
                ac_item = {
                    "ac_id": ac.id,
                    "logical_uuid": ac.logical_uuid,
                    "content": ac.content,
                }
                ac_data.append(ac_item)
                ac_list.append(ac_item)
            scenarios_data.append({
                "scenario_id": sc.id,
                "logical_uuid": sc.logical_uuid,
                "name": sc.name,
                "content": sc.content,
                "acceptance_criteria": ac_list,
            })

    linked_requirements = {
        "features": [
            {"id": f.id, "logical_uuid": f.logical_uuid, "name": f.name, "description": f.description}
            for f in flow.features
        ],
        "scenarios": scenarios_data,
        "acceptance_criteria": ac_data,
    }

    # Applicable rules are selected through explicit applies-to links.
    step_uuids = {s.logical_uuid for s in steps_rows}
    trans_uuids = {t.logical_uuid for t in trans_rows}
    feature_uuids = {f.logical_uuid for f in flow.features}
    target_uuids = {flow.logical_uuid}.union(step_uuids).union(trans_uuids).union(feature_uuids)

    rule_links_stmt = select(RuleLinkModel).where(
        RuleLinkModel.project_id == project_id,
        RuleLinkModel.workspace_id == workspace_id,
        RuleLinkModel.target_logical_uuid.in_(target_uuids),
    ).options(selectinload(RuleLinkModel.rule).selectinload(DomainRuleModel.parent_rule), selectinload(RuleLinkModel.rule).selectinload(DomainRuleModel.links))
    rule_links_rows = (await session.execute(rule_links_stmt)).scalars().all()

    rules_by_id = {}
    for link in rule_links_rows:
        if link.rule and link.rule.id not in rules_by_id:
            rules_by_id[link.rule.id] = link.rule

    applicable_rules = [
        {
            "rule_id": r.id,
            "logical_uuid": r.logical_uuid,
            "title": r.title,
            "statement": r.statement,
            "confirmation_status": r.confirmation_status,
            "origin": r.origin,
            "parent_rule_uuid": r.parent_rule.logical_uuid if r.parent_rule else None,
            "links": [
                {
                    "target_kind": link.target_kind,
                    "target_logical_uuid": link.target_logical_uuid,
                    "link_purpose": link.link_purpose,
                }
                for link in (r.links or [])
            ],
        }
        for r in rules_by_id.values()
    ]

    # Actor and object candidates are reduced to the refinement scope below.
    bo_stmt = select(BusinessObjectModel).where(
        BusinessObjectModel.project_id == project_id,
        BusinessObjectModel.workspace_id == workspace_id,
    ).options(selectinload(BusinessObjectModel.attributes))
    bo_rows = (await session.execute(bo_stmt)).scalars().all()
    project_bos = [
        {
            "id": b.id,
            "logical_uuid": b.logical_uuid,
            "name": b.name,
            "description": b.description or "",
            "number": f"BO-{b.id}",
            "attributes": [
                {"name": a.name, "data_type": a.data_type, "description": a.description}
                for a in b.attributes
            ],
        }
        for b in bo_rows
    ]

    actor_stmt = select(ActorModel).where(
        ActorModel.project_id == project_id,
        ActorModel.workspace_id == workspace_id,
    )
    actor_rows = (await session.execute(actor_stmt)).scalars().all()
    project_actors = [
        {"id": a.id, "logical_uuid": a.logical_uuid, "name": a.name, "description": a.description or ""}
        for a in actor_rows
    ]

    # Findings provide the diagnostic reason for targeted refinement.
    finding_context = None
    if source_finding_id:
        try:
            policy = HowFindingPolicy()
            findings = await policy.get_findings(project_id, session, workspace_id=workspace_id)
            matching = next(
                (f for f in findings if str(f.findingId) == str(source_finding_id)),
                None,
            )
            if matching:
                finding_context = f"Quality Finding: [{matching.code}] {matching.title}\nDescription: {matching.description}\nTarget: {matching.target}"
            else:
                raise ValueError(f"finding_not_found: {source_finding_id}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"finding_retrieval_failed: {source_finding_id} ({e})") from e

    # 8b. Knowledge retrieval and whitelist
    knowledge_fragments: list[dict[str, Any]] = []
    context_knowledge_uuids: set[str] = set()
    try:
        from backend.database.model import ProjectGenerationStrategyConfigModel
        strat_stmt = select(ProjectGenerationStrategyConfigModel).where(
            ProjectGenerationStrategyConfigModel.project_id == project_id
        )
        strat_res = await session.execute(strat_stmt)
        strat_cfg = strat_res.scalar_one_or_none()
        if strat_cfg is None or strat_cfg.knowledge_enabled:
            from backend.services.knowledge.retrieval import KnowledgeRetrievalService
            k_query = f"{flow.name}\n{flow.description or ''}"
            chunks = await KnowledgeRetrievalService.retrieve_chunks(
                session=session,
                query=k_query[:1000] if k_query.strip() else "flow refinement business rules",
                project_id=project_id,
                top_n=10,
            )
            for c in chunks:
                frag_id = f"chunk-{c.id}"
                context_knowledge_uuids.add(frag_id)
                context_knowledge_uuids.add(str(c.id))
                knowledge_fragments.append({
                    "fragment_id": frag_id,
                    "logical_uuid": frag_id,
                    "document_id": c.document_id,
                    "document_name": c.document.original_filename,
                    "content": c.text[:300],
                })
    except Exception as e:
        raise ValueError(f"knowledge_retrieval_failed: {e}") from e

    # Step-level refinement is restricted to its one-hop neighborhood.
    allowed_step_positions = None
    allowed_step_uuids = None
    allowed_transition_uuids = None
    allowed_actor_ids = None
    allowed_bo_ids = None
    allowed_bo_numbers = None

    if target_kind == "flow_step" and anchor_step_data:
        focus_id = anchor_step_data["step_id"]
        focus_pos = anchor_step_data["position"]
        adjacent_pos: set[int] = set()
        allowed_t_uuids: set[str] = set()

        for t in existing_transitions:
            src_match = t.get("source_step_id") == focus_id or t.get("source_step_position") == focus_pos
            tgt_match = t.get("target_step_id") == focus_id or t.get("target_step_position") == focus_pos
            if src_match:
                allowed_t_uuids.add(t["logical_uuid"])
                if t.get("target_step_position") is not None:
                    adjacent_pos.add(t["target_step_position"])
            if tgt_match:
                allowed_t_uuids.add(t["logical_uuid"])
                if t.get("source_step_position") is not None:
                    adjacent_pos.add(t["source_step_position"])

        allowed_step_positions = {focus_pos}.union(adjacent_pos)
        allowed_step_uuids = {anchor_step_data["logical_uuid"]}.union({
            s["logical_uuid"] for s in existing_steps if s.get("position") in allowed_step_positions
        })
        allowed_transition_uuids = allowed_t_uuids

        # Compute local radius actors & business objects
        radius_steps = [s for s in existing_steps if s.get("position") in allowed_step_positions]
        allowed_actor_ids = {aid for s in radius_steps for aid in s.get("actor_ids", [])}
        allowed_bo_ids = {
            b_id
            for s in radius_steps
            for b_id in s.get("input_business_object_ids", []) + s.get("output_business_object_ids", [])
        }
        allowed_bo_numbers = {
            b["number"] for b in project_bos if b["id"] in allowed_bo_ids
        }

        # Confine context actors and BOs to the local radius
        scoped_actors = [a for a in project_actors if a["id"] in allowed_actor_ids]
        scoped_bos = [b for b in project_bos if b["id"] in allowed_bo_ids]
    else:
        # Flow-level refinement: confined to the target Flow's existing steps
        allowed_actor_ids = {aid for s in existing_steps for aid in s.get("actor_ids", [])}
        allowed_bo_ids = {
            b_id
            for s in existing_steps
            for b_id in s.get("input_business_object_ids", []) + s.get("output_business_object_ids", [])
        }
        allowed_bo_numbers = {
            b["number"] for b in project_bos if b["id"] in allowed_bo_ids
        }
        scoped_actors = [a for a in project_actors if a["id"] in allowed_actor_ids]
        scoped_bos = [b for b in project_bos if b["id"] in allowed_bo_ids]

    # The complete deterministic context protects candidate freshness.
    ctx_hash = compute_refinement_context_hash(
        flow_uuid=flow.logical_uuid,
        flow_name=flow.name,
        steps=existing_steps,
        transitions=existing_transitions,
        rules=applicable_rules,
        scenarios=scenarios_data,
        flow_description=flow.description or "",
        features=linked_requirements["features"],
        actors=scoped_actors,
        business_objects=scoped_bos,
        finding_context=finding_context,
        knowledge_fragments=knowledge_fragments,
    )

    return FlowRefinementContext(
        project_id=project_id,
        workspace_id=workspace_id,
        target_flow_id=flow.id,
        target_flow_logical_uuid=flow.logical_uuid,
        target_flow_name=flow.name,
        target_flow_description=flow.description or "",
        anchor_kind=target_kind,
        anchor_id=target_id,
        anchor_step=anchor_step_data,
        existing_steps=existing_steps,
        existing_transitions=existing_transitions,
        path_projection=path_projection,
        linked_requirements=linked_requirements,
        applicable_rules=applicable_rules,
        business_objects=scoped_bos,
        actors=scoped_actors,
        allowed_step_positions=allowed_step_positions,
        allowed_step_uuids=allowed_step_uuids,
        allowed_transition_uuids=allowed_transition_uuids,
        allowed_actor_ids=allowed_actor_ids,
        allowed_bo_ids=allowed_bo_ids,
        allowed_bo_numbers=allowed_bo_numbers,
        context_feature_uuids=context_feature_uuids,
        context_scenario_uuids=context_scenario_uuids,
        context_knowledge_uuids=context_knowledge_uuids,
        finding_context=finding_context,
        focus_text=focus_text,
        context_hash=ctx_hash,
        knowledge_fragments=knowledge_fragments,
    )
