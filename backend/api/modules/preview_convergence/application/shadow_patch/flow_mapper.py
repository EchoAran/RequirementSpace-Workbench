from typing import Any

from .common import (
    _resolve_generated_reference,
    _resolve_next_step_refs,
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
    step_index_by_number = {}
    for step_index, step in enumerate(flow_steps):
        step_number = (
            step.get("step_number")
            or step.get("id")
            or f"gen_{step_index + 1}"
        )
        step_index_by_number.setdefault(step_number, step_index)

    for step_index, step in enumerate(flow_steps):
        step_number = f"gen_{step_index + 1}"
        patch["flow_steps_added"].append({
            "temp_id": f"tmp_step_{flow_number}_{step_number}",
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
            "next_step_refs": _resolve_next_step_refs(
                flow_number,
                step_index_by_number,
                step.get("next_steps", []),
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
    step_index_by_number = {}
    for step_index, step in enumerate(flow_steps):
        step_number = (
            step.get("step_number")
            or step.get("id")
            or f"gen_{step_index + 1}"
        )
        step_index_by_number.setdefault(step_number, step_index)

    for step_index, step in enumerate(flow_steps):
        step_number = f"gen_{step_index + 1}"
        patch["flow_steps_added"].append({
            "temp_id": f"tmp_step_{flow_number}_{step_number}",
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
            "next_step_refs": _resolve_next_step_refs(
                flow_number,
                step_index_by_number,
                step.get("next_steps", []),
            ),
        })

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
