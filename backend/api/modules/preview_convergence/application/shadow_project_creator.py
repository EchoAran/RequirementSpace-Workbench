import copy
import hashlib
import json
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
    ProjectModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    FlowModel,
    FlowStepModel,
    ScopeModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
    flow_step_next_table,
    beijing_now,
)


def calculate_stable_snapshot_hash(snapshot: dict) -> str:
    """
    Computes SHA-256 hash based on canonical JSON sorting,
    ignoring unstable/transient properties.
    """
    dumped = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def remap_snapshot_to_pydantic(snapshot: dict) -> dict:
    s = copy.deepcopy(snapshot)
    shadow_updated_at = beijing_now()

    def get_updated_at(node: dict):
        updated_at = node.get("updated_at") or node.get("updatedAt") or shadow_updated_at
        return updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at
    
    # Remap project fields
    s["project_id"] = s.get("project_id", s.get("id"))
    s["project_name"] = s.get("project_name", s.get("name"))
    s["project_description"] = s.get("project_description", s.get("description"))
    
    # Remap actors
    new_actors = []
    for a in s.get("actors", []):
        new_actors.append({
            "actor_id": a.get("actor_id") if "actor_id" in a else a.get("id"),
            "actor_name": a.get("actor_name") if "actor_name" in a else a.get("name"),
            "actor_description": a.get("actor_description") if "actor_description" in a else a.get("description"),
            "updated_at": get_updated_at(a),
            "kind": "actor"
        })
    s["actors"] = new_actors
    
    # Remap features
    new_features = []
    for f in s.get("features", []):
        scenarios_remapped = []
        for sc in f.get("scenarios", []):
            ac_remapped = []
            for ac in sc.get("acceptance_criteria", []):
                ac_remapped.append({
                    "criterion_id": ac.get("criterion_id") if "criterion_id" in ac else ac.get("id"),
                    "criterion_content": ac.get("criterion_content") if "criterion_content" in ac else ac.get("content"),
                    "updated_at": get_updated_at(ac),
                    "kind": "acceptance_criterion"
                })
            scenarios_remapped.append({
                "scenario_id": sc.get("scenario_id") if "scenario_id" in sc else sc.get("id"),
                "scenario_name": sc.get("scenario_name") if "scenario_name" in sc else sc.get("name"),
                "scenario_content": sc.get("scenario_content") if "scenario_content" in sc else sc.get("content"),
                "feature_id": sc.get("feature_id"),
                "actor_id": sc.get("actor_id"),
                "acceptance_criteria": ac_remapped,
                "updated_at": get_updated_at(sc),
                "kind": "scenario"
            })
            
        scope_remapped = None
        scope_obj = f.get("scope")
        if scope_obj:
            scope_remapped = {
                "scope_id": scope_obj.get("scope_id") if "scope_id" in scope_obj else scope_obj.get("id"),
                "scope_status": scope_obj.get("scope_status") if "scope_status" in scope_obj else scope_obj.get("status"),
                "reason": scope_obj.get("reason"),
                "positive_summary": scope_obj.get("positive_summary"),
                "negative_summary": scope_obj.get("negative_summary"),
                "positive_picture_base64": scope_obj.get("positive_picture_base64") or scope_obj.get("positivePictureBase64"),
                "negative_picture_base64": scope_obj.get("negative_picture_base64") or scope_obj.get("negativePictureBase64"),
                "kano_category": scope_obj.get("kano_category"),
                "kano_category_name": scope_obj.get("kano_category_name"),
                "updated_at": get_updated_at(scope_obj),
                "kind": "scope"
            }
            
        new_features.append({
            "feature_id": f.get("feature_id") if "feature_id" in f else f.get("id"),
            "feature_name": f.get("feature_name") if "feature_name" in f else f.get("name"),
            "feature_description": f.get("feature_description") if "feature_description" in f else f.get("description"),
            "actor_ids": f.get("actor_ids", []),
            "parent_id": f.get("parent_id"),
            "children_ids": f.get("children_ids", []),
            "scenarios": scenarios_remapped,
            "scope": scope_remapped,
            "updated_at": get_updated_at(f),
            "kind": "feature"
        })
    s["features"] = new_features
    
    # Remap business objects
    new_bos = []
    for bo in s.get("business_objects", []):
        attrs_remapped = []
        for attr in bo.get("business_object_attributes", []):
            attr_id = attr.get("business_object_attribute_id") if "business_object_attribute_id" in attr else attr.get("id")
            attr_name = attr.get("business_object_attribute_name") if "business_object_attribute_name" in attr else attr.get("name")
            attr_desc = attr.get("business_object_attribute_description") if "business_object_attribute_description" in attr else attr.get("description")
            attr_type = attr.get("business_object_attribute_type") if "business_object_attribute_type" in attr else (attr.get("data_type") or attr.get("business_object_attribute_type"))
            attr_example = attr.get("business_object_attribute_example") if "business_object_attribute_example" in attr else attr.get("example")

            attrs_remapped.append({
                "business_object_attribute_id": attr_id or 0,
                "business_object_attribute_name": attr_name or "",
                "business_object_attribute_description": attr_desc or "",
                "business_object_attribute_type": attr_type or "string",
                "business_object_attribute_example": attr_example or "",
                "updated_at": get_updated_at(attr),
                "kind": "business_object_attribute"
            })
        
        bo_id = bo.get("business_object_id") if "business_object_id" in bo else bo.get("id")
        bo_name = bo.get("business_object_name") if "business_object_name" in bo else bo.get("name")
        bo_desc = bo.get("business_object_description") if "business_object_description" in bo else bo.get("description")

        new_bos.append({
            "business_object_id": bo_id or 0,
            "business_object_name": bo_name or "",
            "business_object_description": bo_desc or "",
            "business_object_attributes": attrs_remapped,
            "updated_at": get_updated_at(bo),
            "kind": "business_object"
        })
    s["business_objects"] = new_bos
    
    # Remap flows
    new_flows = []
    for fl in s.get("flows", []):
        steps_remapped = []
        for step in fl.get("flow_steps", []):
            steps_remapped.append({
                "step_id": step.get("step_id") if "step_id" in step else step.get("id"),
                "step_name": step.get("step_name") if "step_name" in step else step.get("name"),
                "step_description": step.get("step_description") if "step_description" in step else step.get("description"),
                "step_type": step.get("step_type"),
                "position": step.get("position"),
                "actor_ids": step.get("actor_ids", []),
                "input_business_object_ids": step.get("input_business_object_ids", []),
                "output_business_object_ids": step.get("output_business_object_ids", []),
                "next_step_ids": step.get("next_step_ids", []),
                "updated_at": get_updated_at(step),
                "kind": "flow_step"
            })
        new_flows.append({
            "flow_id": fl.get("flow_id") if "flow_id" in fl else fl.get("id"),
            "flow_name": fl.get("flow_name") if "flow_name" in fl else fl.get("name"),
            "flow_description": fl.get("flow_description") if "flow_description" in fl else fl.get("description"),
            "feature_ids": fl.get("feature_ids", []),
            "flow_steps": steps_remapped,
            "updated_at": get_updated_at(fl),
            "kind": "flow"
        })
    s["flows"] = new_flows
    
    return s


