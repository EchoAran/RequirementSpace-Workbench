from __future__ import annotations

from backend.core.model_invariants.flow_invariants import (
    validate_no_self_loop,
    validate_transition_position,
)
from backend.core.model_invariants.rule_invariants import (
    validate_rule_confirmation_status,
    validate_rule_link_purpose,
    validate_rule_link_target,
    validate_rule_origin,
    validate_rule_parent_graph,
    validate_rule_text,
)

from .apply_state import NegativeIdAllocator


def _reference_id(reference: str, allocator: NegativeIdAllocator) -> int:
    resolved = allocator.resolve(reference)
    if not resolved:
        raise ValueError(f"Unresolved shadow reference '{reference}'")
    return resolved


def _transition_index(snapshot: dict) -> dict[int, tuple[dict, dict]]:
    return {
        transition.get("id", transition.get("transition_id")): (flow, transition)
        for flow in snapshot.get("flows", [])
        for transition in flow.get("transitions", [])
    }


def _rule_index(snapshot: dict) -> dict[int, dict]:
    return {
        rule["id"]: rule
        for rule in snapshot.get("domain_rules", [])
    }


def _link_index(snapshot: dict) -> dict[int, tuple[dict, dict]]:
    return {
        link["id"]: (rule, link)
        for rule in snapshot.get("domain_rules", [])
        for link in rule.get("links", [])
    }


