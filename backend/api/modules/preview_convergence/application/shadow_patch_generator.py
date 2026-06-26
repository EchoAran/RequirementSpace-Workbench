import asyncio
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.database import AsyncSessionLocal
from backend.schemas import ActorNode, FeatureNode, ScenarioNode
from backend.core.generators.flows_generator import FlowsGeneratorInput


class PreviewShadowPatchGenerator:
    @staticmethod
    async def generate_shadow_patch(
        service,
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
        from backend.api.modules.requirements_core.ports import (
            get_flow_generation_service,
            get_scope_generation_service,
            get_feature_generation_service,
        )
        flow_generation_service = get_flow_generation_service()
        scope_generation_service = get_scope_generation_service()
        feature_generation_service = get_feature_generation_service()

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
            gates = await service.gate_evaluator.evaluate_gates(project_id, active_session)
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
            await service._update_progress(draft_id, 15, "AI 正在智能推演补充 What 阶段设计资产：生成参与者角色...")
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
            await service._update_progress(draft_id, 25, "AI 正在智能推演补充 What 阶段设计资产：生成系统功能特征树...")
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
                
                # Links to actors
                raw_actor_ids = f.get("actor_ids", [])
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
                    act_ref_str = act_ref or f"tmp_actor_1"
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

            feat_id_to_temp_id: dict[int, str] = {
                f_node.featureId: f_data["temp_id"]
                for f_data, f_node in zip(patch["features_added"], feature_nodes)
            }

            feat_node_map = {node.featureId: node for node in feature_nodes}
            for node in feature_nodes:
                if node.parentId is not None and node.parentId in feat_node_map:
                    parent_node = feat_node_map[node.parentId]
                    if node.featureId not in parent_node.childrenIds:
                        parent_node.childrenIds.append(node.featureId)

            # Generate Scenarios and ACs for ALL leaf features
            await service._update_progress(draft_id, 35, "AI 正在智能推演补充 What 阶段设计资产：生成典型故事场景及 AC...")
            from backend.core.generators.scenarios_generator import ScenariosGenerator, ScenariosGeneratorInput
            from backend.core.generators.acceptance_criteria_generator import AcceptanceCriteriaGenerator, AcceptanceCriteriaGeneratorInput
            scenarios_generator = ScenariosGenerator()
            ac_generator = AcceptanceCriteriaGenerator()

            actor_map_by_id = {node.actorId: node for node in actor_nodes}
            leaf_nodes = [node for node in feature_nodes if not node.childrenIds]
            primary_leaf = leaf_nodes[0] if leaf_nodes else (feature_nodes[0] if feature_nodes else None)

            sc_counter = 1
            llm_scenarios_generated = False

            for leaf_node in leaf_nodes:
                linked_actor_ids = leaf_node.actorIds if leaf_node.actorIds else [actor_nodes[0].actorId if actor_nodes else 1]
                feat_ref = feat_id_to_temp_id.get(leaf_node.featureId, "tmp_feature_1")

                for actor_id in linked_actor_ids:
                    bound_actor = actor_map_by_id.get(actor_id) or actor_nodes[0]

                    try:
                        act_idx = actor_nodes.index(bound_actor)
                        act_ref = patch["actors_added"][act_idx]["temp_id"]
                    except Exception:
                        act_ref = "tmp_actor_1"

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

            if not how_passed:
                await service._update_progress(draft_id, 50, "AI 正在增量推演 How 阶段业务规约：分析核心业务流及数据实体...")
                from backend.core.generators.flows_generator import FlowsGenerator
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
                await service._update_progress(draft_id, 75, "AI 正在评估交付范围：生成 Kano 价值评估与剪裁建议...")
                leaf_feature_nodes = [node for node in feature_nodes if not node.childrenIds]
                scopes = await service._generate_scopes_for_features(
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
            await service._update_progress(draft_id, 25, "AI 正在检测并补充 What 阶段缺失的典型故事场景与验收标准（AC）...")
            features = base_snapshot.get("features", [])
            actors = base_snapshot.get("actors", [])
            
            parent_ids = {f.get("parent_id") for f in features if f.get("parent_id") is not None}
            leaf_features = [f for f in features if f.get("id") not in parent_ids]
            
            sc_counter = 1
            for lf in leaf_features:
                lf_id = lf.get("id")
                lf_name = lf.get("name", "未命名功能")
                lf_desc = lf.get("description", "")
                lf_actor_ids = lf.get("actor_ids", [])
                
                if not lf_actor_ids and actors:
                    lf_actor_ids = [actors[0].get("id")]
                
                scenarios_in_feat = lf.get("scenarios", [])
                
                for act_id in lf_actor_ids:
                    actor_obj = next((a for a in actors if a.get("id") == act_id), None)
                    act_name = actor_obj.get("name") if actor_obj else f"角色{act_id}"
                    
                    exist_scs = [s for s in scenarios_in_feat if s.get("actor_id") == act_id]
                    
                    if not exist_scs:
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
                await service._update_progress(draft_id, 50, "AI 正在增量推演 How 阶段业务规约：分析核心业务流及数据实体...")
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
                                actor_refs.append(f"actor:{act_id}")
                            else:
                                try:
                                    actor_refs.append(f"actor:{int(act_id)}")
                                except (ValueError, TypeError):
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
                await service._update_progress(draft_id, 75, "AI 正在评估交付范围：生成 Kano 价值评估与剪裁建议...")
                async with get_session_ctx() as ctx_session:
                    (
                        user_requirements,
                        feature_nodes,
                        leaf_feature_nodes,
                    ) = await scope_generation_service._load_project_context(
                        project_id=project_id,
                        session=ctx_session,
                    )
                
                scopes = await service._generate_scopes_for_features(
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
