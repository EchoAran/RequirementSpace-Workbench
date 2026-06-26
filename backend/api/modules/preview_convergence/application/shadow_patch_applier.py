import copy


class PreviewShadowPatchApplier:
    @staticmethod
    def apply_patch_to_snapshot(base_snapshot: dict, patch: dict) -> tuple[dict, dict[str, int]]:
        """
        Merges patch_json into base_snapshot, translating all transient 'tmp_' string references
        to negative integers to satisfy Pydantic Model validators without violating database schema.
        """
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