def apply_how_removals(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    for reference in patch.get("rule_links_removed", []):
        link_id = _reference_id(reference, allocator)
        owner_and_link = _link_index(snapshot).get(link_id)
        if owner_and_link is None:
            raise ValueError(f"Unresolved rule link reference '{reference}'")
        owner, link = owner_and_link
        owner["links"].remove(link)

    for reference in patch.get("flow_transitions_removed", []):
        transition_id = _reference_id(reference, allocator)
        owner_and_transition = _transition_index(snapshot).get(transition_id)
        if owner_and_transition is None:
            raise ValueError(f"Unresolved transition reference '{reference}'")
        linked = [
            link
            for rule in snapshot.get("domain_rules", [])
            for link in rule.get("links", [])
            if link.get("target_kind") == "flow_transition"
            and link.get("target_logical_uuid")
            == owner_and_transition[1].get("logical_uuid")
        ]
        if linked:
            raise ValueError("shadow_transition_has_rule_links")
        flow, transition = owner_and_transition
        flow["transitions"].remove(transition)

    for reference in patch.get("domain_rules_removed", []):
        rule_id = _reference_id(reference, allocator)
        rule = _rule_index(snapshot).get(rule_id)
        if rule is None:
            raise ValueError(f"Unresolved domain rule reference '{reference}'")
        if rule.get("links"):
            raise ValueError("shadow_rule_has_links")
        logical_uuid = rule.get("logical_uuid")
        if any(
            candidate.get("parent_rule_logical_uuid") == logical_uuid
            for candidate in snapshot.get("domain_rules", [])
        ):
            raise ValueError("shadow_rule_has_children")
        snapshot["domain_rules"].remove(rule)


def apply_how_updates(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
    resolve_target_logical_uuid,
) -> None:
    rules = _rule_index(snapshot)
    for update in patch.get("domain_rules_updated", []):
        rule = rules.get(_reference_id(update["rule_ref"], allocator))
        if rule is None:
            raise ValueError(f"Unresolved domain rule reference '{update['rule_ref']}'")
        for field_name in ("title", "statement", "origin", "confirmation_status"):
            if field_name in update:
                rule[field_name] = update[field_name]
        if "parent_ref" in update:
            parent_ref = update["parent_ref"]
            parent = (
                rules.get(_reference_id(parent_ref, allocator))
                if parent_ref is not None
                else None
            )
            rule["parent_rule_logical_uuid"] = (
                parent.get("logical_uuid") if parent else None
            )

    links = _link_index(snapshot)
    for update in patch.get("rule_links_updated", []):
        owner_and_link = links.get(
            _reference_id(update["rule_link_ref"], allocator)
        )
        if owner_and_link is None:
            raise ValueError(
                f"Unresolved rule link reference '{update['rule_link_ref']}'"
            )
        owner, link = owner_and_link
        if "rule_ref" in update:
            target_owner = rules.get(
                _reference_id(update["rule_ref"], allocator)
            )
            if target_owner is None:
                raise ValueError(
                    f"Unresolved domain rule reference '{update['rule_ref']}'"
                )
            owner["links"].remove(link)
            target_owner.setdefault("links", []).append(link)
        target_kind = update.get("target_kind", link["target_kind"])
        if "target_ref" in update or "target_kind" in update:
            target_ref = update.get("target_ref")
            if target_ref is None:
                raise ValueError("shadow_rule_link_target_ref_required")
            link["target_kind"] = target_kind
            link["target_logical_uuid"] = resolve_target_logical_uuid(
                snapshot,
                target_kind,
                target_ref,
                allocator,
            )
        for field_name in ("link_purpose", "context_text"):
            if field_name in update:
                link[field_name] = update[field_name]

    transitions = _transition_index(snapshot)
    for update in patch.get("flow_transitions_updated", []):
        flow, transition = transitions.get(
            _reference_id(update["transition_ref"], allocator),
            (None, None),
        )
        if transition is None:
            raise ValueError(
                f"Unresolved transition reference '{update['transition_ref']}'"
            )
        step_ids = {
            step.get("id", step.get("step_id"))
            for step in flow.get("flow_steps", [])
        }
        for field_name, target_name in (
            ("source_step_ref", "source_step_id"),
            ("target_step_ref", "target_step_id"),
        ):
            if field_name in update:
                step_id = _reference_id(update[field_name], allocator)
                if step_id not in step_ids:
                    raise ValueError("shadow_transition_step_outside_flow")
                transition[target_name] = step_id
        for field_name in (
            "label",
            "condition_text",
            "is_default",
            "position",
            "origin",
            "confirmation_status",
        ):
            if field_name in update:
                transition[field_name] = update[field_name]
        if "semantic_tags" in update:
            transition["semantic_tags"] = sorted(set(update["semantic_tags"]))


def validate_how_snapshot(snapshot: dict) -> None:
    parent_by_rule = {
        rule["logical_uuid"]: rule.get("parent_rule_logical_uuid")
        for rule in snapshot.get("domain_rules", [])
    }
    validate_rule_parent_graph(parent_by_rule)
    for rule in snapshot.get("domain_rules", []):
        validate_rule_text(rule.get("title", ""), rule.get("statement", ""))
        validate_rule_origin(rule.get("origin", ""))
        validate_rule_confirmation_status(rule.get("confirmation_status", ""))
        for link in rule.get("links", []):
            validate_rule_link_target(
                link.get("target_kind", ""),
                link.get("target_logical_uuid", ""),
            )
            validate_rule_link_purpose(link.get("link_purpose", ""))

    for flow in snapshot.get("flows", []):
        step_ids = {
            step.get("id", step.get("step_id"))
            for step in flow.get("flow_steps", [])
        }
        seen_edges: set[tuple[int, int]] = set()
        defaults: set[int] = set()
        positions: set[tuple[int, int]] = set()
        for transition in flow.get("transitions", []):
            source_id = transition["source_step_id"]
            target_id = transition["target_step_id"]
            if source_id not in step_ids or target_id not in step_ids:
                raise ValueError("shadow_transition_step_outside_flow")
            validate_no_self_loop(source_id, target_id)
            edge = (source_id, target_id)
            if edge in seen_edges:
                raise ValueError("shadow_duplicate_transition")
            seen_edges.add(edge)
            position = transition.get("position", 0)
            validate_transition_position(position)
            position_key = (source_id, position)
            if position_key in positions:
                raise ValueError("shadow_duplicate_transition_position")
            positions.add(position_key)
            if transition.get("is_default"):
                if source_id in defaults:
                    raise ValueError("shadow_duplicate_default_transition")
                defaults.add(source_id)
