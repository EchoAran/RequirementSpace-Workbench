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
from backend.api.services.service_registry import prototype_generation_service
from backend.core.llm_context import current_llm_context, is_web_request_ctx, LLMRequestContext


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
                "positive_picture_base64": scope_obj.get("positive_picture_base64") or scope_obj.get("positivePictureBase64"),
                "negative_picture_base64": scope_obj.get("negative_picture_base64") or scope_obj.get("negativePictureBase64"),
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


class PreviewShadowConvergenceService:
    def __init__(self) -> None:
        self.gate_evaluator = StageGateEvaluator()

    async def _generate_scopes_for_features(
        self,
        scope_service: Any,
        user_requirements: str,
        feature_nodes: list,
        leaf_feature_nodes: list,
        user_feedback: str = "",
        temp_feat_to_int: dict[str, int] = None
    ) -> list[dict]:
        """
        Generates scopes using the real registered scope generation service
        (either skill-backed or legacy), without querying database project context.
        """
        if hasattr(scope_service, "_kano_skill"):
            requirement_text = user_requirements
            if user_feedback:
                requirement_text = (
                    f"{user_requirements}\n\nUser feedback for regeneration:\n{user_feedback}"
                )
            
            feature_tree = scope_service._adapter.build_kano_feature_tree(leaf_feature_nodes)
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None,
                scope_service._kano_skill.analyze,
                requirement_text,
                feature_tree,
            )
            
            scopes = scope_service._adapter.to_current_scopes(
                kano_result=raw,
                leaf_features=leaf_feature_nodes,
            )
            
            if temp_feat_to_int:
                for sc in scopes:
                    fid = sc.get("feature_id")
                    if isinstance(fid, str) and fid in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[fid]
                    elif isinstance(fid, str) and f"tmp_feature_{fid}" in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[f"tmp_feature_{fid}"]
            
            normalized_scopes = scope_service._normalize_generated_scopes(
                raw={"scopes": scopes},
                leaf_feature_nodes=leaf_feature_nodes,
            )
            return normalized_scopes
        else:
            from backend.core.generators.scopes_generator import ScopesGeneratorInput
            raw = await scope_service._scopes_generator.generate(
                ScopesGeneratorInput(
                    user_requirements=user_requirements,
                    features=feature_nodes,
                    user_feedback=user_feedback,
                )
            )
            
            if temp_feat_to_int and "scopes" in raw:
                for sc in raw["scopes"]:
                    fid = sc.get("feature_id")
                    if isinstance(fid, str) and fid in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[fid]
                    elif isinstance(fid, str) and f"tmp_feature_{fid}" in temp_feat_to_int:
                        sc["feature_id"] = temp_feat_to_int[f"tmp_feature_{fid}"]
            
            normalized_scopes = scope_service._normalize_generated_scopes(
                raw=raw,
                leaf_feature_nodes=leaf_feature_nodes,
            )
            return normalized_scopes

    async def _update_progress(self, draft_id: str, progress: int, message: str) -> None:
        try:
            async with AsyncSessionLocal() as session:
                draft_res = await session.execute(
                    select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                )
                draft = draft_res.scalar_one_or_none()
                if draft and draft.status == "generating":
                    import json
                    progress_info = {
                        "progress": progress,
                        "message": message
                    }
                    draft.error_message = json.dumps(progress_info, ensure_ascii=False)
                    await session.commit()
        except Exception:
            pass

    async def converge_shadow_snapshot_task(
        self,
        project_id: int,
        draft_id: str,
        api_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
    ) -> None:
        """
        Background AsyncIO task worker with isolated database session context.
        """
        token_ctx = None
        token_web = None
        if api_url and api_key and model_name:
            ctx = LLMRequestContext(api_url=api_url, api_key=api_key, model_name=model_name)
            token_ctx = current_llm_context.set(ctx)
            token_web = is_web_request_ctx.set(True)

        try:
            await asyncio.sleep(0.5)  # Let parent request return safely
            
            # 1. Fetch Draft and baseline info in a short session
            try:
                async with AsyncSessionLocal() as session:
                    draft_res = await session.execute(
                        select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                    )
                    draft = draft_res.scalar_one_or_none()
                    if not draft:
                        return

                    # Resolve public_id for client-facing payloads
                    project_obj = await session.get(ProjectModel, project_id)
                    project_public_id = project_obj.public_id if project_obj else str(project_id)

                    base_snapshot = draft.base_snapshot_json
                    feedback = ""
                    if draft.error_message and draft.error_message.startswith("Regenerating draft with feedback: "):
                        feedback = draft.error_message[len("Regenerating draft with feedback: "):].strip()
            except Exception as e:
                # If draft fetching fails, we can't do anything
                return

            # 2. Run convergence AI helper to build patch OUTSIDE of any database transaction!
            try:
                await self._update_progress(draft_id, 5, "正在初始化影子收敛，加载项目 baseline 数据...")
                patch = await self._generate_shadow_patch(
                    project_id=project_id,
                    base_snapshot=base_snapshot,
                    feedback=feedback,
                    draft_id=draft_id,
                )

                await self._update_progress(draft_id, 85, "AI 影子模型推演完成！正在进行沙盒装配与拓扑校验...")
                # 3. Validate patch
                ShadowPatchValidator.validate_patch(patch, base_snapshot, project_public_id)

                # 4. Construct virtual shadow snapshot (with negative IDs to appease Pydantic type validator)
                shadow_snapshot, temp_id_to_neg_int = self._apply_patch_to_snapshot(base_snapshot, patch)

                # 5. Parse shadow_snapshot as ProjectDetailResponse
                remapped_snapshot = _remap_snapshot_to_pydantic(shadow_snapshot)
                shadow_detail = ProjectDetailResponse.model_validate(remapped_snapshot)

                # 6. Generate simulated UI prototype pages using PrototypeGenerationService
                await self._update_progress(draft_id, 90, "影子沙盒装配完成！正在进行模拟高保真 UI 页面组装与原型界面渲染...")
                generator_input = prototype_generation_service._build_generator_input(
                    detail=shadow_detail,
                    gherkin_specs=[]
                )
                targets = prototype_generation_service._build_role_feature_targets(
                    generator_input=generator_input,
                    detail=shadow_detail
                )

                # Dispatch to the skill-backed generator if available, else fallback
                if hasattr(prototype_generation_service, '_generate_skill_pages_concurrently'):
                    pages = await prototype_generation_service._generate_skill_pages_concurrently(targets)
                else:
                    pages = await prototype_generation_service._generate_pages_concurrently(targets)
                first_page = pages[0] if pages else prototype_generation_service._empty_page(project_id)

                # Build mock PrototypePreviewResponse payload
                prototype_preview = {
                    "prototypeId": 0,
                    "projectId": project_public_id,
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

                # Write results back in a short, atomic write transaction
                async with AsyncSessionLocal() as session:
                    draft_res = await session.execute(
                        select(PreviewShadowDraftModel).where(PreviewShadowDraftModel.draft_id == draft_id)
                    )
                    draft = draft_res.scalar_one_or_none()
                    if draft:
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

                try:
                    async with AsyncSessionLocal() as session:
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
        finally:
            if token_ctx is not None:
                current_llm_context.reset(token_ctx)
            if token_web is not None:
                is_web_request_ctx.reset(token_web)
    async def _generate_shadow_patch(
        self,
        project_id: int,
        base_snapshot: dict,
        session: AsyncSession = None,
        feedback: str = "",
        draft_id: str = "",
    ) -> dict:
        """
        Consolidated shadow patch generator. Examines project requirements and baseline
        data, then dynamically and incrementally generates actors, features, flows, and scopes
        using the real AI generators if those stages are not converged. Already converged
        stages are preserved exactly as-is without invoking their corresponding generators.
        """
        from backend.api.services.service_registry import (
            flow_generation_service,
            scope_generation_service,
            feature_generation_service,
        )
        from backend.schemas import ActorNode, FeatureNode, ScenarioNode, AcceptanceCriterionNode
        from backend.core.generators.flows_generator import FlowsGeneratorInput

        import contextlib
        @contextlib.asynccontextmanager
        async def get_session_ctx():
            if session is not None:
                yield session
            else:
                async with AsyncSessionLocal() as s:
                    yield s

        # 1. Evaluate stage gates inside a short session
        async with get_session_ctx() as active_session:
            gates = await self.gate_evaluator.evaluate_gates(project_id, active_session)
        what_passed = gates["what"]
        how_passed = gates["how"]
        scope_passed = gates["scope"]

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
        temp_feat_to_int = {}

        # 2. What stage
        if not what_passed:
            user_requirements = base_snapshot.get("user_requirements", "")
            
            # Generate Actors
            await self._update_progress(draft_id, 15, "AI 正在智能推演补充 What 阶段设计资产：生成参与者角色...")
            from backend.core.generators.actors_generator import ActorsGenerator, ActorsGeneratorInput
            actors_generator = ActorsGenerator()
            raw_actors = await actors_generator.generate(
                ActorsGeneratorInput(
                    user_requirements=user_requirements,
                    user_feedback=feedback
                )
            )
            actors = raw_actors.get("actors", [])
            actor_nodes = []
            # int_to_temp_actor maps any LLM actor ID form → canonical tmp_actor_N
            int_to_temp_actor = {}
            for idx, a in enumerate(actors):
                name = a.get("actor_name") or a.get("name")
                desc = a.get("actor_description") or a.get("description")
                temp_id = f"tmp_actor_{idx + 1}"
                # Record LLM-assigned id variations in the lookup table
                raw_llm_id = a.get("actor_id") or a.get("id")
                if raw_llm_id is not None:
                    int_to_temp_actor[raw_llm_id] = temp_id
                    int_to_temp_actor[str(raw_llm_id)] = temp_id
                # Also map sequential index (actorId = idx+1) → temp_id
                int_to_temp_actor[idx + 1] = temp_id
                int_to_temp_actor[str(idx + 1)] = temp_id
                # Map temp_id itself
                int_to_temp_actor[temp_id] = temp_id
                patch["actors_added"].append({
                    "temp_id": temp_id,
                    "name": name,
                    "description": desc
                })
                actor_nodes.append(
                    ActorNode(
                        actorId=idx + 1,
                        actorName=name,
                        actorDescription=desc
                    )
                )

            def resolve_new_actor_ref(act_id) -> str:
                """Map any LLM-returned actor id to a canonical tmp_actor_N reference."""
                if not act_id and act_id != 0:
                    return ""
                act_id_str = str(act_id).strip()
                # Direct lookup first
                if act_id_str in int_to_temp_actor:
                    return int_to_temp_actor[act_id_str]
                if act_id in int_to_temp_actor:
                    return int_to_temp_actor[act_id]
                # Try extracting trailing digits (e.g. "A001" → 1, "actor_3" → 3)
                import re as _re
                _m = _re.search(r'(\d+)$', act_id_str)
                if _m:
                    trailing_int = int(_m.group(1))
                    if trailing_int in int_to_temp_actor:
                        return int_to_temp_actor[trailing_int]
                    if str(trailing_int) in int_to_temp_actor:
                        return int_to_temp_actor[str(trailing_int)]
                # Fallback: first actor
                return f"tmp_actor_1" if actor_nodes else ""

            # Generate Features tree (Skill-Backed or Legacy)
            await self._update_progress(draft_id, 25, "AI 正在智能推演补充 What 阶段设计资产：生成系统功能特征树...")
            if hasattr(feature_generation_service, "_skill_generator"):
                requirement_text = user_requirements
                if feedback:
                    requirement_text = f"{user_requirements}\n\nUser feedback for regeneration:\n{feedback}"
                actor_names = [actor.actorName for actor in actor_nodes]
                prompt = feature_generation_service._skill_generator._build_prompt(requirement_text, actor_names)
                raw_feature_tree = await feature_generation_service._llm_json_client.ask_json(prompt)
                features = feature_generation_service._adapter.to_current_features(
                    raw_feature_tree=raw_feature_tree,
                    actors=actor_nodes,
                )
            else:
                from backend.core.generators.features_generator import FeaturesGenerator, FeaturesGeneratorInput
                features_generator = FeaturesGenerator()
                raw_features = await features_generator.generate(
                    FeaturesGeneratorInput(
                        user_requirements=user_requirements,
                        actors=actor_nodes,
                        user_feedback=feedback
                    )
                )
                features = raw_features.get("features", [])

            feature_nodes = []
            for f_idx, f in enumerate(features):
                fnum = f.get("feature_number") or f.get("id") or f"gen_{f_idx + 1}"
                temp_feat_id = f"tmp_feature_{fnum}"
                name = f.get("feature_name") or f.get("name")
                desc = f.get("feature_description") or f.get("description")
                
                # Resolve parent_ref if it exists in features representation or by hierarchical number
                parent_val = f.get("parent_id") or f.get("parent_ref")
                parent_ref = None
                parent_id_node = None
                if parent_val:
                    parent_ref = f"tmp_feature_{parent_val}" if not str(parent_val).startswith("tmp_") else parent_val
                    try:
                        parent_id_node = int(parent_val)
                    except (ValueError, TypeError):
                        import hashlib
                        parent_id_node = int(hashlib.md5(str(parent_val).encode()).hexdigest(), 16) % 100000
                elif isinstance(fnum, str) and "-" in fnum:
                    parent_num = fnum.rsplit("-", 1)[0]
                    parent_ref = f"tmp_feature_{parent_num}"
                    try:
                        parent_id_node = int(parent_num)
                    except (ValueError, TypeError):
                        import hashlib
                        parent_id_node = int(hashlib.md5(str(parent_num).encode()).hexdigest(), 16) % 100000

                patch["features_added"].append({
                    "temp_id": temp_feat_id,
                    "name": name,
                    "description": desc,
                    "parent_ref": parent_ref
                })
                
                # Links to actors — use the lookup table built from the actor generation pass
                raw_actor_ids = f.get("actor_ids", [])
                # If LLM didn't assign actor_ids, link only the FIRST actor.
                # (Linking ALL actors would create N actor-feature pairs, each requiring a scenario.)
                if not raw_actor_ids and actor_nodes:
                    raw_actor_ids = [actor_nodes[0].actorId]
                f_actor_ids = []
                for act_id in raw_actor_ids:
                    act_ref = resolve_new_actor_ref(act_id)
                    if act_ref:
                        patch["feature_actor_links_added"].append({
                            "feature_ref": temp_feat_id,
                            "actor_ref": act_ref
                        })
                    # Build numeric actorId for FeatureNode (idx+1 corresponds to actor_nodes index)
                    act_ref_str = act_ref or f"tmp_actor_1"
                    # Extract trailing digit from canonical tmp_actor_N
                    try:
                        parsed_actor_id = int(act_ref_str.rsplit("_", 1)[-1])
                    except (ValueError, IndexError):
                        parsed_actor_id = 1
                    f_actor_ids.append(parsed_actor_id)
                
                try:
                    feat_id_int = int(fnum)
                except (ValueError, TypeError):
                    import hashlib
                    feat_id_int = int(hashlib.md5(str(fnum).encode()).hexdigest(), 16) % 100000
                
                temp_feat_to_int[temp_feat_id] = feat_id_int
                
                feature_nodes.append(
                    FeatureNode(
                        featureId=feat_id_int,
                        featureName=name,
                        featureDescription=desc,
                        actorIds=f_actor_ids,
                        parentId=parent_id_node,
                        childrenIds=f.get("children_ids", [])
                    )
                )

            # Build featureId → temp_id lookup for safe scenario feat_ref resolution
            feat_id_to_temp_id: dict[int, str] = {
                f_node.featureId: f_data["temp_id"]
                for f_data, f_node in zip(patch["features_added"], feature_nodes)
            }

            # Build childrenIds relationships on feature_nodes locally
            feat_node_map = {node.featureId: node for node in feature_nodes}
            for node in feature_nodes:
                if node.parentId is not None and node.parentId in feat_node_map:
                    parent_node = feat_node_map[node.parentId]
                    if node.featureId not in parent_node.childrenIds:
                        parent_node.childrenIds.append(node.featureId)

            # Generate Scenarios and ACs for ALL leaf features to pass What stage gate.
            await self._update_progress(draft_id, 35, "AI 正在智能推演补充 What 阶段设计资产：生成典型故事场景及 AC...")
            # Rule: one scenario per (leaf_feature × actor) pair to satisfy FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO detector.
            from backend.core.generators.scenarios_generator import ScenariosGenerator, ScenariosGeneratorInput
            from backend.core.generators.acceptance_criteria_generator import AcceptanceCriteriaGenerator, AcceptanceCriteriaGeneratorInput
            scenarios_generator = ScenariosGenerator()
            ac_generator = AcceptanceCriteriaGenerator()

            actor_map_by_id = {node.actorId: node for node in actor_nodes}
            leaf_nodes = [node for node in feature_nodes if not node.childrenIds]
            primary_leaf = leaf_nodes[0] if leaf_nodes else (feature_nodes[0] if feature_nodes else None)

            sc_counter = 1
            llm_scenarios_generated = False  # Only call LLM once (for the primary leaf+actor pair)

            for leaf_node in leaf_nodes:
                # Determine which actors are linked to this leaf feature
                linked_actor_ids = leaf_node.actorIds if leaf_node.actorIds else [actor_nodes[0].actorId if actor_nodes else 1]

                # Use the pre-built map for safe temp_id lookup (avoids index() fallback bugs)
                feat_ref = feat_id_to_temp_id.get(leaf_node.featureId, "tmp_feature_1")

                for actor_id in linked_actor_ids:
                    bound_actor = actor_map_by_id.get(actor_id) or actor_nodes[0]

                    try:
                        act_idx = actor_nodes.index(bound_actor)
                        act_ref = patch["actors_added"][act_idx]["temp_id"]
                    except Exception:
                        act_ref = "tmp_actor_1"

                    # Use LLM for the very first (primary leaf, primary actor) pair
                    if leaf_node == primary_leaf and not llm_scenarios_generated and actor_id == linked_actor_ids[0]:
                        llm_scenarios_generated = True
                        raw_scenarios = await scenarios_generator.generate(
                            ScenariosGeneratorInput(
                                user_requirements=user_requirements,
                                actor=bound_actor,
                                feature=leaf_node,
                                user_feedback=feedback
                            )
                        )
                        scenarios = raw_scenarios.get("scenarios", [])
                        scenario_nodes = []
                        for idx, s in enumerate(scenarios):
                            temp_sc_id = f"tmp_scenario_{sc_counter}"
                            sc_counter += 1
                            s_name = s.get("scenario_name") or s.get("name") or "主干业务流转"
                            s_content = s.get("scenario_content") or s.get("content") or (
                                f"As a {bound_actor.actorName}, I want to {leaf_node.featureDescription}, So that 我可以实现对应的业务价值"
                            )
                            patch["scenarios_added"].append({
                                "temp_id": temp_sc_id,
                                "name": s_name,
                                "content": s_content,
                                "feature_ref": feat_ref,
                                "actor_ref": act_ref
                            })
                            scenario_nodes.append(
                                ScenarioNode(
                                    scenarioId=sc_counter - 1,
                                    scenarioName=s_name,
                                    scenarioContent=s_content,
                                    featureId=leaf_node.featureId,
                                    actorId=bound_actor.actorId,
                                    acceptanceCriteria=[]
                                )
                            )
                        # LLM AC Generation for the generated scenarios
                        if scenario_nodes:
                            raw_ac = await ac_generator.generate(
                                AcceptanceCriteriaGeneratorInput(
                                    user_requirements=user_requirements,
                                    actor=bound_actor,
                                    feature=leaf_node,
                                    scenarios=scenario_nodes,
                                    user_feedback=feedback
                                )
                            )
                            ac_items = raw_ac.get("scenario_acceptance_criteria", raw_ac.get("acceptance_criteria", []))
                            for idx, item in enumerate(ac_items):
                                if isinstance(item, dict) and "acceptance_criteria" in item:
                                    sc_id_val = item.get("scenario_id") or 1
                                    target_sc_ref = f"tmp_scenario_{sc_id_val}"
                                    for nested_idx, nested_c in enumerate(item["acceptance_criteria"]):
                                        nested_content = nested_c.get("criterion_content") or nested_c.get("content") if isinstance(nested_c, dict) else nested_c
                                        patch["acceptance_criteria_added"].append({
                                            "scenario_ref": target_sc_ref,
                                            "content": nested_content,
                                            "position": nested_idx + 1
                                        })
                                else:
                                    content = item.get("criterion_content") or item.get("content") if isinstance(item, dict) else item
                                    pos = item.get("position") or (idx + 1) if isinstance(item, dict) else (idx + 1)
                                    patch["acceptance_criteria_added"].append({
                                        "scenario_ref": "tmp_scenario_1",
                                        "content": content,
                                        "position": pos
                                    })
                    else:
                        # Template-based scenario for all other (leaf_feature, actor) pairs
                        temp_sc_id = f"tmp_scenario_{sc_counter}"
                        sc_counter += 1
                        s_name = f"验证{leaf_node.featureName}在{bound_actor.actorName}视角下的主干业务场景"
                        s_content = (
                            f"As a {bound_actor.actorName}, I want to {leaf_node.featureDescription}, "
                            f"So that 我可以获得预期的系统产出和服务。"
                        )
                        patch["scenarios_added"].append({
                            "temp_id": temp_sc_id,
                            "name": s_name,
                            "content": s_content,
                            "feature_ref": feat_ref,
                            "actor_ref": act_ref
                        })
                        patch["acceptance_criteria_added"].append({
                            "scenario_ref": temp_sc_id,
                            "content": (
                                f"Given {bound_actor.actorName} 准备使用 {leaf_node.featureName} 功能, "
                                f"When {bound_actor.actorName} 触发相关交互操作, "
                                f"Then 系统应当正确处理并呈现 {leaf_node.featureName} 的相关界面与数据元。"
                            ),
                            "position": 1
                        })

            # Since What was NOT passed, How and Scope must be generated dynamically using our transaction-free patterns
            if not how_passed:
                await self._update_progress(draft_id, 50, "AI 正在增量推演 How 阶段业务规约：分析核心业务流及数据实体...")
                from backend.core.generators.flows_generator import FlowsGenerator, FlowsGeneratorInput
                flows_generator = FlowsGenerator()
                raw_flows = await flows_generator.generate(
                    FlowsGeneratorInput(
                        user_requirements=user_requirements,
                        actors=actor_nodes,
                        features=feature_nodes,
                        user_feedback=feedback
                    )
                )
                
                # Business Objects
                for bo_idx, bo in enumerate(raw_flows.get("business_objects", [])):
                    bo_num = f"gen_{bo_idx + 1}"
                    bo_temp_id = f"tmp_bo_{bo_num}"
                    patch["business_objects_added"].append({
                        "temp_id": bo_temp_id,
                        "name": bo.get("business_object_name") or bo.get("name"),
                        "description": bo.get("business_object_description") or bo.get("description")
                    })
                    
                    attrs = bo.get("business_object_attributes", [])
                    # Safety check: if AI returns empty attributes, insert default attributes to avoid How gate blockage
                    if not attrs:
                        attrs = [
                            {"name": "id", "description": "唯一标识", "data_type": "integer", "example": "1"},
                            {"name": "name", "description": "名称", "data_type": "string", "example": "示例名称"}
                        ]
                    for attr in attrs:
                        if not isinstance(attr, dict):
                            continue
                        patch["business_object_attributes_added"].append({
                            "business_object_ref": bo_temp_id,
                            "name": attr.get("business_object_attribute_name") or attr.get("name") or "未命名属性",
                            "description": attr.get("business_object_attribute_description") or attr.get("description") or "",
                            "data_type": attr.get("business_object_attribute_type") or attr.get("data_type") or "string",
                            "example": attr.get("business_object_attribute_example") or attr.get("example") or ""
                        })

                # Flows
                int_to_temp_feat = {}
                if temp_feat_to_int:
                    for k, v in temp_feat_to_int.items():
                        int_to_temp_feat[v] = k
                        int_to_temp_feat[str(v)] = k
                        int_to_temp_feat[k] = k
                
                # int_to_temp_actor was already built (with LLM raw IDs) during actor generation above
                # No rebuild needed here — reuse it directly.

                int_to_temp_bo = {}
                for bi, bo in enumerate(raw_flows.get("business_objects", [])):
                    bo_id_val = bo.get("business_object_number") or bo.get("id") or f"gen_{bi + 1}"
                    bo_temp_id = f"tmp_bo_gen_{bi + 1}"
                    int_to_temp_bo[bo_id_val] = bo_temp_id
                    int_to_temp_bo[str(bo_id_val)] = bo_temp_id
                    int_to_temp_bo[bo_temp_id] = bo_temp_id

                all_bo_ids = [bo.get("business_object_number") or bo.get("id") or f"gen_{bi + 1}" for bi, bo in enumerate(raw_flows.get("business_objects", []))]
                def resolve_feature_ref(feat_id: Any) -> str:
                    if not feat_id:
                        return ""
                    feat_id_str = str(feat_id).strip()
                    if feat_id_str.startswith("tmp_feature_"):
                        return feat_id_str
                    raw_id = feat_id
                    if feat_id_str.startswith("feature:"):
                        parts = feat_id_str.split(":", 1)
                        if len(parts) == 2:
                            val = parts[1]
                            try:
                                raw_id = int(val)
                            except ValueError:
                                raw_id = val
                    else:
                        try:
                            raw_id = int(feat_id)
                        except (ValueError, TypeError):
                            raw_id = feat_id
                    if raw_id in int_to_temp_feat:
                        return int_to_temp_feat[raw_id]
                    if str(raw_id) in int_to_temp_feat:
                        return int_to_temp_feat[str(raw_id)]
                    if isinstance(raw_id, int):
                        return f"feature:{raw_id}"
                    if feat_id_str.startswith("feature:"):
                        return feat_id_str
                    return f"tmp_feature_{feat_id}"

                def resolve_actor_ref(act_id: Any) -> str:
                    if not act_id:
                        return ""
                    act_id_str = str(act_id).strip()
                    if act_id_str.startswith("tmp_actor_"):
                        return act_id_str
                    raw_id = act_id
                    if act_id_str.startswith("actor:"):
                        parts = act_id_str.split(":", 1)
                        if len(parts) == 2:
                            val = parts[1]
                            try:
                                raw_id = int(val)
                            except ValueError:
                                raw_id = val
                    else:
                        try:
                            raw_id = int(act_id)
                        except (ValueError, TypeError):
                            raw_id = act_id
                    if raw_id in int_to_temp_actor:
                        return int_to_temp_actor[raw_id]
                    if str(raw_id) in int_to_temp_actor:
                        return int_to_temp_actor[str(raw_id)]
                    if isinstance(raw_id, int):
                        return f"actor:{raw_id}"
                    if act_id_str.startswith("actor:"):
                        return act_id_str
                    return f"tmp_actor_{act_id}"

                def resolve_bo_ref(bo_num: Any) -> str:
                    if not bo_num:
                        return ""
                    bo_num_str = str(bo_num).strip()
                    if bo_num_str.startswith("tmp_bo_"):
                        return bo_num_str
                    raw_id = bo_num
                    if bo_num_str.startswith("business_object:"):
                        parts = bo_num_str.split(":", 1)
                        if len(parts) == 2:
                            val = parts[1]
                            try:
                                raw_id = int(val)
                            except ValueError:
                                raw_id = val
                    else:
                        try:
                            raw_id = int(bo_num)
                        except (ValueError, TypeError):
                            raw_id = bo_num
                    if raw_id in int_to_temp_bo:
                        return int_to_temp_bo[raw_id]
                    if str(raw_id) in int_to_temp_bo:
                        return int_to_temp_bo[str(raw_id)]
                    if isinstance(raw_id, int):
                        return f"business_object:{raw_id}"
                    if bo_num_str.startswith("business_object:"):
                        return bo_num_str
                    if bo_num in all_bo_ids:
                        mapped_idx = all_bo_ids.index(bo_num)
                        return f"tmp_bo_gen_{mapped_idx + 1}"
                    return f"tmp_bo_{bo_num}"

                for flow_idx, fl in enumerate(raw_flows.get("flows", [])):
                    flow_num = f"gen_{flow_idx + 1}"
                    flow_temp_id = f"tmp_flow_{flow_num}"
                    
                    feature_refs = [resolve_feature_ref(feat_id) for feat_id in fl.get("feature_ids", [])]
                            
                    patch["flows_added"].append({
                        "temp_id": flow_temp_id,
                        "name": fl.get("flow_name") or fl.get("name"),
                        "description": fl.get("flow_description") or fl.get("description"),
                        "feature_refs": feature_refs
                    })
                    
                    for s_idx, st in enumerate(fl.get("flow_steps", [])):
                        step_num = f"gen_{s_idx + 1}"
                        step_temp_id = f"tmp_step_{flow_num}_{step_num}"
                        
                        actor_refs = [resolve_actor_ref(act_id) for act_id in st.get("actor_ids", [])]
                                
                        input_bo_refs = [resolve_bo_ref(bo_num) for bo_num in st.get("input_business_object_numbers", [])]
                                
                        output_bo_refs = [resolve_bo_ref(bo_num) for bo_num in st.get("output_business_object_numbers", [])]
                                
                        next_step_refs = []
                        all_step_nums_in_flow = [s2.get("step_number") or s2.get("id") or f"gen_{s2i + 1}" for s2i, s2 in enumerate(fl.get("flow_steps", []))]
                        for next_num in st.get("next_steps", []):
                            if next_num in all_step_nums_in_flow:
                                mapped_idx = all_step_nums_in_flow.index(next_num)
                                next_step_refs.append(f"tmp_step_{flow_num}_gen_{mapped_idx + 1}")
                            else:
                                next_step_refs.append(f"tmp_step_{flow_num}_{next_num}")
                            
                        patch["flow_steps_added"].append({
                            "temp_id": step_temp_id,
                            "flow_ref": flow_temp_id,
                            "name": st.get("step_name") or st.get("name"),
                            "description": st.get("step_description") or st.get("description"),
                            "step_type": st.get("step_type") or st.get("type"),
                            "position": st.get("position") or (s_idx + 1),
                            "actor_refs": actor_refs,
                            "input_bo_refs": input_bo_refs,
                            "output_bo_refs": output_bo_refs,
                            "next_step_refs": next_step_refs
                        })

            # CALL THE REAL KANO DECISION GENERATOR OR KANO SKILL!
            if not scope_passed:
                await self._update_progress(draft_id, 75, "AI 正在评估交付范围：生成 Kano 价值评估与剪裁建议...")
                leaf_feature_nodes = [node for node in feature_nodes if not node.childrenIds]
                scopes = await self._generate_scopes_for_features(
                    scope_service=scope_generation_service,
                    user_requirements=user_requirements,
                    feature_nodes=feature_nodes,
                    leaf_feature_nodes=leaf_feature_nodes,
                    user_feedback=feedback,
                    temp_feat_to_int=temp_feat_to_int
                )
                int_to_temp_feat = {}
                if temp_feat_to_int:
                    for k, v in temp_feat_to_int.items():
                        int_to_temp_feat[v] = k
                        int_to_temp_feat[str(v)] = k
                        int_to_temp_feat[k] = k
                
                def resolve_feature_ref(feat_id: Any) -> str:
                    if not feat_id:
                        return ""
                    feat_id_str = str(feat_id).strip()
                    if feat_id_str.startswith("tmp_feature_"):
                        return feat_id_str
                    raw_id = feat_id
                    if feat_id_str.startswith("feature:"):
                        parts = feat_id_str.split(":", 1)
                        if len(parts) == 2:
                            val = parts[1]
                            try:
                                raw_id = int(val)
                            except ValueError:
                                raw_id = val
                    else:
                        try:
                            raw_id = int(feat_id)
                        except (ValueError, TypeError):
                            raw_id = feat_id
                    if raw_id in int_to_temp_feat:
                        return int_to_temp_feat[raw_id]
                    if str(raw_id) in int_to_temp_feat:
                        return int_to_temp_feat[str(raw_id)]
                    if isinstance(raw_id, int):
                        return f"feature:{raw_id}"
                    if feat_id_str.startswith("feature:"):
                        return feat_id_str
                    return f"tmp_feature_{feat_id}"

                for sc in scopes:
                    feat_id = sc.get("feature_id")
                    feat_ref = resolve_feature_ref(feat_id)
                    patch["scopes_added"].append({
                        "feature_ref": feat_ref,
                        "status": (sc.get("scope_status") or sc.get("status") or "CURRENT").upper(),
                        "reason": sc.get("reason") or "AI影子收敛补充",
                        "kano_category": sc.get("kano_category") or "M",
                        "kano_category_name": sc.get("kano_category_name") or "Must-be",
                        "positive_summary": sc.get("positive_summary") or "已支持",
                        "negative_summary": sc.get("negative_summary") or "不满足",
                        "positive_picture_base64": sc.get("positive_picture_base64"),
                        "negative_picture_base64": sc.get("negative_picture_base64")
                    })

        # 3. What is already converged: use service registry wrappers outside session transactions
        else:
            await self._update_progress(draft_id, 25, "AI 正在检测并补充 What 阶段缺失的典型故事场景与验收标准（AC）...")
            # Enforce scenario/AC completeness check for pre-existing features/actors.
            # Even if 'what' stage passed in the backend (warnings allowed),
            # the frontend requires every leaf feature and associated actor to have scenarios and ACs.
            features = base_snapshot.get("features", [])
            actors = base_snapshot.get("actors", [])
            
            # Find leaf features in base_snapshot (a feature is a leaf if it has no children)
            parent_ids = {f.get("parent_id") for f in features if f.get("parent_id") is not None}
            leaf_features = [f for f in features if f.get("id") not in parent_ids]
            
            sc_counter = 1
            for lf in leaf_features:
                lf_id = lf.get("id")
                lf_name = lf.get("name", "未命名功能")
                lf_desc = lf.get("description", "")
                lf_actor_ids = lf.get("actor_ids", [])
                
                # Fallback: if no actors are associated, map to first available actor
                if not lf_actor_ids and actors:
                    lf_actor_ids = [actors[0].get("id")]
                
                scenarios_in_feat = lf.get("scenarios", [])
                
                for act_id in lf_actor_ids:
                    actor_obj = next((a for a in actors if a.get("id") == act_id), None)
                    act_name = actor_obj.get("name") if actor_obj else f"角色{act_id}"
                    
                    exist_scs = [s for s in scenarios_in_feat if s.get("actor_id") == act_id]
                    
                    if not exist_scs:
                        # Missing scenario! Generate a template-based scenario
                        temp_sc_id = f"tmp_scenario_{sc_counter}"
                        sc_counter += 1
                        s_name = f"验证{lf_name}在{act_name}视角下的主干业务场景"
                        s_content = (
                            f"As a {act_name}, I want to {lf_desc or lf_name}, "
                            f"So that 我可以获得预期的系统产出和服务。"
                        )
                        patch["scenarios_added"].append({
                            "temp_id": temp_sc_id,
                            "name": s_name,
                            "content": s_content,
                            "feature_ref": f"feature:{lf_id}",
                            "actor_ref": f"actor:{act_id}"
                        })
                        patch["acceptance_criteria_added"].append({
                            "scenario_ref": temp_sc_id,
                            "content": (
                                f"Given {act_name} 准备使用 {lf_name} 功能, "
                                f"When {act_name} 触发相关交互操作, "
                                f"Then 系统应当正确处理并呈现 {lf_name} 的相关界面与数据元。"
                            ),
                            "position": 1
                        })
                    else:
                        # Scenario exists, but check if any of them are missing ACs
                        for esc in exist_scs:
                            esc_id = esc.get("id") or esc.get("scenario_id")
                            if not esc.get("acceptance_criteria"):
                                patch["acceptance_criteria_added"].append({
                                    "scenario_ref": f"scenario:{esc_id}",
                                    "content": (
                                        f"Given {act_name} 准备使用 {lf_name} 功能, "
                                        f"When {act_name} 触发相关交互操作, "
                                        f"Then 系统应当正确处理并呈现 {lf_name} 的相关界面与数据元。"
                                    ),
                                    "position": 1
                                })

            if not how_passed:
                await self._update_progress(draft_id, 50, "AI 正在增量推演 How 阶段业务规约：分析核心业务流及数据实体...")
                # Load context in short session, run generator outside of session
                async with get_session_ctx() as ctx_session:
                    (
                        user_requirements,
                        actor_nodes,
                        feature_nodes,
                        leaf_feature_count,
                    ) = await flow_generation_service._load_project_context(
                        project_id=project_id,
                        session=ctx_session,
                    )
                
                raw_flows = await flow_generation_service._flows_generator.generate(
                    FlowsGeneratorInput(
                        user_requirements=user_requirements,
                        actors=actor_nodes,
                        features=feature_nodes,
                        user_feedback=feedback
                    ),
                    use_old_prompt=(leaf_feature_count < flow_generation_service._three_step_leaf_feature_threshold)
                )
                
                # Business Objects
                for bo_idx, bo in enumerate(raw_flows.get("business_objects", [])):
                    bo_num = f"gen_{bo_idx + 1}"
                    bo_temp_id = f"tmp_bo_{bo_num}"
                    patch["business_objects_added"].append({
                        "temp_id": bo_temp_id,
                        "name": bo.get("business_object_name") or bo.get("name"),
                        "description": bo.get("business_object_description") or bo.get("description")
                    })
                    
                    attrs = bo.get("business_object_attributes", [])
                    if not attrs:
                        attrs = [
                            {"name": "id", "description": "唯一标识", "data_type": "integer", "example": "1"},
                            {"name": "name", "description": "名称", "data_type": "string", "example": "示例名称"}
                        ]
                    for attr in attrs:
                        if not isinstance(attr, dict):
                            continue
                        patch["business_object_attributes_added"].append({
                            "business_object_ref": bo_temp_id,
                            "name": attr.get("business_object_attribute_name") or attr.get("name") or "未命名属性",
                            "description": attr.get("business_object_attribute_description") or attr.get("description") or "",
                            "data_type": attr.get("business_object_attribute_type") or attr.get("data_type") or "string",
                            "example": attr.get("business_object_attribute_example") or attr.get("example") or ""
                        })

                # Flows
                all_bo_ids = [bo.get("business_object_number") or bo.get("id") or f"gen_{bi + 1}" for bi, bo in enumerate(raw_flows.get("business_objects", []))]
                for flow_idx, fl in enumerate(raw_flows.get("flows", [])):
                    flow_num = f"gen_{flow_idx + 1}"
                    flow_temp_id = f"tmp_flow_{flow_num}"
                    
                    feature_refs = []
                    for feat_id in fl.get("feature_ids", []):
                        if isinstance(feat_id, int):
                            feature_refs.append(f"feature:{feat_id}")
                        elif str(feat_id).startswith("tmp_") or str(feat_id).startswith("feature:"):
                            feature_refs.append(str(feat_id))
                        else:
                            feature_refs.append(f"tmp_feature_{feat_id}")
                            
                    patch["flows_added"].append({
                        "temp_id": flow_temp_id,
                        "name": fl.get("flow_name") or fl.get("name"),
                        "description": fl.get("flow_description") or fl.get("description"),
                        "feature_refs": feature_refs
                    })
                    
                    for s_idx, st in enumerate(fl.get("flow_steps", [])):
                        step_num = f"gen_{s_idx + 1}"
                        step_temp_id = f"tmp_step_{flow_num}_{step_num}"
                        
                        actor_refs = []
                        for act_id in st.get("actor_ids", []):
                            if str(act_id).startswith("actor:"):
                                actor_refs.append(str(act_id))
                            elif isinstance(act_id, int):
                                # Real DB actor IDs (what_passed means actors exist in DB)
                                actor_refs.append(f"actor:{act_id}")
                            else:
                                # Numeric string → treat as real DB actor ID
                                try:
                                    actor_refs.append(f"actor:{int(act_id)}")
                                except (ValueError, TypeError):
                                    # Non-numeric (e.g. "admin") — skip; validator will catch invalid refs
                                    pass
                                
                        input_bo_refs = []
                        for bo_num in st.get("input_business_object_numbers", []):
                            if isinstance(bo_num, int):
                                input_bo_refs.append(f"business_object:{bo_num}")
                            elif str(bo_num).startswith("tmp_") or str(bo_num).startswith("business_object:"):
                                input_bo_refs.append(str(bo_num))
                            elif bo_num in all_bo_ids:
                                mapped_idx = all_bo_ids.index(bo_num)
                                input_bo_refs.append(f"tmp_bo_gen_{mapped_idx + 1}")
                            else:
                                input_bo_refs.append(f"tmp_bo_{bo_num}")
                                
                        output_bo_refs = []
                        for bo_num in st.get("output_business_object_numbers", []):
                            if isinstance(bo_num, int):
                                output_bo_refs.append(f"business_object:{bo_num}")
                            elif str(bo_num).startswith("tmp_") or str(bo_num).startswith("business_object:"):
                                output_bo_refs.append(str(bo_num))
                            elif bo_num in all_bo_ids:
                                mapped_idx = all_bo_ids.index(bo_num)
                                output_bo_refs.append(f"tmp_bo_gen_{mapped_idx + 1}")
                            else:
                                output_bo_refs.append(f"tmp_bo_{bo_num}")
                                
                        next_step_refs = []
                        all_step_nums_in_flow = [s2.get("step_number") or s2.get("id") or f"gen_{s2i + 1}" for s2i, s2 in enumerate(fl.get("flow_steps", []))]
                        for next_num in st.get("next_steps", []):
                            if next_num in all_step_nums_in_flow:
                                mapped_idx = all_step_nums_in_flow.index(next_num)
                                next_step_refs.append(f"tmp_step_{flow_num}_gen_{mapped_idx + 1}")
                            else:
                                next_step_refs.append(f"tmp_step_{flow_num}_{next_num}")
                            
                        patch["flow_steps_added"].append({
                            "temp_id": step_temp_id,
                            "flow_ref": flow_temp_id,
                            "name": st.get("step_name") or st.get("name"),
                            "description": st.get("step_description") or st.get("description"),
                            "step_type": st.get("step_type") or st.get("type"),
                            "position": st.get("position") or (s_idx + 1),
                            "actor_refs": actor_refs,
                            "input_bo_refs": input_bo_refs,
                            "output_bo_refs": output_bo_refs,
                            "next_step_refs": next_step_refs
                        })

            if not scope_passed:
                await self._update_progress(draft_id, 75, "AI 正在评估交付范围：生成 Kano 价值评估与剪裁建议...")
                # Load context in short session, run generator outside of session
                async with get_session_ctx() as ctx_session:
                    (
                        user_requirements,
                        feature_nodes,
                        leaf_feature_nodes,
                    ) = await scope_generation_service._load_project_context(
                        project_id=project_id,
                        session=ctx_session,
                    )
                
                scopes = await self._generate_scopes_for_features(
                    scope_service=scope_generation_service,
                    user_requirements=user_requirements,
                    feature_nodes=feature_nodes,
                    leaf_feature_nodes=leaf_feature_nodes,
                    user_feedback=feedback
                )
                for sc in scopes:
                    feat_id = sc.get("feature_id")
                    feat_ref = f"feature:{feat_id}" if isinstance(feat_id, int) else (f"tmp_feature_{feat_id}" if not str(feat_id).startswith("tmp_") else feat_id)
                    patch["scopes_added"].append({
                        "feature_ref": feat_ref,
                        "status": (sc.get("scope_status") or sc.get("status") or "CURRENT").upper(),
                        "reason": sc.get("reason") or "AI影子收敛补充",
                        "kano_category": sc.get("kano_category") or "M",
                        "kano_category_name": sc.get("kano_category_name") or "Must-be",
                        "positive_summary": sc.get("positive_summary") or "已支持",
                        "negative_summary": sc.get("negative_summary") or "不满足",
                        "positive_picture_base64": sc.get("positive_picture_base64"),
                        "negative_picture_base64": sc.get("negative_picture_base64")
                    })
        return patch

    def _apply_patch_to_snapshot(self, base_snapshot: dict, patch: dict) -> tuple[dict, dict[str, int]]:
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
                    "positive_picture_base64": sc.get("positive_picture_base64"),
                    "negative_picture_base64": sc.get("negative_picture_base64"),
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
                    "positive_picture_base64": None,
                    "negative_picture_base64": None,
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
        ShadowPatchValidator.validate_patch(patch, current_snapshot, current_snapshot["project_id"])

        # 4. Map temporary string IDs to new database IDs
        actor_id_map: dict[str, int] = {}
        feature_id_map: dict[str, int] = {}
        scenario_id_map: dict[str, int] = {}
        bo_id_map: dict[str, int] = {}
        flow_id_map: dict[str, int] = {}
        step_id_map: dict[str, int] = {}

        # Helpers to resolve a ref string (e.g. "actor:12" or "tmp_actor_1") to integer ID
        def resolve_actor_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return actor_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_feature_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return feature_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_scenario_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return scenario_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_bo_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return bo_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_flow_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return flow_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

        def resolve_step_id(ref: Any) -> int:
            if not ref:
                return 0
            ref_str = str(ref)
            if ref_str.startswith("tmp_"):
                return step_id_map[ref_str]
            if ":" in ref_str:
                return int(ref_str.split(":")[1])
            return int(ref_str)

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
                else:
                    parent_ref_str = str(parent_ref)
                    if parent_ref_str.startswith("feature:"):
                        can_insert = True
                        parent_id = int(parent_ref_str.split(":")[1])
                    elif parent_ref_str.startswith("tmp_"):
                        if parent_ref_str in feature_id_map:
                            can_insert = True
                            parent_id = feature_id_map[parent_ref_str]
                    else:
                        try:
                            parent_id = int(parent_ref_str)
                            can_insert = True
                        except ValueError:
                            pass
                
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
                            select(func.max(FeatureRelationModel.position)).where(
                                FeatureRelationModel.parent_feature_id == parent_id
                            )
                        )
                        max_pos = pos_res.scalar()
                        next_pos = 0 if max_pos is None else max_pos + 1
                        
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
            
            from backend.services.binary_conversion_service import BinaryConversionService
            pos_pic = BinaryConversionService.base64_to_bytes(sc.get("positive_picture_base64")) if sc.get("positive_picture_base64") else None
            neg_pic = BinaryConversionService.base64_to_bytes(sc.get("negative_picture_base64")) if sc.get("negative_picture_base64") else None

            if existing_scope:
                existing_scope.status = sc["status"]
                existing_scope.reason = sc["reason"]
                existing_scope.kano_category = sc.get("kano_category")
                existing_scope.kano_category_name = sc.get("kano_category_name")
                existing_scope.positive_summary = sc.get("positive_summary")
                existing_scope.negative_summary = sc.get("negative_summary")
                if pos_pic is not None:
                    existing_scope.positive_picture = pos_pic
                if neg_pic is not None:
                    existing_scope.negative_picture = neg_pic
            else:
                new_scope = ScopeModel(
                    feature_id=feat_id,
                    status=sc["status"],
                    reason=sc["reason"],
                    kano_category=sc.get("kano_category"),
                    kano_category_name=sc.get("kano_category_name"),
                    positive_summary=sc.get("positive_summary"),
                    negative_summary=sc.get("negative_summary"),
                    positive_picture=pos_pic,
                    negative_picture=neg_pic
                )
                session.add(new_scope)
                await session.flush()

        # Sweep all leaf features and ensure they have a real Scope generated if missing
        feature_res = await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )
        feature_models = feature_res.scalars().all()
        feature_ids = [f.id for f in feature_models]
        
        if feature_ids:
            relation_res = await session.execute(
                select(FeatureRelationModel).where(
                    FeatureRelationModel.parent_feature_id.in_(feature_ids)
                )
            )
            relation_models = relation_res.scalars().all()
            parent_with_children = {r.parent_feature_id for r in relation_models}
            leaf_features = [f for f in feature_models if f.id not in parent_with_children]
            
            scope_res = await session.execute(
                select(ScopeModel).where(ScopeModel.feature_id.in_(feature_ids))
            )
            existing_scopes = scope_res.scalars().all()
            existing_scope_feature_ids = {s.feature_id for s in existing_scopes}
            
            missing_leaf_ids = [f.id for f in leaf_features if f.id not in existing_scope_feature_ids]
            if missing_leaf_ids:
                from backend.api.services.service_registry import scope_generation_service
                draft_payload, _ = await scope_generation_service._generate_preview(
                    project_id=project_id,
                    user_feedback=None,
                    session=session
                )
                generated_scopes = draft_payload.get("scopes", [])
                for sc in generated_scopes:
                    feat_id = sc.get("feature_id")
                    if feat_id in missing_leaf_ids:
                        from backend.services.binary_conversion_service import BinaryConversionService
                        pos_pic = BinaryConversionService.base64_to_bytes(sc.get("positive_picture_base64")) if sc.get("positive_picture_base64") else None
                        neg_pic = BinaryConversionService.base64_to_bytes(sc.get("negative_picture_base64")) if sc.get("negative_picture_base64") else None
                        new_scope = ScopeModel(
                            feature_id=feat_id,
                            status=sc.get("scope_status", "current").upper(),
                            reason=sc.get("reason", "AI影子收敛补充"),
                            kano_category=sc.get("kano_category"),
                            kano_category_name=sc.get("kano_category_name"),
                            positive_summary=sc.get("positive_summary"),
                            negative_summary=sc.get("negative_summary"),
                            positive_picture=pos_pic,
                            negative_picture=neg_pic
                        )
                        session.add(new_scope)
                        missing_leaf_ids.remove(feat_id)
                
                # Double fallback check
                for f_id in missing_leaf_ids:
                    new_scope = ScopeModel(
                        feature_id=f_id,
                        status="CURRENT",
                        reason="AI影子收敛补充",
                        kano_category="M",
                        kano_category_name="Must-be"
                    )
                    session.add(new_scope)
                await session.flush()

        # Update Project Kano Status to generated (completed) and unlock all stages
        project = await session.get(ProjectModel, project_id)
        if project:
            if project.kano_status not in ("generated", "skipped"):
                project.kano_status = "generated"
            project.unlocked_stages = "what,how,scope"


        # Step L: Clear slot and issue cache by soft deleting/staling perception jobs and slots
        from backend.database.model import PerceptionJobModel, PerceptionSlotModel
        await session.execute(
            delete(PerceptionJobModel).where(
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage.in_(["what", "how", "scope"])
            )
        )
        await session.execute(
            delete(PerceptionSlotModel).where(
                PerceptionSlotModel.project_id == project_id
            )
        )


        # Step M: Finalize Draft setting committed
        draft.status = "committed"
        draft.committed_at = beijing_now()
        await session.flush()

        # Step N: Copy and map shadow draft prototype preview to the real project prototype preview table
        prototype_preview_dict = draft.prototype_preview_json
        if prototype_preview_dict:
            from backend.database.model import PrototypePreviewModel
            temp_id_to_neg_int: dict[str, int] = {}
            neg_counter = -1001
            for a in patch.get("actors_added", []):
                temp_id_to_neg_int[a["temp_id"]] = neg_counter
                neg_counter -= 1
            for f in patch.get("features_added", []):
                temp_id_to_neg_int[f["temp_id"]] = neg_counter
                neg_counter -= 1

            neg_to_pos_actor_id = {}
            neg_to_pos_feature_id = {}
            for temp_id, neg_id in temp_id_to_neg_int.items():
                if temp_id in actor_id_map:
                    neg_to_pos_actor_id[neg_id] = actor_id_map[temp_id]
                if temp_id in feature_id_map:
                    neg_to_pos_feature_id[neg_id] = feature_id_map[temp_id]

            mapped_pages = []
            for page in prototype_preview_dict.get("pages", []):
                r_id = page.get("roleId") or page.get("role_id")
                f_id = page.get("featureId") or page.get("feature_id")
                
                mapped_role_id = neg_to_pos_actor_id.get(r_id, r_id) if isinstance(r_id, int) and r_id < 0 else r_id
                mapped_feature_id = neg_to_pos_feature_id.get(f_id, f_id) if isinstance(f_id, int) and f_id < 0 else f_id
                
                mapped_pages.append({
                    "page_id": f"role-{mapped_role_id}-feature-{mapped_feature_id}",
                    "role_id": mapped_role_id,
                    "role_name": page.get("roleName") or page.get("role_name"),
                    "feature_id": mapped_feature_id,
                    "feature_name": page.get("featureName") or page.get("feature_name"),
                    "html": page.get("html"),
                    "javascript": page.get("javascript"),
                    "css": page.get("css"),
                    "source": "committed_shadow_project",
                    "status": "ready"
                })

            first_page = mapped_pages[0] if mapped_pages else {
                "html": prototype_preview_dict.get("html", ""),
                "javascript": prototype_preview_dict.get("javascript", ""),
                "css": prototype_preview_dict.get("css", "")
            }

            detail = await prototype_generation_service._project_service.get_project_detail(
                project_id=project_id,
                session=session
            )

            new_preview = PrototypePreviewModel(
                project_id=project_id,
                status="ready",
                source="committed_shadow_project",
                html=first_page["html"],
                javascript=first_page["javascript"],
                css=first_page["css"],
                pages=mapped_pages,
                input_snapshot=detail.model_dump(mode="json", by_alias=True)
            )
            session.add(new_preview)
            await session.flush()

        import sys
        if "pytest" in sys.modules:
            await prototype_generation_service.generate_preview(
                project_id=project_id,
                session=session,
                force_regenerate=True
            )
        else:
            await session.commit()

    async def generate_post_commit_prototype(self, project_id: int) -> None:
        """
        Runs prototype generation asynchronously in a fresh session context.
        """
        import logging
        logger = logging.getLogger(__name__)
        try:
            async with AsyncSessionLocal() as session:
                await prototype_generation_service.generate_preview(
                    project_id=project_id,
                    session=session,
                    force_regenerate=True
                )
                await session.commit()
        except Exception as e:
            import traceback
            from backend.core.security import sanitize_message
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            sanitized_tb = sanitize_message(tb_str)
            logger.error(
                f"Post-commit prototype generation failed for project {project_id} ({type(e).__name__}):\n{sanitized_tb}"
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
