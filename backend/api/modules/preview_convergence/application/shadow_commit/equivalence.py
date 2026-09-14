from __future__ import annotations


def _flow_indexes(snapshot: dict) -> tuple[dict[str, tuple], dict[str, tuple]]:
    steps: dict[str, tuple] = {}
    transitions: dict[str, tuple] = {}
    actor_names = {
        actor.get("id", actor.get("actor_id")): actor.get(
            "name", actor.get("actor_name", "")
        )
        for actor in snapshot.get("actors", [])
    }
    object_names = {
        item.get("id", item.get("business_object_id")): item.get(
            "name", item.get("business_object_name", "")
        )
        for item in snapshot.get("business_objects", [])
    }
    for flow in snapshot.get("flows", []):
        flow_name = flow.get("name", flow.get("flow_name", ""))
        step_names = {}
        for step in flow.get("flow_steps", []):
            step_id = step.get("id", step.get("step_id"))
            step_name = step.get("name", step.get("step_name", ""))
            step_names[step_id] = step_name
            key = (
                flow_name,
                step_name,
                step.get("description", step.get("step_description", "")),
                step.get("step_type", ""),
                step.get("position"),
                tuple(sorted(
                    actor_names.get(item, str(item))
                    for item in step.get("actor_ids", [])
                )),
                tuple(sorted(
                    object_names.get(item, str(item))
                    for item in step.get("input_business_object_ids", [])
                )),
                tuple(sorted(
                    object_names.get(item, str(item))
                    for item in step.get("output_business_object_ids", [])
                )),
            )
            if step.get("logical_uuid"):
                steps[step["logical_uuid"]] = key
        for transition in flow.get("transitions", []):
            key = (
                flow_name,
                step_names.get(transition.get("source_step_id")),
                step_names.get(transition.get("target_step_id")),
                transition.get("label", ""),
                transition.get("condition_text", ""),
                bool(transition.get("is_default")),
                transition.get("position", 0),
                tuple(sorted(set(transition.get("semantic_tags", [])))),
                transition.get("origin", ""),
                transition.get("confirmation_status", ""),
            )
            if transition.get("logical_uuid"):
                transitions[transition["logical_uuid"]] = key
    return steps, transitions


def build_how_semantic_signature(snapshot: dict) -> dict[str, tuple]:
    steps, transitions = _flow_indexes(snapshot)
    target_identities: dict[str, dict[str, object]] = {
        "flow_step": steps,
        "flow_transition": transitions,
        "flow": {
            flow.get("logical_uuid"): flow.get("name", flow.get("flow_name", ""))
            for flow in snapshot.get("flows", [])
        },
        "feature": {},
        "scenario": {},
        "acceptance_criterion": {},
    }
    for feature in snapshot.get("features", []):
        target_identities["feature"][feature.get("logical_uuid")] = feature.get(
            "name", feature.get("feature_name", "")
        )
        for scenario in feature.get("scenarios", []):
            target_identities["scenario"][scenario.get("logical_uuid")] = (
                scenario.get("name", scenario.get("scenario_name", ""))
            )
            for criterion in scenario.get("acceptance_criteria", []):
                target_identities["acceptance_criterion"][
                    criterion.get("logical_uuid")
                ] = criterion.get(
                    "content", criterion.get("criterion_content", "")
                )
    rules = snapshot.get("domain_rules", [])
    rule_title_by_uuid = {
        rule.get("logical_uuid"): rule.get("title", "")
        for rule in rules
    }
    rule_signature = tuple(sorted(
        (
            rule.get("title", ""),
            rule.get("statement", ""),
            rule.get("origin", ""),
            rule.get("confirmation_status", ""),
            rule_title_by_uuid.get(rule.get("parent_rule_logical_uuid")),
        )
        for rule in rules
    ))
    link_signature = []
    for rule in rules:
        for link in rule.get("links", []):
            target_uuid = link.get("target_logical_uuid")
            target_identity = target_identities.get(
                link.get("target_kind"), {}
            ).get(target_uuid, target_uuid)
            link_signature.append((
                rule.get("title", ""),
                link.get("target_kind", ""),
                target_identity,
                link.get("link_purpose", ""),
                link.get("context_text", ""),
            ))
    return {
        "rules": rule_signature,
        "rule_links": tuple(sorted(link_signature, key=repr)),
        "steps": tuple(sorted(steps.values(), key=repr)),
        "transitions": tuple(sorted(transitions.values(), key=repr)),
    }
