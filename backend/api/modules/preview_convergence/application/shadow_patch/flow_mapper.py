
from .common import (
    _resolve_generated_reference,
)


def _resolve_preserved_actor_refs(actor_ids: list) -> list[str]:
    actor_refs = []
    for actor_id in actor_ids:
        if str(actor_id).startswith("actor:"):
            actor_refs.append(str(actor_id))
        elif isinstance(actor_id, int):
            actor_refs.append(f"actor:{actor_id}")
        else:
            try:
                actor_refs.append(f"actor:{int(actor_id)}")
            except (ValueError, TypeError):
                pass
    return actor_refs

def _resolve_preserved_business_object_refs(
    business_object_numbers: list,
    business_object_index_by_id: dict,
) -> list[str]:
    business_object_refs = []
    for business_object_number in business_object_numbers:
        if isinstance(business_object_number, int):
            business_object_refs.append(
                f"business_object:{business_object_number}"
            )
        elif (
            str(business_object_number).startswith("tmp_")
            or str(business_object_number).startswith("business_object:")
        ):
            business_object_refs.append(str(business_object_number))
        elif business_object_number in business_object_index_by_id:
            mapped_index = business_object_index_by_id[
                business_object_number
            ]
            business_object_refs.append(f"tmp_bo_gen_{mapped_index + 1}")
        else:
            business_object_refs.append(f"tmp_bo_{business_object_number}")
    return business_object_refs

def _append_preserved_flow_steps(
    patch: dict,
    flow: dict,
    flow_number: str,
    business_object_index_by_id: dict,
) -> None:
    flow_steps = flow.get("flow_steps", [])
    step_temp_id_by_number = {}
    step_temp_ids = []
    for step_index, step in enumerate(flow_steps):
        step_number = (
            step.get("step_number")
            or step.get("id")
            or f"gen_{step_index + 1}"
        )
        temp_id = f"tmp_step_{flow_number}_gen_{step_index + 1}"
        step_temp_id_by_number[str(step_number)] = temp_id
        if step.get("id"):
            step_temp_id_by_number[str(step["id"])] = temp_id
            step_temp_id_by_number[f"step:{step['id']}"] = temp_id
        step_temp_ids.append(temp_id)

    for step_index, step in enumerate(flow_steps):
        temp_id = step_temp_ids[step_index]
        patch["flow_steps_added"].append({
            "temp_id": temp_id,
            "flow_ref": f"tmp_flow_{flow_number}",
            "name": step.get("step_name") or step.get("name"),
            "description": (
                step.get("step_description") or step.get("description")
            ),
            "step_type": step.get("step_type") or step.get("type"),
            "position": step.get("position") or (step_index + 1),
            "actor_refs": _resolve_preserved_actor_refs(
                step.get("actor_ids", [])
            ),
            "input_bo_refs": _resolve_preserved_business_object_refs(
                step.get("input_business_object_numbers", []),
                business_object_index_by_id,
            ),
            "output_bo_refs": _resolve_preserved_business_object_refs(
                step.get("output_business_object_numbers", []),
                business_object_index_by_id,
            ),
        })

    _append_flow_transitions(
        patch,
        flow,
        flow_number,
        step_temp_id_by_number,
        step_temp_ids,
    )

def _append_flow_transitions(
    patch: dict,
    flow: dict,
    flow_number: str,
    step_temp_id_by_number: dict,
    step_temp_ids: list[str],
) -> None:
    transitions = flow.get("transitions", [])
    if not transitions and len(step_temp_ids) > 1:
        raise ValueError("flow_generation_missing_transitions")

    for trans_index, trans in enumerate(transitions):
        source_val = (
            trans.get("source_step_number")
            or trans.get("source_step_id")
            or trans.get("source_step_ref")
        )
        target_val = (
            trans.get("target_step_number")
            or trans.get("target_step_id")
            or trans.get("target_step_ref")
        )
        source_ref = step_temp_id_by_number.get(str(source_val), str(source_val))
        target_ref = step_temp_id_by_number.get(str(target_val), str(target_val))
        patch.setdefault("flow_transitions_added", []).append({
            "temp_id": f"tmp_trans_{flow_number}_gen_{trans_index + 1}",
            "flow_ref": f"tmp_flow_{flow_number}",
            "source_step_ref": source_ref,
            "target_step_ref": target_ref,
            "condition_text": trans.get("condition_text", ""),
            "label": trans.get("label") or "",
            "is_default": bool(trans.get("is_default", False)),
            "position": trans.get("position", trans_index),
            "semantic_tags": trans.get("semantic_tags", []),
            "origin": trans.get("origin", "ai_generated"),
            "confirmation_status": trans.get(
                "confirmation_status", "ai_assumption"
            ),
        })

