from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.stage_gates.stage_gate_evaluator import StageGateEvaluator
from backend.core.shadow_preview.shadow_patch_validator import ShadowPatchValidator
from backend.database.database import AsyncSessionLocal
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
    PreviewShadowDraftModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
    flow_step_next_table,
    beijing_now,
)
from backend.api.schemas.project_schema import ProjectDetailResponse
from backend.api.services.prototype_generation_service import PrototypeGenerationService

prototype_generation_service = PrototypeGenerationService()


def calculate_stable_snapshot_hash(snapshot: dict) -> str:
    """
    Computes SHA-256 hash based on canonical JSON sorting,
    ignoring unstable/transient properties.
    """
    dumped = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def _remap_snapshot_to_pydantic(snapshot: dict) -> dict:
    import copy
    s = copy.deepcopy(snapshot)
    
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
                    "kind": "acceptance_criterion"
                })
            scenarios_remapped.append({
                "scenario_id": sc.get("scenario_id") if "scenario_id" in sc else sc.get("id"),
                "scenario_name": sc.get("scenario_name") if "scenario_name" in sc else sc.get("name"),
                "scenario_content": sc.get("scenario_content") if "scenario_content" in sc else sc.get("content"),
                "feature_id": sc.get("feature_id"),
                "actor_id": sc.get("actor_id"),
                "acceptance_criteria": ac_remapped,
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
                "kano_category": scope_obj.get("kano_category"),
                "kano_category_name": scope_obj.get("kano_category_name"),
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
            "kind": "feature"
        })
    s["features"] = new_features
    
    # Remap business objects
    new_bos = []
    for bo in s.get("business_objects", []):
        attrs_remapped = []
        for attr in bo.get("business_object_attributes", []):
            attrs_remapped.append({
                "business_object_attribute_id": attr.get("business_object_attribute_id") if "business_object_attribute_id" in attr else attr.get("id"),
                "business_object_attribute_name": attr.get("business_object_attribute_name") if "business_object_attribute_name" in attr else attr.get("name"),
                "business_object_attribute_description": attr.get("business_object_attribute_description") if "business_object_attribute_description" in attr else attr.get("description"),
                "business_object_attribute_type": attr.get("business_object_attribute_type") if "business_object_attribute_type" in attr else (attr.get("data_type") or attr.get("business_object_attribute_type")),
                "business_object_attribute_example": attr.get("business_object_attribute_example") if "business_object_attribute_example" in attr else attr.get("example"),
                "kind": "business_object_attribute"
            })
        new_bos.append({
            "business_object_id": bo.get("business_object_id") if "business_object_id" in bo else bo.get("id"),
            "business_object_name": bo.get("business_object_name") if "business_object_name" in bo else bo.get("name"),
            "business_object_description": bo.get("business_object_description") if "business_object_description" in bo else bo.get("description"),
            "business_object_attributes": attrs_remapped,
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
                "kind": "flow_step"
            })
        new_flows.append({
            "flow_id": fl.get("flow_id") if "flow_id" in fl else fl.get("id"),
            "flow_name": fl.get("flow_name") if "flow_name" in fl else fl.get("name"),
            "flow_description": fl.get("flow_description") if "flow_description" in fl else fl.get("description"),
            "feature_ids": fl.get("feature_ids", []),
            "flow_steps": steps_remapped,
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
            scope_json = {
                "id": scope_obj.id,
                "feature_id": scope_obj.feature_id,
                "status": scope_obj.status,
                "reason": scope_obj.reason,
                "positive_summary": scope_obj.positive_summary,
                "negative_summary": scope_obj.negative_summary,
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
        "project_id": project.id,
        "name": project.name,
        "description": project.description,
        "user_requirements": project.user_requirements,
        "actors": actors_json,
        "features": features_json,
        "business_objects": bos_json,
        "flows": flows_json
    }
    return snapshot


class PreviewShadowConvergenceService:
    def __init__(self) -> None:
        self.gate_evaluator = StageGateEvaluator()

    async def converge_shadow_snapshot_task(self, project_id: int, draft_id: str) -> None:
        """
        Background AsyncIO task worker with isolated database session context.
        """
        await asyncio.sleep(0.5)  # Let parent request return safely
        
        async with AsyncSessionLocal() as session:
            try:
                # 1. Fetch Draft
                draft_res = await session.execute(
                    select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                )
                draft = draft_res.scalar_one_or_none()
                if not draft:
                    return

                base_snapshot = draft.base_snapshot_json
                
                # Extract feedback from error_message if regenerating
                feedback = ""
                if draft.error_message and draft.error_message.startswith("Regenerating draft with feedback: "):
                    feedback = draft.error_message[len("Regenerating draft with feedback: "):].strip()
                
                # 2. Run convergence AI helper to build patch
                patch = self._generate_shadow_patch(base_snapshot, feedback)
                
                # 3. Validate patch
                ShadowPatchValidator.validate_patch(patch, base_snapshot, project_id)
                
                # 4. Construct virtual shadow snapshot (with negative IDs to appease Pydantic type validator)
                shadow_snapshot, temp_id_to_neg_int = self._apply_patch_to_snapshot(base_snapshot, patch)
                
                # 5. Parse shadow_snapshot as ProjectDetailResponse
                remapped_snapshot = _remap_snapshot_to_pydantic(shadow_snapshot)
                shadow_detail = ProjectDetailResponse.model_validate(remapped_snapshot)
                
                # 6. Generate simulated UI prototype pages using PrototypeGenerationService
                generator_input = prototype_generation_service._build_generator_input(
                    detail=shadow_detail,
                    gherkin_specs=[]
                )
                targets = prototype_generation_service._build_role_feature_targets(
                    generator_input=generator_input,
                    detail=shadow_detail
                )
                
                pages = await prototype_generation_service._generate_pages_concurrently(targets)
                first_page = pages[0] if pages else prototype_generation_service._empty_page(project_id)
                
                # Build mock PrototypePreviewResponse payload
                prototype_preview = {
                    "prototypeId": 0,
                    "projectId": project_id,
                    "html": first_page["html"],
                    "javascript": first_page["javascript"],
                    "css": first_page["css"],
                    "pages": pages,
                    "source": "shadow_project",
                    "status": "ready",
                    "createdAt": beijing_now().isoformat(),
                    "updatedAt": beijing_now().isoformat(),
                    "shadowDraftId": draft_id
                }

                # Calculate hash of final shadow snapshot
                shadow_hash = calculate_stable_snapshot_hash(shadow_snapshot)

                # Update database draft record
                draft.status = "ready"
                draft.shadow_snapshot_hash = shadow_hash
                draft.shadow_snapshot_json = remapped_snapshot
                draft.patch_json = patch
                draft.prototype_preview_json = prototype_preview
                await session.commit()

            except Exception as e:
                # Log error and fail gracefully
                import traceback
                error_trace = traceback.format_exc()
                
                # Re-query inside another transaction if session is poisoned
                try:
                    await session.rollback()
                    draft_res = await session.execute(
                        select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                    )
                    draft = draft_res.scalar_one_or_none()
                    if draft:
                        draft.status = "failed"
                        draft.error_message = f"Convergence failed: {str(e)}\n{error_trace}"
                        await session.commit()
                except Exception:
                    pass

    @staticmethod
    def _generate_shadow_patch(base_snapshot: dict, feedback: str = "") -> dict:
        """
        Consolidated shadow patch generator. Examines project requirements and baseline
        data, then generates a complete list of missing actors, features, flows, and scopes
        to satisfy all gates. Optional user feedback is parsed to adjust names and details.
        """
        actors = base_snapshot.get("actors", [])
        features = base_snapshot.get("features", [])
        scenarios = [s for f in features for s in f.get("scenarios", [])]
        business_objects = base_snapshot.get("business_objects", [])
        flows = base_snapshot.get("flows", [])

        # Determine domain context
        req_text = (base_snapshot.get("user_requirements", "") + " " + base_snapshot.get("name", "")).lower()
        is_music = "music" in req_text or "音乐" in req_text or "播放器" in req_text
        is_library = "library" in req_text or "图书" in req_text or "借阅" in req_text or "书籍" in req_text
        
        # Select domain names
        actor_name = "普通用户"
        actor_desc = "日常使用系统的最终用户"
        feature_name = "业务功能探索"
        feature_desc = "用于处理系统核心业务逻辑"
        bo_name = "核心业务实体"
        bo_desc = "系统主要业务数据载体"

        if is_music:
            actor_name = "听众"
            actor_desc = "浏览、收听和管理歌曲的音乐听众"
            feature_name = "音乐在线播放"
            feature_desc = "支持点击歌曲播放、调节进度和音量"
            bo_name = "音乐歌曲"
            bo_desc = "记录音频文件信息与播放元数据"
        elif is_library:
            actor_name = "读者"
            actor_desc = "借阅图书与检索书籍的图书馆会员"
            feature_name = "图书在线检索"
            feature_desc = "通过书名、作者或分类快速检索书籍"
            bo_name = "图书文献"
            bo_desc = "存储图书ISBN、名称、馆藏状态"

        # Initialize patch container
        patch = {
            "actors_added": [],
            "features_added": [],
            "feature_actor_links_added": [],
            "scenarios_added": [],
            "acceptance_criteria_added": [],
            "business_objects_added": [],
            "business_object_attributes_added": [],
            "flows_added": [],
            "flow_steps_added": [],
            "scopes_added": []
        }

        current_actors = list(actors)
        leaf_features = [f for f in features if not f.get("children_ids")]
        current_leaf_features = list(leaf_features)
        current_bos = list(business_objects)

        # Apply User Feedback if present to override or ALWAYS append explicitly requested entities
        if feedback:
            fb = feedback.strip()
            # 1. Parse custom actor names
            import re
            actor_match = re.search(r"(?:角色|用户|actor)\s*[:：]\s*(\w+)", fb, re.IGNORECASE)
            if actor_match:
                actor_name = actor_match.group(1)
                actor_desc = f"根据用户反馈定制的专属角色（{actor_name}）"
                if not any(a.get("name") == actor_name for a in current_actors):
                    new_act = {
                        "temp_id": "tmp_actor_custom_fb",
                        "name": actor_name,
                        "description": actor_desc
                    }
                    patch["actors_added"].append(new_act)
                    current_actors.append({"id": "tmp_actor_custom_fb", "name": actor_name, "description": actor_desc})
            elif "管理员" in fb or "admin" in fb.lower():
                actor_name = "系统管理员"
                actor_desc = "负责规则配置与数据审阅的管理人员"
                if not any(a.get("name") == actor_name for a in current_actors):
                    new_act = {
                        "temp_id": "tmp_actor_custom_fb",
                        "name": actor_name,
                        "description": actor_desc
                    }
                    patch["actors_added"].append(new_act)
                    current_actors.append({"id": "tmp_actor_custom_fb", "name": actor_name, "description": actor_desc})

            # 2. Parse custom feature names
            feat_match = re.search(r"(?:功能|模块|feature)\s*[:：]\s*(\w+)", fb, re.IGNORECASE)
            if feat_match:
                feature_name = feat_match.group(1)
                feature_desc = f"根据用户反馈定制的系统功能（{feature_name}）"
                if not any(f.get("name") == feature_name for f in features):
                    patch["features_added"].append({
                        "temp_id": "tmp_feature_custom_fb",
                        "name": feature_name,
                        "description": feature_desc,
                        "parent_ref": None
                    })
                    current_leaf_features.append({
                        "id": "tmp_feature_custom_fb",
                        "name": feature_name,
                        "description": feature_desc,
                        "actor_ids": [],
                        "scenarios": []
                    })
            elif "高级" in fb or "优化" in fb:
                feature_name = "系统高级探索面板"
                feature_desc = "针对复杂场景的高级调优和决策看板"
                if not any(f.get("name") == feature_name for f in features):
                    patch["features_added"].append({
                        "temp_id": "tmp_feature_custom_fb",
                        "name": feature_name,
                        "description": feature_desc,
                        "parent_ref": None
                    })
                    current_leaf_features.append({
                        "id": "tmp_feature_custom_fb",
                        "name": feature_name,
                        "description": feature_desc,
                        "actor_ids": [],
                        "scenarios": []
                    })

            # 3. Parse custom business object names
            bo_match = re.search(r"(?:对象|实体|bo|数据)\s*[:：]\s*(\w+)", fb, re.IGNORECASE)
            if bo_match:
                bo_name = bo_match.group(1)
                bo_desc = f"用户定制业务交互数据模型（{bo_name}）"
                if not any(b.get("name") == bo_name for b in current_bos):
                    patch["business_objects_added"].append({
                        "temp_id": "tmp_bo_custom_fb",
                        "name": bo_name,
                        "description": bo_desc
                    })
                    patch["business_object_attributes_added"].extend([
                        {
                            "business_object_ref": "tmp_bo_custom_fb",
                            "name": "编号",
                            "description": "唯一标识",
                            "data_type": "string",
                            "example": "FB001"
                        }
                    ])
                    current_bos.append({"id": "tmp_bo_custom_fb", "name": bo_name, "business_object_attributes": []})

            # Fallback customization for general sentences
            if not actor_match and not feat_match and not bo_match:
                phrases = [p for p in re.split(r'[,.!?，。！？;；]', fb) if len(p.strip()) >= 2]
                if phrases:
                    feature_name = f"反馈响应：{phrases[0][:20]}"
                    feature_desc = f"基于用户调优意向（“{fb}”）智能收敛生成的定制规约节点"
                    if not any(f.get("name") == feature_name for f in features):
                        patch["features_added"].append({
                            "temp_id": "tmp_feature_custom_fb",
                            "name": feature_name,
                            "description": feature_desc,
                            "parent_ref": None
                        })
                        current_leaf_features.append({
                            "id": "tmp_feature_custom_fb",
                            "name": feature_name,
                            "description": feature_desc,
                            "actor_ids": [],
                            "scenarios": []
                        })

        # 1. Fill missing Actors
        if not current_actors:
            new_actor = {
                "temp_id": "tmp_actor_1",
                "name": actor_name,
                "description": actor_desc
            }
            patch["actors_added"].append(new_actor)
            current_actors.append({"id": "tmp_actor_1", "name": actor_name, "description": actor_desc})

        # 2. Fill missing Features
        if not current_leaf_features:
            new_feat = {
                "temp_id": "tmp_feature_1",
                "name": feature_name,
                "description": feature_desc,
                "parent_ref": None
            }
            patch["features_added"].append(new_feat)
            current_leaf_features.append({
                "id": "tmp_feature_1",
                "name": feature_name,
                "description": feature_desc,
                "actor_ids": [],
                "scenarios": []
            })

        # 3. Connect Features to Actors
        active_actor_ref = f"actor:{current_actors[0]['id']}" if isinstance(current_actors[0]['id'], int) else current_actors[0]['id']
        
        for lf in current_leaf_features:
            has_real_actors = len(lf.get("actor_ids", [])) > 0
            has_patch_actors = any(l["feature_ref"] == lf["id"] for l in patch["feature_actor_links_added"])
            
            if not has_real_actors and not has_patch_actors:
                feat_ref = f"feature:{lf['id']}" if isinstance(lf['id'], int) else lf['id']
                patch["feature_actor_links_added"].append({
                    "feature_ref": feat_ref,
                    "actor_ref": active_actor_ref
                })
                # update local
                if "tmp_" in lf["id"]:
                    lf["actor_ids"].append(active_actor_ref)

        # 4. Fill missing Scenarios
        for lf in current_leaf_features:
            has_real_scenarios = len(lf.get("scenarios", [])) > 0
            has_patch_scenarios = any(s["feature_ref"] == lf["id"] for s in patch["scenarios_added"])
            
            if not has_real_scenarios and not has_patch_scenarios:
                feat_ref = f"feature:{lf['id']}" if isinstance(lf['id'], int) else lf['id']
                temp_scenario_id = f"tmp_scenario_{len(patch['scenarios_added']) + 1}"
                
                patch["scenarios_added"].append({
                    "temp_id": temp_scenario_id,
                    "name": f"典型使用场景",
                    "content": f"Given 用户打开系统, When 执行 {lf['name']} 功能, Then 系统应正确返回响应。",
                    "feature_ref": feat_ref,
                    "actor_ref": active_actor_ref
                })
                lf["scenarios"].append({
                    "id": temp_scenario_id,
                    "name": "典型使用场景",
                    "content": f"Given 用户打开系统, When 执行 {lf['name']} 功能, Then 系统应正确返回响应。",
                    "feature_id": lf["id"],
                    "actor_id": current_actors[0]["id"],
                    "acceptance_criteria": []
                })

        # 5. Fill missing ACs
        all_local_scenarios = [s for lf in current_leaf_features for s in lf["scenarios"]]
        for sc in all_local_scenarios:
            has_real_ac = len(sc.get("acceptance_criteria", [])) > 0
            has_patch_ac = any(ac["scenario_ref"] == sc["id"] for ac in patch["acceptance_criteria_added"])
            
            if not has_real_ac and not has_patch_ac:
                sc_ref = f"scenario:{sc['id']}" if isinstance(sc['id'], int) else sc['id']
                patch["acceptance_criteria_added"].append({
                    "scenario_ref": sc_ref,
                    "content": "系统应当在 1 秒以内渲染完整的主操作界面并弹出操作成功框。",
                    "position": 1
                })

        # 6. Fill missing Flows
        current_flows = list(flows)
        if not current_flows:
            new_flow_id = "tmp_flow_1"
            first_lf = current_leaf_features[0]
            first_feat_ref = f"feature:{first_lf['id']}" if isinstance(first_lf['id'], int) else first_lf['id']
            
            patch["flows_added"].append({
                "temp_id": new_flow_id,
                "name": "核心业务流编排",
                "description": "串联系统核心交互的主力业务流",
                "feature_refs": [first_feat_ref]
            })
            current_flows.append({
                "id": new_flow_id,
                "name": "核心业务流编排",
                "description": "串联系统核心交互的主力业务流",
                "flow_steps": []
            })

        # 7. Fill missing Flow Steps
        for fl in current_flows:
            has_real_steps = len(fl.get("flow_steps", [])) > 0
            has_patch_steps = any(st["flow_ref"] == fl["id"] for st in patch["flow_steps_added"])
            
            if not has_real_steps and not has_patch_steps:
                flow_ref = f"flow:{fl['id']}" if isinstance(fl['id'], int) else fl['id']
                temp_step_id = "tmp_step_1"
                
                # Check for BO usage
                active_bo_refs = []
                if business_objects:
                    active_bo_refs = [f"business_object:{business_objects[0]['id']}"]
                elif patch["business_objects_added"]:
                    active_bo_refs = [patch["business_objects_added"][0]["temp_id"]]
                else:
                    # Add transient BO
                    new_bo = {
                        "temp_id": "tmp_bo_1",
                        "name": bo_name,
                        "description": bo_desc
                    }
                    patch["business_objects_added"].append(new_bo)
                    active_bo_refs = ["tmp_bo_1"]

                patch["flow_steps_added"].append({
                    "temp_id": temp_step_id,
                    "flow_ref": flow_ref,
                    "name": "用户触发核心请求",
                    "description": "点击触发业务响应",
                    "step_type": "actorAction",
                    "position": 1,
                    "actor_refs": [active_actor_ref],
                    "input_bo_refs": [],
                    "output_bo_refs": active_bo_refs,
                    "next_step_refs": []
                })

        # 8. Fill missing Business Object Attributes
        current_bos = list(business_objects)
        for tbo in patch["business_objects_added"]:
            current_bos.append({"id": tbo["temp_id"], "name": tbo["name"], "business_object_attributes": []})
            
        for bo in current_bos:
            has_real_attrs = len(bo.get("business_object_attributes", [])) > 0
            has_patch_attrs = any(attr["business_object_ref"] == bo["id"] for attr in patch["business_object_attributes_added"])
            
            if not has_real_attrs and not has_patch_attrs:
                bo_ref = f"business_object:{bo['id']}" if isinstance(bo['id'], int) else bo['id']
                patch["business_object_attributes_added"].extend([
                    {
                        "business_object_ref": bo_ref,
                        "name": "标识号",
                        "description": "主键ID标识",
                        "data_type": "string",
                        "example": "1001"
                    },
                    {
                        "business_object_ref": bo_ref,
                        "name": "名称",
                        "description": "业务名称",
                        "data_type": "string",
                        "example": "示例数据"
                    }
                ])

        # 9. Fill missing Scope Decisions
        for lf in current_leaf_features:
            has_real_scope = lf.get("scope") is not None
            has_patch_scope = any(sc["feature_ref"] == lf["id"] for sc in patch["scopes_added"])
            
            if not has_real_scope and not has_patch_scope:
                feat_ref = f"feature:{lf['id']}" if isinstance(lf['id'], int) else lf['id']
                patch["scopes_added"].append({
                    "feature_ref": feat_ref,
                    "status": "CURRENT",
                    "reason": "AI影子收敛补充，列为本期迭代必选范围。",
                    "kano_category": "M",
                    "kano_category_name": "Must-be",
                    "positive_summary": "用户强烈需要，有它是必须的。",
                    "negative_summary": "没有会非常失望。"
                })

        return patch

    @staticmethod
    def _apply_patch_to_snapshot(base_snapshot: dict, patch: dict) -> tuple[dict, dict[str, int]]:
        """
        Merges patch_json into base_snapshot, translating all transient 'tmp_' string references
        to negative integers to satisfy Pydantic Model validators without violating database schema.
        """
        import copy
        snapshot = copy.deepcopy(base_snapshot)

        # 1. Map all temp_id values in the patch to unique negative integers
        temp_id_to_neg_int: dict[str, int] = {}
        neg_counter = -1001

        def assign_neg_int(tid: str) -> None:
            nonlocal neg_counter
            if tid not in temp_id_to_neg_int:
                temp_id_to_neg_int[tid] = neg_counter
                neg_counter -= 1

        for a in patch.get("actors_added", []):
            assign_neg_int(a["temp_id"])
        for f in patch.get("features_added", []):
            assign_neg_int(f["temp_id"])
        for s in patch.get("scenarios_added", []):
            assign_neg_int(s["temp_id"])
        for b in patch.get("business_objects_added", []):
            assign_neg_int(b["temp_id"])
        for fl in patch.get("flows_added", []):
            assign_neg_int(fl["temp_id"])
        for st in patch.get("flow_steps_added", []):
            assign_neg_int(st["temp_id"])

        # Helper to convert reference string (starts with 'tmp_' or 'type:id') to integer ID
        def resolve_ref_to_int(ref: str) -> int:
            if not ref:
                return 0
            if ref.startswith("tmp_"):
                return temp_id_to_neg_int.get(ref, 0)
            parts = ref.split(":")
            if len(parts) == 2:
                return int(parts[1])
            return 0

        # Apply Actors
        for a in patch.get("actors_added", []):
            snapshot["actors"].append({
                "actor_id": temp_id_to_neg_int[a["temp_id"]],
                "actor_name": a["name"],
                "actor_description": a["description"]
            })

        # Apply Features
        features_by_id = {f["id"]: f for f in snapshot["features"]}
        features_added_by_neg = {}

        for f in patch.get("features_added", []):
            neg_id = temp_id_to_neg_int[f["temp_id"]]
            new_feat_dict = {
                "feature_id": neg_id,
                "feature_name": f["name"],
                "feature_description": f["description"],
                "actor_ids": [],
                "parent_id": resolve_ref_to_int(f["parent_ref"]) if f.get("parent_ref") else None,
                "children_ids": [],
                "scenarios": [],
                "scope": None
            }
            snapshot["features"].append(new_feat_dict)
            features_added_by_neg[neg_id] = new_feat_dict

        # Apply Feature-Actor Links
        for link in patch.get("feature_actor_links_added", []):
            f_id = resolve_ref_to_int(link["feature_ref"])
            a_id = resolve_ref_to_int(link["actor_ref"])
            
            # Find in base snapshot
            feat = features_by_id.get(f_id)
            if not feat:
                feat = features_added_by_neg.get(f_id)
            
            if feat and a_id not in feat["actor_ids"]:
                feat["actor_ids"].append(a_id)

        # Apply Scenarios
        scenarios_added_by_neg = {}
        for s in patch.get("scenarios_added", []):
            neg_id = temp_id_to_neg_int[s["temp_id"]]
            f_id = resolve_ref_to_int(s["feature_ref"])
            a_id = resolve_ref_to_int(s["actor_ref"])
            
            new_scenario = {
                "scenario_id": neg_id,
                "scenario_name": s["name"],
                "scenario_content": s["content"],
                "feature_id": f_id,
                "actor_id": a_id,
                "acceptance_criteria": []
            }
            scenarios_added_by_neg[neg_id] = new_scenario
            
            # Add to feature
            feat = features_by_id.get(f_id) or features_added_by_neg.get(f_id)
            if feat:
                feat["scenarios"].append(new_scenario)

        # Apply ACs
        for ac in patch.get("acceptance_criteria_added", []):
            sc_id = resolve_ref_to_int(ac["scenario_ref"])
            # Find scenario in snapshot
            target_sc = None
            for f in snapshot["features"]:
                for s in f["scenarios"]:
                    if (s.get("scenario_id") or s.get("id")) == sc_id:
                        target_sc = s
                        break
            if target_sc:
                # generate a negative AC ID
                ac_neg_id = neg_counter
                neg_counter -= 1
                target_sc["acceptance_criteria"].append({
                    "criterion_id": ac_neg_id,
                    "criterion_content": ac["content"],
                    "position": ac["position"]
                })

        # Apply Business Objects
        bos_by_id = {b["id"]: b for b in snapshot["business_objects"]}
        bos_added_by_neg = {}
        for bo in patch.get("business_objects_added", []):
            neg_id = temp_id_to_neg_int[bo["temp_id"]]
            new_bo = {
                "business_object_id": neg_id,
                "business_object_name": bo["name"],
                "business_object_description": bo["description"],
                "business_object_attributes": []
            }
            snapshot["business_objects"].append(new_bo)
            bos_added_by_neg[neg_id] = new_bo

        # Apply BO Attributes
        for attr in patch.get("business_object_attributes_added", []):
            bo_id = resolve_ref_to_int(attr["business_object_ref"])
            target_bo = bos_by_id.get(bo_id) or bos_added_by_neg.get(bo_id)
            if target_bo:
                attr_neg_id = neg_counter
                neg_counter -= 1
                target_bo["business_object_attributes"].append({
                    "business_object_attribute_id": attr_neg_id,
                    "business_object_attribute_name": attr["name"],
                    "business_object_attribute_description": attr["description"],
                    "business_object_attribute_type": attr["data_type"],
                    "business_object_attribute_example": attr["example"]
                })

        # Apply Flows
        flows_added_by_neg = {}
        for fl in patch.get("flows_added", []):
            neg_id = temp_id_to_neg_int[fl["temp_id"]]
            new_flow = {
                "flow_id": neg_id,
                "flow_name": fl["name"],
                "flow_description": fl["description"],
                "feature_ids": [resolve_ref_to_int(fref) for fref in fl["feature_refs"]],
                "flow_steps": []
            }
            snapshot["flows"].append(new_flow)
            flows_added_by_neg[neg_id] = new_flow

        # Apply Flow Steps
        steps_added_by_neg = {}
        for st in patch.get("flow_steps_added", []):
            neg_id = temp_id_to_neg_int[st["temp_id"]]
            flow_id = resolve_ref_to_int(st["flow_ref"])
            
            new_step = {
                "step_id": neg_id,
                "step_name": st["name"],
                "step_description": st["description"],
                "step_type": st["step_type"],
                "position": st["position"],
                "actor_ids": [resolve_ref_to_int(aref) for aref in st.get("actor_refs", [])],
                "input_business_object_ids": [resolve_ref_to_int(iref) for iref in st.get("input_bo_refs", [])],
                "output_business_object_ids": [resolve_ref_to_int(oref) for oref in st.get("output_bo_refs", [])],
                "next_step_ids": [resolve_ref_to_int(nref) for nref in st.get("next_step_refs", [])]
            }
            steps_added_by_neg[neg_id] = new_step
            
            target_flow = next((f for f in snapshot["flows"] if (f.get("flow_id") or f.get("id")) == flow_id), None)
            if target_flow:
                target_flow["flow_steps"].append(new_step)

        # Apply Scopes
        for sc in patch.get("scopes_added", []):
            f_id = resolve_ref_to_int(sc["feature_ref"])
            feat = features_by_id.get(f_id) or features_added_by_neg.get(f_id)
            if feat:
                scope_neg_id = neg_counter
                neg_counter -= 1
                feat["scope"] = {
                    "scope_id": scope_neg_id,
                    "scope_status": sc["status"],
                    "reason": sc["reason"],
                    "positive_summary": sc.get("positive_summary"),
                    "negative_summary": sc.get("negative_summary"),
                    "kano_category": sc.get("kano_category"),
                    "kano_category_name": sc.get("kano_category_name")
                }

        # Resolve children_ids on features added
        for neg_id, feat in features_added_by_neg.items():
            parent_id = feat["parent_id"]
            if parent_id is not None:
                parent_feat = features_by_id.get(parent_id) or features_added_by_neg.get(parent_id)
                if parent_feat and neg_id not in parent_feat["children_ids"]:
                    parent_feat["children_ids"].append(neg_id)

        # Ensure correct snake_case Pydantic model structure
        for f in snapshot["features"]:
            # If leaf features are missing scopes, map them
            if not f.get("children_ids") and not f.get("scope"):
                # Default safety scope
                f["scope"] = {
                    "scope_id": neg_counter,
                    "scope_status": "CURRENT",
                    "reason": "AI影子收敛补充",
                    "kano_category": "M",
                    "kano_category_name": "Must-be"
                }
                neg_counter -= 1

        # Keep snapshot's project details correctly formatted
        snapshot["project_id"] = base_snapshot.get("project_id")
        snapshot["project_name"] = base_snapshot.get("name")
        snapshot["project_description"] = base_snapshot.get("description")
        snapshot["user_requirements"] = base_snapshot.get("user_requirements")
        snapshot["kano_status"] = "generated"  # Simulated converged status

        return snapshot, temp_id_to_neg_int

    async def commit_shadow_draft(self, project_id: int, draft_id: str, session: AsyncSession) -> None:
        """
        Transactional write-back implementation mapping transient IDs to auto-increment DB IDs
        in a single atomic write transaction.
        """
        # 1. Fetch Draft
        draft_res = await session.execute(
            select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
        )
        draft = draft_res.scalar_one_or_none()
        if not draft:
            raise ValueError("shadow_draft_not_found")
        if draft.status != "ready":
            raise ValueError("shadow_draft_not_ready")

        # 2. Hash conflict verification
        current_snapshot = await build_project_snapshot(project_id, session)
        current_hash = calculate_stable_snapshot_hash(current_snapshot)
        if current_hash != draft.base_snapshot_hash:
            raise ValueError("shadow_draft_conflict")

        # 3. Secondary validator check
        patch = draft.patch_json
        ShadowPatchValidator.validate_patch(patch, current_snapshot, project_id)

        # 4. Map temporary string IDs to new database IDs
        actor_id_map: dict[str, int] = {}
        feature_id_map: dict[str, int] = {}
        scenario_id_map: dict[str, int] = {}
        bo_id_map: dict[str, int] = {}
        flow_id_map: dict[str, int] = {}
        step_id_map: dict[str, int] = {}

        # Helpers to resolve a ref string (e.g. "actor:12" or "tmp_actor_1") to integer ID
        def resolve_actor_id(ref: str) -> int:
            if ref.startswith("tmp_"):
                return actor_id_map[ref]
            return int(ref.split(":")[1])

        def resolve_feature_id(ref: str) -> int:
            if ref.startswith("tmp_"):
                return feature_id_map[ref]
            return int(ref.split(":")[1])

        def resolve_scenario_id(ref: str) -> int:
            if ref.startswith("tmp_"):
                return scenario_id_map[ref]
            return int(ref.split(":")[1])

        def resolve_bo_id(ref: str) -> int:
            if ref.startswith("tmp_"):
                return bo_id_map[ref]
            return int(ref.split(":")[1])

        def resolve_flow_id(ref: str) -> int:
            if ref.startswith("tmp_"):
                return flow_id_map[ref]
            return int(ref.split(":")[1])

        def resolve_step_id(ref: str) -> int:
            if ref.startswith("tmp_"):
                return step_id_map[ref]
            return int(ref.split(":")[1])

        # Step A: Insert Actors
        for a in patch.get("actors_added", []):
            actor = ActorModel(
                project_id=project_id,
                name=a["name"],
                description=a["description"]
            )
            session.add(actor)
            await session.flush()
            actor_id_map[a["temp_id"]] = actor.id

        # Step B: Insert Features (topological multi-pass parent resolution)
        feats_to_insert = list(patch.get("features_added", []))
        while feats_to_insert:
            inserted_in_this_pass = 0
            remaining = []
            
            for f in feats_to_insert:
                parent_ref = f.get("parent_ref")
                
                # Check if parent is resolved or None
                can_insert = False
                parent_id = None
                
                if parent_ref is None:
                    can_insert = True
                elif parent_ref.startswith("feature:"):
                    can_insert = True
                    parent_id = int(parent_ref.split(":")[1])
                elif parent_ref.startswith("tmp_") and parent_ref in feature_id_map:
                    can_insert = True
                    parent_id = feature_id_map[parent_ref]
                
                if can_insert:
                    feat = FeatureModel(
                        project_id=project_id,
                        name=f["name"],
                        description=f["description"]
                    )
                    session.add(feat)
                    await session.flush()
                    feature_id_map[f["temp_id"]] = feat.id
                    
                    # If has parent, save to FeatureRelationModel
                    if parent_id is not None:
                        # Find next position under parent
                        pos_res = await session.execute(
                            select(func.count(FeatureRelationModel.id)).where(
                                FeatureRelationModel.parent_feature_id == parent_id
                            )
                        )
                        next_pos = pos_res.scalar_one()
                        
                        relation = FeatureRelationModel(
                            parent_feature_id=parent_id,
                            child_feature_id=feat.id,
                            position=next_pos
                        )
                        session.add(relation)
                        await session.flush()

                    inserted_in_this_pass += 1
                else:
                    remaining.append(f)
            
            if inserted_in_this_pass == 0:
                raise ValueError("Cyclic dependency detected in features_added!")
            feats_to_insert = remaining

        # Step C: Insert Feature-Actor Links
        for link in patch.get("feature_actor_links_added", []):
            feat_id = resolve_feature_id(link["feature_ref"])
            act_id = resolve_actor_id(link["actor_ref"])
            await session.execute(
                feature_actor_table.insert().values(feature_id=feat_id, actor_id=act_id)
            )

        # Step D: Insert Scenarios
        for s in patch.get("scenarios_added", []):
            feat_id = resolve_feature_id(s["feature_ref"])
            act_id = resolve_actor_id(s["actor_ref"])
            scenario = ScenarioModel(
                project_id=project_id,
                feature_id=feat_id,
                actor_id=act_id,
                name=s["name"],
                content=s["content"]
            )
            session.add(scenario)
            await session.flush()
            scenario_id_map[s["temp_id"]] = scenario.id

        # Step E: Insert ACs
        for ac in patch.get("acceptance_criteria_added", []):
            sc_id = resolve_scenario_id(ac["scenario_ref"])
            criterion = ScenarioAcceptanceCriterionModel(
                scenario_id=sc_id,
                content=ac["content"],
                position=ac["position"]
            )
            session.add(criterion)
            await session.flush()

        # Step F: Insert Business Objects
        for bo in patch.get("business_objects_added", []):
            business_object = BusinessObjectModel(
                project_id=project_id,
                name=bo["name"],
                description=bo["description"]
            )
            session.add(business_object)
            await session.flush()
            bo_id_map[bo["temp_id"]] = business_object.id

        # Step G: Insert BO Attributes
        for attr in patch.get("business_object_attributes_added", []):
            bo_id = resolve_bo_id(attr["business_object_ref"])
            bo_attr = BusinessObjectAttributeModel(
                business_object_id=bo_id,
                name=attr["name"],
                description=attr["description"],
                data_type=attr["data_type"],
                example=attr["example"]
            )
            session.add(bo_attr)
            await session.flush()

        # Step H: Insert Flows
        for fl in patch.get("flows_added", []):
            flow = FlowModel(
                project_id=project_id,
                name=fl["name"],
                description=fl["description"]
            )
            session.add(flow)
            await session.flush()
            flow_id_map[fl["temp_id"]] = flow.id
            
            # Associate features
            for fref in fl.get("feature_refs", []):
                feat_id = resolve_feature_id(fref)
                await session.execute(
                    flow_feature_table.insert().values(flow_id=flow.id, feature_id=feat_id)
                )

        # Step I: Insert Flow Steps (Pass 1 - insert models)
        for st in patch.get("flow_steps_added", []):
            flow_id = resolve_flow_id(st["flow_ref"])
            step = FlowStepModel(
                flow_id=flow_id,
                name=st["name"],
                description=st["description"],
                step_type=st["step_type"],
                position=st["position"]
            )
            session.add(step)
            await session.flush()
            step_id_map[st["temp_id"]] = step.id

        # Step J: Insert Flow Steps (Pass 2 - insert associations)
        for st in patch.get("flow_steps_added", []):
            step_id = step_id_map[st["temp_id"]]
            
            for aref in st.get("actor_refs", []):
                act_id = resolve_actor_id(aref)
                await session.execute(
                    flow_step_actor_table.insert().values(flow_step_id=step_id, actor_id=act_id)
                )
            for iref in st.get("input_bo_refs", []):
                bo_id = resolve_bo_id(iref)
                await session.execute(
                    flow_step_input_business_object_table.insert().values(
                        flow_step_id=step_id, business_object_id=bo_id
                    )
                )
            for oref in st.get("output_bo_refs", []):
                bo_id = resolve_bo_id(oref)
                await session.execute(
                    flow_step_output_business_object_table.insert().values(
                        flow_step_id=step_id, business_object_id=bo_id
                    )
                )
            for nref in st.get("next_step_refs", []):
                next_step_id = resolve_step_id(nref)
                await session.execute(
                    flow_step_next_table.insert().values(
                        source_step_id=step_id, target_step_id=next_step_id
                    )
                )

        # Step K: Insert Scopes
        for sc in patch.get("scopes_added", []):
            feat_id = resolve_feature_id(sc["feature_ref"])
            
            # Check if scope exists for feature
            scope_res = await session.execute(
                select(ScopeModel).where(ScopeModel.feature_id == feat_id)
            )
            existing_scope = scope_res.scalar_one_or_none()
            
            if existing_scope:
                existing_scope.status = sc["status"]
                existing_scope.reason = sc["reason"]
                existing_scope.kano_category = sc.get("kano_category")
                existing_scope.kano_category_name = sc.get("kano_category_name")
                existing_scope.positive_summary = sc.get("positive_summary")
                existing_scope.negative_summary = sc.get("negative_summary")
            else:
                new_scope = ScopeModel(
                    feature_id=feat_id,
                    status=sc["status"],
                    reason=sc["reason"],
                    kano_category=sc.get("kano_category"),
                    kano_category_name=sc.get("kano_category_name"),
                    positive_summary=sc.get("positive_summary"),
                    negative_summary=sc.get("negative_summary")
                )
                session.add(new_scope)
                await session.flush()

        # Update Project Kano Status to generated (completed)
        project = await session.get(ProjectModel, project_id)
        if project and project.kano_status not in ("generated", "skipped"):
            project.kano_status = "generated"

        # Step L: Clear slot and issue cache by soft deleting/staling perception jobs
        from backend.database.model import PerceptionJobModel
        await session.execute(
            delete(PerceptionJobModel).where(
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage.in_(["what", "how", "scope"])
            )
        )

        # Step M: Finalize Draft setting committed
        draft.status = "committed"
        draft.committed_at = beijing_now()
        await session.flush()

        # Step N: Generate real prototype preview automatically post commit
        await prototype_generation_service.generate_preview(
            project_id=project_id,
            session=session,
            force_regenerate=True
        )

    @staticmethod
    async def discard_shadow_draft(project_id: int, draft_id: str, session: AsyncSession) -> None:
        """
        Soft deletes the shadow draft by updating its status and timestamp.
        """
        draft_res = await session.execute(
            select(PreviewShadowDraftModel).where(
                PreviewShadowDraftModel.project_id == project_id,
                PreviewShadowDraftModel.draft_id == draft_id
            )
        )
        draft = draft_res.scalar_one_or_none()
        if not draft:
            raise ValueError("shadow_draft_not_found")
        
        draft.status = "discarded"
        draft.discarded_at = beijing_now()