async def build_project_snapshot(project_id: int, session: AsyncSession) -> dict:
    """
    Constructs a stable snapshot dictionary of the project's components.
    Only serializes structural properties to avoid hash instability.
    """
    project = await session.get(ProjectModel, project_id)
    if not project:
        raise ValueError("project_not_found")

    # 1. Fetch Actors
    actors_res = await session.execute(
        select(ActorModel).where(ActorModel.project_id == project_id).order_by(ActorModel.id.asc())
    )
    actors = actors_res.scalars().all()

    # 2. Fetch Features
    features_res = await session.execute(
        select(FeatureModel).where(FeatureModel.project_id == project_id).order_by(FeatureModel.id.asc())
    )
    features = features_res.scalars().all()

    # 3. Fetch Scenarios
    scenarios_res = await session.execute(
        select(ScenarioModel).where(ScenarioModel.project_id == project_id).order_by(ScenarioModel.id.asc())
    )
    scenarios = scenarios_res.scalars().all()

    # 4. Fetch Flows
    flows_res = await session.execute(
        select(FlowModel).where(FlowModel.project_id == project_id).order_by(FlowModel.id.asc())
    )
    flows = flows_res.scalars().all()

    # 5. Fetch Business Objects
    business_objects_res = await session.execute(
        select(BusinessObjectModel).where(BusinessObjectModel.project_id == project_id).order_by(BusinessObjectModel.id.asc())
    )
    business_objects = business_objects_res.scalars().all()

    # 6. Fetch Scopes
    scopes_res = await session.execute(
        select(ScopeModel).join(FeatureModel).where(FeatureModel.project_id == project_id).order_by(ScopeModel.id.asc())
    )
    scopes = scopes_res.scalars().all()
    scopes_by_feature = {s.feature_id: s for s in scopes}

    # 7. Fetch all Feature-Actor links directly to avoid lazy loading
    links_res = await session.execute(
        select(feature_actor_table.c.feature_id, feature_actor_table.c.actor_id)
    )
    links = links_res.all()
    actors_by_feature = {}
    for f_id, act_id in links:
        actors_by_feature.setdefault(f_id, []).append(act_id)

    # 8. Fetch Feature relations directly to avoid lazy loading
    rel_res = await session.execute(
        select(FeatureRelationModel.parent_feature_id, FeatureRelationModel.child_feature_id)
    )
    relations = rel_res.all()
    parent_by_child = {r.child_feature_id: r.parent_feature_id for r in relations}
    children_by_parent = {}
    for parent_id, child_id in relations:
        children_by_parent.setdefault(parent_id, []).append(child_id)

    # 9. Fetch ACs directly to avoid lazy loading
    ac_res = await session.execute(
        select(ScenarioAcceptanceCriterionModel).order_by(ScenarioAcceptanceCriterionModel.position.asc())
    )
    acs = ac_res.scalars().all()
    acs_by_scenario = {}
    for ac in acs:
        acs_by_scenario.setdefault(ac.scenario_id, []).append(ac)

    # 10. Fetch Flow features links directly to avoid lazy loading
    ff_res = await session.execute(
        select(flow_feature_table.c.flow_id, flow_feature_table.c.feature_id)
    )
    ff_links = ff_res.all()
    features_by_flow = {}
    for fl_id, feat_id in ff_links:
        features_by_flow.setdefault(fl_id, []).append(feat_id)

    # 11. Fetch Flow Steps, Step Actors, Step Inputs, Step Outputs, Step Nexts
    steps_res = await session.execute(
        select(FlowStepModel).where(FlowStepModel.flow_id.in_([fl.id for fl in flows])).order_by(FlowStepModel.position.asc())
    )
    steps = steps_res.scalars().all()
    steps_by_flow = {}
    for step in steps:
        steps_by_flow.setdefault(step.flow_id, []).append(step)

    step_actor_res = await session.execute(
        select(flow_step_actor_table.c.flow_step_id, flow_step_actor_table.c.actor_id)
    )
    step_actors = step_actor_res.all()
    actors_by_step = {}
    for step_id, act_id in step_actors:
        actors_by_step.setdefault(step_id, []).append(act_id)

    step_input_res = await session.execute(
        select(flow_step_input_business_object_table.c.flow_step_id, flow_step_input_business_object_table.c.business_object_id)
    )
    step_inputs = step_input_res.all()
    inputs_by_step = {}
    for step_id, bo_id in step_inputs:
        inputs_by_step.setdefault(step_id, []).append(bo_id)

    step_output_res = await session.execute(
        select(flow_step_output_business_object_table.c.flow_step_id, flow_step_output_business_object_table.c.business_object_id)
    )
    step_outputs = step_output_res.all()
    outputs_by_step = {}
    for step_id, bo_id in step_outputs:
        outputs_by_step.setdefault(step_id, []).append(bo_id)

    step_next_res = await session.execute(
        select(flow_step_next_table.c.source_step_id, flow_step_next_table.c.target_step_id)
    )
    step_nexts = step_next_res.all()
    next_by_step = {}
    for src_id, tgt_id in step_nexts:
        next_by_step.setdefault(src_id, []).append(tgt_id)

    # Serialize Actors
    actors_json = []
    for a in actors:
        actors_json.append({
            "id": a.id,
            "name": a.name,
            "description": a.description
        })

    # Group scenarios by feature
    scenarios_by_feature = {}
    for s in scenarios:
        scenarios_by_feature.setdefault(s.feature_id, []).append(s)

    # Serialize Features
    features_json = []
    for f in features:
        feat_scenarios = scenarios_by_feature.get(f.id, [])
        scenarios_json = []
        for s in feat_scenarios:
            scenarios_json.append({
                "id": s.id,
                "name": s.name,
                "content": s.content,
                "feature_id": s.feature_id,
                "actor_id": s.actor_id,
                "acceptance_criteria": [
                    {
                        "id": ac.id,
                        "content": ac.content,
                        "position": ac.position
                    }
                    for ac in acs_by_scenario.get(s.id, [])
                ]
            })

        scope_json = None
        scope_obj = scopes_by_feature.get(f.id)
        if scope_obj:
            from backend.services.binary_conversion_service import BinaryConversionService
            scope_json = {
                "id": scope_obj.id,
                "feature_id": scope_obj.feature_id,
                "status": scope_obj.status,
                "reason": scope_obj.reason,
                "positive_summary": scope_obj.positive_summary,
                "negative_summary": scope_obj.negative_summary,
                "positive_picture_base64": BinaryConversionService.bytes_to_base64(scope_obj.positive_picture) if scope_obj.positive_picture is not None else None,
                "negative_picture_base64": BinaryConversionService.bytes_to_base64(scope_obj.negative_picture) if scope_obj.negative_picture is not None else None,
                "kano_category": scope_obj.kano_category,
                "kano_category_name": scope_obj.kano_category_name
            }

        features_json.append({
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "actor_ids": sorted(actors_by_feature.get(f.id, [])),
            "parent_id": parent_by_child.get(f.id),
            "children_ids": sorted(children_by_parent.get(f.id, [])),
            "scenarios": scenarios_json,
            "scope": scope_json
        })

    # Serialize Business Objects
    bos_json = []
    for bo in business_objects:
        # Load attributes directly to avoid lazy loading
        attrs_res = await session.execute(
            select(BusinessObjectAttributeModel)
            .where(BusinessObjectAttributeModel.business_object_id == bo.id)
            .order_by(BusinessObjectAttributeModel.id.asc())
        )
        attributes = attrs_res.scalars().all()
        
        bos_json.append({
            "id": bo.id,
            "name": bo.name,
            "description": bo.description,
            "business_object_attributes": [
                {
                    "id": attr.id,
                    "name": attr.name,
                    "description": attr.description,
                    "data_type": attr.data_type,
                    "example": attr.example
                }
                for attr in attributes
            ]
        })

    # Serialize Flows
    flows_json = []
    for fl in flows:
        flow_steps_serialized = []
        for step in steps_by_flow.get(fl.id, []):
            flow_steps_serialized.append({
                "id": step.id,
                "name": step.name,
                "description": step.description,
                "step_type": step.step_type,
                "position": step.position,
                "actor_ids": sorted(actors_by_step.get(step.id, [])),
                "input_business_object_ids": sorted(inputs_by_step.get(step.id, [])),
                "output_business_object_ids": sorted(outputs_by_step.get(step.id, [])),
                "next_step_ids": sorted(next_by_step.get(step.id, []))
            })

        flows_json.append({
            "id": fl.id,
            "name": fl.name,
            "description": fl.description,
            "feature_ids": sorted(features_by_flow.get(fl.id, [])),
            "flow_steps": flow_steps_serialized
        })

    # Assemble
    snapshot = {
        "project_id": project.public_id,
        "name": project.name,
        "description": project.description,
        "user_requirements": project.user_requirements,
        "actors": actors_json,
        "features": features_json,
        "business_objects": bos_json,
        "flows": flows_json
    }
    return snapshot


class PreviewShadowProjectCreator:
    pass