def _append_preserved_flows(patch: dict, raw_flows: dict) -> None:
    all_business_object_ids = [
        business_object.get("business_object_number")
        or business_object.get("id")
        or f"gen_{business_object_index + 1}"
        for business_object_index, business_object in enumerate(
            raw_flows.get("business_objects", [])
        )
    ]
    business_object_index_by_id = {}
    for business_object_index, business_object_id in enumerate(
        all_business_object_ids
    ):
        business_object_index_by_id.setdefault(
            business_object_id,
            business_object_index,
        )
    for flow_index, flow in enumerate(raw_flows.get("flows", [])):
        flow_number = f"gen_{flow_index + 1}"
        feature_refs = []
        for feature_id in flow.get("feature_ids", []):
            if isinstance(feature_id, int):
                feature_refs.append(f"feature:{feature_id}")
            elif (
                str(feature_id).startswith("tmp_")
                or str(feature_id).startswith("feature:")
            ):
                feature_refs.append(str(feature_id))
            else:
                feature_refs.append(f"tmp_feature_{feature_id}")

        patch["flows_added"].append({
            "temp_id": f"tmp_flow_{flow_number}",
            "name": flow.get("flow_name") or flow.get("name"),
            "description": (
                flow.get("flow_description") or flow.get("description")
            ),
            "feature_refs": feature_refs,
        })
        _append_preserved_flow_steps(
            patch,
            flow,
            flow_number,
            business_object_index_by_id,
        )

def _append_generated_flow_steps(
    patch: dict,
    flow: dict,
    flow_number: str,
    actor_ref_by_id: dict,
    business_object_ref_by_id: dict,
) -> None:
    flow_steps = flow.get("flow_steps", [])
    step_temp_id_by_number = {}
    step_temp_ids = []
    for step_index, step in enumerate(flow_steps):
        step_number = (
            step.get("step_number")
            or step.get("id")
            or f"gen_{step_index + 1}"
        )
        temp_id = f"tmp_step_{flow_number}_gen_{step_index + 1}"
        step_temp_id_by_number[str(step_number)] = temp_id
        if step.get("id"):
            step_temp_id_by_number[str(step["id"])] = temp_id
            step_temp_id_by_number[f"step:{step['id']}"] = temp_id
        step_temp_ids.append(temp_id)

    for step_index, step in enumerate(flow_steps):
        temp_id = step_temp_ids[step_index]
        patch["flow_steps_added"].append({
            "temp_id": temp_id,
            "flow_ref": f"tmp_flow_{flow_number}",
            "name": step.get("step_name") or step.get("name"),
            "description": (
                step.get("step_description") or step.get("description")
            ),
            "step_type": step.get("step_type") or step.get("type"),
            "position": step.get("position") or (step_index + 1),
            "actor_refs": [
                _resolve_generated_reference(
                    actor_id,
                    actor_ref_by_id,
                    "actor",
                    "tmp_actor_",
                )
                for actor_id in step.get("actor_ids", [])
            ],
            "input_bo_refs": [
                _resolve_generated_reference(
                    business_object_id,
                    business_object_ref_by_id,
                    "business_object",
                    "tmp_bo_",
                )
                for business_object_id in step.get(
                    "input_business_object_numbers",
                    [],
                )
            ],
            "output_bo_refs": [
                _resolve_generated_reference(
                    business_object_id,
                    business_object_ref_by_id,
                    "business_object",
                    "tmp_bo_",
                )
                for business_object_id in step.get(
                    "output_business_object_numbers",
                    [],
                )
            ],
        })

    _append_flow_transitions(
        patch,
        flow,
        flow_number,
        step_temp_id_by_number,
        step_temp_ids,
    )

def _append_generated_flows(
    patch: dict,
    raw_flows: dict,
    feature_ref_by_id: dict,
    actor_ref_by_id: dict,
    business_object_ref_by_id: dict,
) -> None:
    for flow_index, flow in enumerate(raw_flows.get("flows", [])):
        flow_number = f"gen_{flow_index + 1}"
        patch["flows_added"].append({
            "temp_id": f"tmp_flow_{flow_number}",
            "name": flow.get("flow_name") or flow.get("name"),
            "description": (
                flow.get("flow_description") or flow.get("description")
            ),
            "feature_refs": [
                _resolve_generated_reference(
                    feature_id,
                    feature_ref_by_id,
                    "feature",
                    "tmp_feature_",
                )
                for feature_id in flow.get("feature_ids", [])
            ],
        })
        _append_generated_flow_steps(
            patch,
            flow,
            flow_number,
            actor_ref_by_id,
            business_object_ref_by_id,
        )
