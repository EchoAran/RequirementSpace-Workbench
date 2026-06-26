import re
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.stage_gates.stage_gate_evaluator import StageGateEvaluator


class PreviewShadowValidator:
    def __init__(self) -> None:
        self.gate_evaluator = StageGateEvaluator()

    async def evaluate_gates(self, project_id: int, session: AsyncSession) -> dict:
        """
        Evaluate stage gates for the project.
        """
        return await self.gate_evaluator.evaluate_gates(project_id, session)

    def validate_patch(self, patch: dict, base_snapshot: dict, project_id: str) -> bool:
        """
        Validates the generated shadow patch against the base snapshot of the project.
        Enforces schema constraints, temp ID uniqueness, project membership,
        and sequential step ordering.
        Raises ValueError if any validation fails.
        """
        # Ensure project_id matches base_snapshot
        base_proj_id = base_snapshot.get("project_id")
        if base_proj_id is not None and str(base_proj_id) != str(project_id):
            raise ValueError(
                f"Project ID mismatch: base_snapshot is for project {base_proj_id}, "
                f"but active project is {project_id}."
            )

        # 1. Collect all real IDs in base snapshot for membership verification
        real_actors = {item["id"] for item in base_snapshot.get("actors", [])}
        real_features = {item["id"] for item in base_snapshot.get("features", [])}
        
        real_scenarios = set()
        for f in base_snapshot.get("features", []):
            for s in f.get("scenarios", []):
                real_scenarios.add(s["id"])
                
        real_flows = {item["id"] for item in base_snapshot.get("flows", [])}
        real_bos = {item["id"] for item in base_snapshot.get("business_objects", [])}
        
        real_steps = set()
        for fl in base_snapshot.get("flows", []):
            for step in fl.get("flow_steps", []):
                real_steps.add(step["id"])

        # Helper to parse references
        def verify_ref(ref: str, expected_type: str, allowed_temp_ids: set[str]) -> bool:
            if not ref:
                return False
            if ref.startswith("tmp_"):
                if ref not in allowed_temp_ids:
                    raise ValueError(f"Invalid temporary reference '{ref}': not defined in patch.")
                return True
            
            # Format: type:id, e.g., "feature:3"
            parts = ref.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid reference format '{ref}'. Must be type:id.")
            
            ref_type, ref_id_str = parts[0], parts[1]
            if ref_type != expected_type:
                raise ValueError(f"Reference type mismatch for '{ref}': expected '{expected_type}', got '{ref_type}'.")
            
            try:
                ref_id = int(ref_id_str)
            except ValueError:
                raise ValueError(f"Invalid non-integer ID in reference '{ref}'.")
            
            # Verify project membership (must exist in base snapshot)
            if ref_type == "actor" and ref_id not in real_actors:
                raise ValueError(f"Actor ID {ref_id} in reference '{ref}' does not exist or belong to project {project_id}.")
            if ref_type == "feature" and ref_id not in real_features:
                raise ValueError(f"Feature ID {ref_id} in reference '{ref}' does not exist or belong to project {project_id}.")
            if ref_type == "scenario" and ref_id not in real_scenarios:
                raise ValueError(f"Scenario ID {ref_id} in reference '{ref}' does not exist or belong to project {project_id}.")
            if ref_type == "flow" and ref_id not in real_flows:
                raise ValueError(f"Flow ID {ref_id} in reference '{ref}' does not exist or belong to project {project_id}.")
            if ref_type == "business_object" and ref_id not in real_bos:
                raise ValueError(f"Business Object ID {ref_id} in reference '{ref}' does not exist or belong to project {project_id}.")
            if ref_type == "flow_step" and ref_id not in real_steps:
                raise ValueError(f"Flow Step ID {ref_id} in reference '{ref}' does not exist or belong to project {project_id}.")
            
            return True

        # Extract added lists
        actors_added = patch.get("actors_added", [])
        features_added = patch.get("features_added", [])
        links_added = patch.get("feature_actor_links_added", [])
        scenarios_added = patch.get("scenarios_added", [])
        ac_added = patch.get("acceptance_criteria_added", [])
        bos_added = patch.get("business_objects_added", [])
        bo_attrs_added = patch.get("business_object_attributes_added", [])
        flows_added = patch.get("flows_added", [])
        steps_added = patch.get("flow_steps_added", [])
        scopes_added = patch.get("scopes_added", [])

        # 2. Gather and validate all temp_ids (temp_id must be unique across all arrays)
        temp_ids = set()
        
        # Temp ID sets by type for topological reference checks
        temp_actors = set()
        temp_features = set()
        temp_scenarios = set()
        temp_flows = set()
        temp_bos = set()
        temp_steps = set()

        def add_temp_id(tid: str, category_set: set[str], field_name: str) -> None:
            if not tid:
                raise ValueError(f"Empty temp_id in {field_name}.")
            if not tid.startswith("tmp_"):
                raise ValueError(f"Temporary ID '{tid}' in {field_name} must start with 'tmp_'.")
            if tid in temp_ids:
                raise ValueError(f"Duplicate temp_id '{tid}' across patch elements.")
            temp_ids.add(tid)
            category_set.add(tid)

        for a in actors_added:
            add_temp_id(a.get("temp_id"), temp_actors, "actors_added")
        for f in features_added:
            add_temp_id(f.get("temp_id"), temp_features, "features_added")
        for s in scenarios_added:
            add_temp_id(s.get("temp_id"), temp_scenarios, "scenarios_added")
        for b in bos_added:
            add_temp_id(b.get("temp_id"), temp_bos, "business_objects_added")
        for fl in flows_added:
            add_temp_id(fl.get("temp_id"), temp_flows, "flows_added")
        for st in steps_added:
            add_temp_id(st.get("temp_id"), temp_steps, "flow_steps_added")

        # 3. Validate Features added (parent_ref must be valid)
        for f in features_added:
            parent_ref = f.get("parent_ref")
            if parent_ref:
                verify_ref(parent_ref, "feature", temp_features)

        # 4. Validate Feature-Actor Links
        for link in links_added:
            verify_ref(link.get("feature_ref"), "feature", temp_features)
            verify_ref(link.get("actor_ref"), "actor", temp_actors)

        # 5. Validate Scenarios added
        for s in scenarios_added:
            verify_ref(s.get("feature_ref"), "feature", temp_features)
            verify_ref(s.get("actor_ref"), "actor", temp_actors)

        # 6. Validate AC added (scenario_ref must exist in base or patch)
        for ac in ac_added:
            verify_ref(ac.get("scenario_ref"), "scenario", temp_scenarios)
            if not ac.get("content", "").strip():
                raise ValueError("Acceptance Criterion content cannot be empty.")

        # 7. Validate Business Object Attributes
        for attr in bo_attrs_added:
            verify_ref(attr.get("business_object_ref"), "business_object", temp_bos)
            if not attr.get("name", "").strip():
                raise ValueError("Business Object Attribute name cannot be empty.")
            if not attr.get("data_type", "").strip():
                raise ValueError("Business Object Attribute data_type cannot be empty.")

        # 8. Validate Flows added
        for fl in flows_added:
            feature_refs = fl.get("feature_refs", [])
            if not feature_refs:
                raise ValueError(f"Flow '{fl.get('name')}' must reference at least one feature.")
            for fref in feature_refs:
                verify_ref(fref, "feature", temp_features)

        # 9. Validate Flow Steps added
        flow_steps_by_flow = {}
        for st in steps_added:
            flow_ref = st.get("flow_ref")
            verify_ref(flow_ref, "flow", temp_flows)
            
            flow_steps_by_flow.setdefault(flow_ref, []).append(st)
            
            # Verify referenced elements in step
            actor_refs = st.get("actor_refs", [])
            input_bo_refs = st.get("input_bo_refs", [])
            output_bo_refs = st.get("output_bo_refs", [])
            next_step_refs = st.get("next_step_refs", [])
            
            if st.get("step_type") == "actorAction" and not actor_refs:
                raise ValueError(f"Flow step '{st.get('name')}' of type 'actorAction' must reference at least one actor.")
            
            for aref in actor_refs:
                verify_ref(aref, "actor", temp_actors)
            for iref in input_bo_refs:
                verify_ref(iref, "business_object", temp_bos)
            for oref in output_bo_refs:
                verify_ref(oref, "business_object", temp_bos)
            for nref in next_step_refs:
                verify_ref(nref, "flow_step", temp_steps)

        # Enforce step sequence positions starting from 1
        for flow_ref, steps in flow_steps_by_flow.items():
            positions = []
            for st in steps:
                pos = st.get("position")
                if pos is None:
                    raise ValueError(f"Step '{st.get('name')}' is missing a position index.")
                positions.append(pos)
            
            sorted_positions = sorted(positions)
            if sorted_positions != list(range(1, len(steps) + 1)):
                raise ValueError(
                    f"Flow steps positions for flow '{flow_ref}' are not consecutive and sequential starting from 1. Got: {sorted_positions}"
                )

        # 10. Validate Scopes added
        for sc in scopes_added:
            verify_ref(sc.get("feature_ref"), "feature", temp_features)
            status = sc.get("status")
            if status not in {"CURRENT", "POSTPONED", "EXCLUDE"}:
                raise ValueError(
                    f"Invalid scope status '{status}' for feature reference '{sc.get('feature_ref')}'. "
                    f"Must be one of 'CURRENT', 'POSTPONED', 'EXCLUDE'."
                )
            if not sc.get("reason", "").strip():
                raise ValueError(f"Scope for feature '{sc.get('feature_ref')}' is missing a rationale reason.")

        return True
