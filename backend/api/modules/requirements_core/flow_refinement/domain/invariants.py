"""Domain invariants and boundary validations for bounded flow refinement."""

from typing import Any

MAX_ADDED_STEPS = 5
MAX_ADDED_TRANSITIONS = 8
MAX_ADDED_RULES = 3


def validate_refinement_bounds(
    steps_added: list[dict[str, Any]],
    transitions_added: list[dict[str, Any]],
    rules_added: list[dict[str, Any]],
) -> None:
    """Validate that candidate increment does not exceed hard bounds."""
    if len(steps_added) > MAX_ADDED_STEPS:
        raise ValueError(
            f"refinement_step_limit_exceeded: candidate has {len(steps_added)} steps, "
            f"max allowed is {MAX_ADDED_STEPS}"
        )
    if len(transitions_added) > MAX_ADDED_TRANSITIONS:
        raise ValueError(
            f"refinement_transition_limit_exceeded: candidate has {len(transitions_added)} transitions, "
            f"max allowed is {MAX_ADDED_TRANSITIONS}"
        )
    if len(rules_added) > MAX_ADDED_RULES:
        raise ValueError(
            f"refinement_rule_limit_exceeded: candidate has {len(rules_added)} rules, "
            f"max allowed is {MAX_ADDED_RULES}"
        )


def validate_refinement_temp_ids(
    steps_added: list[dict[str, Any]],
    transitions_added: list[dict[str, Any]],
    rules_added: list[dict[str, Any]],
) -> None:
    """Ensure all temporary IDs are unique across newly introduced entities."""
    seen_step_ids: set[str] = set()
    for s in steps_added:
        tid = s.get("temp_id")
        if not tid:
            raise ValueError("missing_step_temp_id")
        if tid in seen_step_ids:
            raise ValueError(f"duplicate_step_temp_id: {tid}")
        seen_step_ids.add(tid)

    seen_transition_ids: set[str] = set()
    for t in transitions_added:
        tid = t.get("temp_id")
        if not tid:
            raise ValueError("missing_transition_temp_id")
        if tid in seen_transition_ids:
            raise ValueError(f"duplicate_transition_temp_id: {tid}")
        seen_transition_ids.add(tid)

    seen_rule_ids: set[str] = set()
    for r in rules_added:
        tid = r.get("temp_id")
        if not tid:
            raise ValueError("missing_rule_temp_id")
        if tid in seen_rule_ids:
            raise ValueError(f"duplicate_rule_temp_id: {tid}")
        seen_rule_ids.add(tid)


