"""Normalizer and validation pipeline for flow refinement candidate output."""

from typing import Any

from backend.api.modules.requirements_core.flow_refinement.domain.invariants import (
    validate_no_confirmed_rule_modifications,
    validate_refinement_bounds,
    validate_refinement_references,
    validate_refinement_temp_ids,
)
from backend.core.model_invariants.rule_source_links import canonicalize_rule_source_links


def normalize_refinement_rule_links(raw_output: dict[str, Any]) -> dict[str, Any]:
    """Resolve both transition rule references and explicit links to one persistence form."""
    rules = [
        {
            **rule,
            "source_links": canonicalize_rule_source_links(
                {
                    **link,
                    "target_logical_uuid": link.get("target_ref") or link.get("target_logical_uuid"),
                }
                for link in rule.get("source_links", [])
            ),
        }
        for rule in raw_output.get("rules_added", [])
    ]
    links = list(raw_output.get("rule_links_added", []))
    for transition in raw_output.get("transitions_added", []) + raw_output.get("transitions_updated", []):
        for rule_ref in transition.get("rule_refs") or []:
            links.append({
                "rule_ref": rule_ref,
                "target_kind": "flow_transition",
                "target_ref": transition.get("temp_id") or transition.get("logical_uuid"),
                "link_purpose": "applies_to",
            })

    canonical = {}
    for link in links:
        normalized = {**link, "link_purpose": link.get("link_purpose") or "applies_to"}
        key = (
            normalized.get("rule_ref"), normalized.get("target_kind"),
            normalized.get("target_ref"), normalized["link_purpose"],
        )
        existing = canonical.get(key)
        if existing is None:
            canonical[key] = normalized
        elif len(normalized.get("context_text") or "") > len(existing.get("context_text") or ""):
            existing["context_text"] = normalized["context_text"]
    return {"rules_added": rules, "rule_links_added": list(canonical.values())}


def normalize_and_validate_refinement(
    raw_output: dict[str, Any],
    *,
    existing_step_positions: set[int],
    existing_step_uuids: set[str],
    existing_transition_uuids: set[str],
    existing_rule_uuids: set[str],
    confirmed_rule_statements: set[str],
    existing_flow_uuid: str | None = None,
    target_kind: str = "flow",
    allowed_step_positions: set[int] | None = None,
    allowed_step_uuids: set[str] | None = None,
    allowed_transition_uuids: set[str] | None = None,
    allowed_actor_ids: set[int] | None = None,
    allowed_bo_numbers: set[str] | None = None,
    context_feature_uuids: set[str] | None = None,
    context_scenario_uuids: set[str] | None = None,
    context_knowledge_uuids: set[str] | None = None,
    existing_transitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate candidate output against domain bounds, reference integrity, and confirmed rules."""
    steps_added = raw_output.get("steps_added", [])
    transitions_added = raw_output.get("transitions_added", [])
    transitions_updated = raw_output.get("transitions_updated", [])
    rule_changes = normalize_refinement_rule_links(raw_output)
    rules_added = rule_changes["rules_added"]
    rule_links_added = rule_changes["rule_links_added"]
    business_objects_added = raw_output.get("business_objects_added", [])

    # Ensure at most one default outgoing transition per source step
    existing_default_sources: set[Any] = set()
    if existing_transitions:
        for t in existing_transitions:
            if t.get("is_default"):
                if t.get("source_step_position") is not None:
                    existing_default_sources.add(t["source_step_position"])
                if t.get("source_step_id") is not None:
                    existing_default_sources.add(t["source_step_id"])
                if t.get("source_step_uuid") is not None:
                    existing_default_sources.add(t["source_step_uuid"])

    sources_with_default = set(existing_default_sources)
    for t in transitions_added:
        src = t.get("source_step_ref") or t.get("source_step_position")
        if t.get("is_default"):
            if src in sources_with_default:
                t["is_default"] = False
            else:
                sources_with_default.add(src)

    # Normalize business object attributes (strictly single official field)
    for bo in business_objects_added:
        attrs = bo.get("business_object_attributes", [])
        bo["business_object_attributes"] = attrs

    # Hard limits keep refinement bounded.
    validate_refinement_bounds(steps_added, transitions_added, rules_added)

    # Temporary identifiers form an unambiguous candidate-local namespace.
    validate_refinement_temp_ids(steps_added, transitions_added, rules_added)

    # Confirmed rules are immutable and generated rules remain assumptions.
    validate_no_confirmed_rule_modifications(rules_added, confirmed_rule_statements)

    # Every candidate reference must be grounded in the loaded context.
    validate_refinement_references(
        steps_added,
        transitions_added,
        transitions_updated,
        rules_added,
        rule_links_added,
        existing_step_positions=existing_step_positions,
        existing_step_uuids=existing_step_uuids,
        existing_transition_uuids=existing_transition_uuids,
        existing_rule_uuids=existing_rule_uuids,
        existing_flow_uuid=existing_flow_uuid,
        business_objects_added=business_objects_added,
        target_kind=target_kind,
        allowed_step_positions=allowed_step_positions,
        allowed_step_uuids=allowed_step_uuids,
        allowed_transition_uuids=allowed_transition_uuids,
        allowed_actor_ids=allowed_actor_ids,
        allowed_bo_numbers=allowed_bo_numbers,
        context_feature_uuids=context_feature_uuids,
        context_scenario_uuids=context_scenario_uuids,
        context_knowledge_uuids=context_knowledge_uuids,
    )

    # Enforce ai_assumption confirmation status for all newly added rules
    for r in rules_added:
        r["confirmation_status"] = "ai_assumption"

    # Build step_object_links summary
    step_object_links_added = []
    for s in steps_added:
        for num in s.get("input_business_object_numbers", []):
            step_object_links_added.append({
                "step_ref": s.get("temp_id"),
                "business_object_number": num,
                "direction": "input",
            })
        for num in s.get("output_business_object_numbers", []):
            step_object_links_added.append({
                "step_ref": s.get("temp_id"),
                "business_object_number": num,
                "direction": "output",
            })

    # Return clean normalized structure
    return {
        "rationale": raw_output.get("rationale", ""),
        "steps_added": steps_added,
        "transitions_added": transitions_added,
        "transitions_updated": transitions_updated,
        "rules_added": rules_added,
        "rule_links_added": rule_links_added,
        "business_objects_added": business_objects_added,
        "step_object_links_added": step_object_links_added,
    }