def validate_refinement_references(
    steps_added: list[dict[str, Any]],
    transitions_added: list[dict[str, Any]],
    transitions_updated: list[dict[str, Any]],
    rules_added: list[dict[str, Any]],
    rule_links_added: list[dict[str, Any]],
    *,
    existing_step_positions: set[int],
    existing_step_uuids: set[str],
    existing_transition_uuids: set[str],
    existing_rule_uuids: set[str],
    existing_flow_uuid: str | None = None,
    business_objects_added: list[dict[str, Any]] | None = None,
    target_kind: str = "flow",
    allowed_step_positions: set[int] | None = None,
    allowed_step_uuids: set[str] | None = None,
    allowed_transition_uuids: set[str] | None = None,
    allowed_actor_ids: set[int] | None = None,
    allowed_bo_numbers: set[str] | None = None,
    context_feature_uuids: set[str] | None = None,
    context_scenario_uuids: set[str] | None = None,
    context_knowledge_uuids: set[str] | None = None,
) -> None:
    """Validate that all transitions, step positions, and rule links resolve properly."""
    new_step_temp_ids = {s["temp_id"] for s in steps_added if s.get("temp_id")}
    new_rule_temp_ids = {r["temp_id"] for r in rules_added if r.get("temp_id")}
    new_bo_numbers = {
        b.get("business_object_number") or b.get("number")
        for b in (business_objects_added or [])
        if (b.get("business_object_number") or b.get("number"))
    }

    # Validate step actors and BO references against local radius whitelist
    for s in steps_added:
        if allowed_actor_ids is not None:
            for aid in s.get("actor_ids", []):
                if aid not in allowed_actor_ids:
                    raise ValueError(f"step_actor_outside_local_refinement_radius: actor {aid}")
        if allowed_bo_numbers is not None:
            for b_num in s.get("input_business_object_numbers", []) + s.get("output_business_object_numbers", []):
                if b_num not in allowed_bo_numbers and b_num not in new_bo_numbers:
                    raise ValueError(f"step_business_object_outside_local_refinement_radius: business_object {b_num}")

    # Validate added transitions references
    for t in transitions_added:
        src = t.get("source_step_ref") or t.get("source_step_position")
        tgt = t.get("target_step_ref") or t.get("target_step_position")
        if not src or not tgt:
            raise ValueError("transition_endpoints_missing")

        # Source must be existing step or newly introduced step
        is_src_valid = (
            (isinstance(src, int) and src in existing_step_positions)
            or (isinstance(src, str) and (src in new_step_temp_ids or src in existing_step_uuids))
        )
        if not is_src_valid:
            raise ValueError(f"invalid_transition_source_reference: {src}")

        # Target must be existing step or newly introduced step
        is_tgt_valid = (
            (isinstance(tgt, int) and tgt in existing_step_positions)
            or (isinstance(tgt, str) and (tgt in new_step_temp_ids or tgt in existing_step_uuids))
        )
        if not is_tgt_valid:
            raise ValueError(f"invalid_transition_target_reference: {tgt}")

        # Self loops prohibited
        if src == tgt:
            raise ValueError("transition_self_loop_prohibited")

        # Local radius enforcement for flow_step targets
        if target_kind == "flow_step" and (allowed_step_positions is not None or allowed_step_uuids is not None):
            src_in_radius = (
                (isinstance(src, int) and allowed_step_positions is not None and src in allowed_step_positions)
                or (isinstance(src, str) and (src in new_step_temp_ids or (allowed_step_uuids is not None and src in allowed_step_uuids)))
            )
            tgt_in_radius = (
                (isinstance(tgt, int) and allowed_step_positions is not None and tgt in allowed_step_positions)
                or (isinstance(tgt, str) and (tgt in new_step_temp_ids or (allowed_step_uuids is not None and tgt in allowed_step_uuids)))
            )
            if not src_in_radius or not tgt_in_radius:
                raise ValueError(f"transition_outside_local_refinement_radius: {src}->{tgt}")

    # Validate updated transitions reference existing transitions
    for ut in transitions_updated:
        uuid = ut.get("logical_uuid")
        if not uuid or uuid not in existing_transition_uuids:
            raise ValueError(f"invalid_updated_transition_reference: {uuid}")
        if target_kind == "flow_step" and allowed_transition_uuids is not None:
            if uuid not in allowed_transition_uuids:
                raise ValueError(f"transition_update_outside_local_refinement_radius: {uuid}")

    # Validate rules grounding and parent references
    for r in rules_added:
        parent_ref = r.get("parent_rule_ref")
        has_valid_parent = False
        if parent_ref:
            if parent_ref not in existing_rule_uuids and parent_ref not in new_rule_temp_ids:
                raise ValueError(f"invalid_parent_rule_reference: {parent_ref}")
            has_valid_parent = True

        # Validate source_links of the rule if present
        source_links = r.get("source_links", [])
        has_valid_source_link = False
        for sl in source_links:
            skind = sl.get("target_kind")
            sref = sl.get("target_ref") or sl.get("target_logical_uuid")
            if not skind or not sref:
                continue
            if skind == "feature" and context_feature_uuids is not None:
                if sref not in context_feature_uuids:
                    raise ValueError(f"rule_source_link_not_in_context: feature {sref}")
                has_valid_source_link = True
            elif skind == "scenario" and context_scenario_uuids is not None:
                if sref not in context_scenario_uuids:
                    raise ValueError(f"rule_source_link_not_in_context: scenario {sref}")
                has_valid_source_link = True
            elif skind == "knowledge" and context_knowledge_uuids is not None:
                if sref not in context_knowledge_uuids:
                    raise ValueError(f"rule_source_link_not_in_context: knowledge {sref}")
                has_valid_source_link = True
            elif skind == "flow_step":
                valid_source_steps = (
                    allowed_step_uuids.union(new_step_temp_ids)
                    if (target_kind == "flow_step" and allowed_step_uuids is not None)
                    else existing_step_uuids.union(new_step_temp_ids)
                )
                if sref not in valid_source_steps:
                    raise ValueError(f"rule_source_link_not_in_context: flow_step {sref}")
                has_valid_source_link = True
            elif skind in ("feature", "scenario", "knowledge"):
                has_valid_source_link = True

        # Rule must have either a parent rule or at least one source evidence link
        if not has_valid_parent and not has_valid_source_link:
            raise ValueError(f"rule_lacks_parent_or_source_evidence: {r.get('temp_id')}")

    # Validate rule link targets
    valid_transition_targets = (
        allowed_transition_uuids.union({t["temp_id"] for t in transitions_added if t.get("temp_id")})
        if (target_kind == "flow_step" and allowed_transition_uuids is not None)
        else existing_transition_uuids.union({t["temp_id"] for t in transitions_added if t.get("temp_id")})
    )
    valid_step_targets = (
        allowed_step_uuids.union(new_step_temp_ids)
        if (target_kind == "flow_step" and allowed_step_uuids is not None)
        else existing_step_uuids.union(new_step_temp_ids)
    )

    for link in rule_links_added:
        target_kind_item = link.get("target_kind")
        target_ref = link.get("target_ref") or link.get("target_logical_uuid")
        rule_ref = link.get("rule_ref") or link.get("rule_temp_id")

        if not rule_ref or (rule_ref not in existing_rule_uuids and rule_ref not in new_rule_temp_ids):
            raise ValueError(f"invalid_rule_link_rule_reference: {rule_ref}")

        if target_kind_item == "flow":
            if target_kind != "flow" or not existing_flow_uuid or target_ref != existing_flow_uuid:
                raise ValueError(f"invalid_rule_link_flow_target: {target_ref}")
        elif target_kind_item == "flow_transition":
            if target_ref not in valid_transition_targets:
                raise ValueError(f"invalid_rule_link_transition_target: {target_ref}")
        elif target_kind_item == "flow_step":
            if target_ref not in valid_step_targets:
                raise ValueError(f"invalid_rule_link_step_target: {target_ref}")
        elif target_kind_item == "feature":
            if context_feature_uuids is not None and target_ref not in context_feature_uuids:
                raise ValueError(f"rule_link_target_not_in_context: feature {target_ref}")
        elif target_kind_item == "scenario":
            if context_scenario_uuids is not None and target_ref not in context_scenario_uuids:
                raise ValueError(f"rule_link_target_not_in_context: scenario {target_ref}")
        elif target_kind_item == "knowledge":
            if context_knowledge_uuids is not None and target_ref not in context_knowledge_uuids:
                raise ValueError(f"rule_link_target_not_in_context: knowledge {target_ref}")
        else:
            raise ValueError(f"unsupported_rule_link_target_kind: {target_kind_item}")


def validate_no_confirmed_rule_modifications(
    rules_added: list[dict[str, Any]],
    confirmed_rule_statements: set[str],
) -> None:
    """Ensure refined rules do not overwrite or contradict confirmed rules and cannot be directly confirmed."""
    for r in rules_added:
        if r.get("confirmation_status") == "confirmed":
            raise ValueError("confirmed_rule_generation_forbidden")
        stmt = (r.get("statement") or "").strip()
        if stmt in confirmed_rule_statements:
            raise ValueError("confirmed_rule_modification_forbidden")
