def what_stage_checks(
    actors_count,
    leaf_features,
    feature_actor_map,
    feature_scenario_map,
    scenario_ids,
    ac_scenario_ids,
    scenarios_map,
):
    checks = []
    if actors_count == 0:
        checks.append({
            "code": "missing_actors",
            "message": "stageProgress.checks.missing_actors",
            "targets": [],
        })
    if not leaf_features:
        checks.append({
            "code": "missing_leaf_features",
            "message": "stageProgress.checks.missing_leaf_features",
            "targets": [],
        })
    leaf_without_actor = [
        feature
        for feature in leaf_features
        if not feature_actor_map.get(feature.id)
    ]
    if leaf_without_actor:
        checks.append({
            "code": "leaf_feature_without_actor",
            "message": "stageProgress.checks.leaf_feature_without_actor",
            "targets": [
                {
                    "type": "feature",
                    "id": str(feature.id),
                    "name": feature.name,
                }
                for feature in leaf_without_actor[:5]
            ],
        })
    leaf_without_scenario = [
        feature
        for feature in leaf_features
        if not feature_scenario_map.get(feature.id)
    ]
    if leaf_without_scenario:
        checks.append({
            "code": "leaf_feature_without_scenario",
            "message": "stageProgress.checks.leaf_feature_without_scenario",
            "targets": [
                {
                    "type": "feature",
                    "id": str(feature.id),
                    "name": feature.name,
                }
                for feature in leaf_without_scenario[:5]
            ],
        })
    scenarios_without_ac = [
        scenario_id
        for scenario_id in scenario_ids
        if scenario_id not in ac_scenario_ids
    ]
    if scenarios_without_ac:
        checks.append({
            "code": "missing_acceptance_criteria",
            "message": "stageProgress.checks.missing_acceptance_criteria",
            "targets": [
                {
                    "type": "scenario",
                    "id": str(scenario_id),
                    "name": scenarios_map[scenario_id].name,
                }
                for scenario_id in scenarios_without_ac[:5]
            ],
        })
    return checks


def business_object_definition_checks(business_objects):
    if not business_objects or any(
        business_object.attributes
        for business_object in business_objects
    ):
        return []
    return [{
        "code": "missing_object_attributes",
        "message": "stageProgress.checks.missing_object_attributes",
        "targets": [
            {
                "type": "business_object",
                "id": str(item.id),
                "name": item.name,
            }
            for item in business_objects[:5]
        ],
    }]


def _invalid_actor_step_checks(actors_rows, steps_db, step_actor_map):
    actor_ids = set(actors_rows)
    invalid_steps = [
        step
        for step in steps_db
        if any(
            actor_id not in actor_ids
            for actor_id in step_actor_map.get(step.id, [])
        )
    ]
    if not invalid_steps:
        return []
    return [{
        "code": "invalid_step_actor",
        "message": "stageProgress.checks.invalid_step_actor",
        "targets": [
            {
                "type": "step",
                "id": str(step.id),
                "name": step.name,
            }
            for step in invalid_steps[:5]
        ],
    }]


def _invalid_object_step_checks(
    steps_db,
    step_input_bo_map,
    step_output_bo_map,
    bo_set,
):
    invalid_steps = [
        step
        for step in steps_db
        if any(
            object_id not in bo_set
            for object_id in (
                step_input_bo_map.get(step.id, [])
                + step_output_bo_map.get(step.id, [])
            )
        )
    ]
    if not invalid_steps:
        return []
    return [{
        "code": "invalid_step_business_object",
        "message": "stageProgress.checks.invalid_step_business_object",
        "targets": [
            {
                "type": "step",
                "id": str(step.id),
                "name": step.name,
            }
            for step in invalid_steps[:5]
        ],
    }]


def how_stage_checks(
    flows,
    flows_with_steps,
    flows_map,
    actors_rows,
    steps_db,
    step_actor_map,
    step_input_bo_map,
    step_output_bo_map,
    bo_set,
    bos_db,
):
    if not flows:
        return [{
            "code": "missing_flows",
            "message": "stageProgress.checks.missing_flows",
            "targets": [],
        }]
    checks = []
    flows_without_steps = [
        flow_id
        for flow_id in flows
        if flow_id not in flows_with_steps
    ]
    if flows_without_steps:
        checks.append({
            "code": "flows_without_steps",
            "message": "stageProgress.checks.flows_without_steps",
            "targets": [
                {
                    "type": "flow",
                    "id": str(flow_id),
                    "name": flows_map[flow_id].name,
                }
                for flow_id in flows_without_steps[:5]
            ],
        })
    checks.extend(
        _invalid_actor_step_checks(
            actors_rows,
            steps_db,
            step_actor_map,
        )
    )
    checks.extend(
        _invalid_object_step_checks(
            steps_db,
            step_input_bo_map,
            step_output_bo_map,
            bo_set,
        )
    )
    checks.extend(business_object_definition_checks(bos_db))
    return checks


def scope_stage_checks(leaf_features, scoped_feature_ids, kano_status):
    checks = []
    leaf_not_scoped = [
        feature
        for feature in leaf_features
        if feature.id not in scoped_feature_ids
    ]
    if leaf_not_scoped:
        checks.append({
            "code": "missing_scope_decision",
            "message": "stageProgress.checks.missing_scope_decision",
            "targets": [
                {
                    "type": "feature",
                    "id": str(feature.id),
                    "name": feature.name,
                }
                for feature in leaf_not_scoped[:5]
            ],
        })
    if kano_status not in ("generated", "skipped"):
        checks.append({
            "code": "kano_not_ready",
            "message": "stageProgress.checks.kano_not_ready",
            "targets": [],
        })
    return checks


def stage_status(
    unlocked,
    next_stage_unlocked,
    blocked,
    content_complete,
    analysis_running,
    not_started,
):
    if next_stage_unlocked:
        return "ready"
    if not unlocked:
        return "locked"
    if analysis_running:
        return "analysis_running"
    if blocked:
        return "blocked"
    if content_complete:
        return "ready_to_advance"
    return "unlocked_not_started" if not_started else "in_progress"


def stage_next_action(stage, status_code, public_project_id):
    if status_code == "ready_to_advance":
        transition_actions = {
            "what": "enter_how",
            "how": "enter_scope",
            "scope": "enter_preview",
        }
        return {
            "kind": "stage_transition",
            "transition_action": transition_actions[stage],
            "route": None,
            "label": "stageProgress.actions.request_transition",
        }
    fixed_actions = {
        "blocked": (
            "open_gate_findings",
            "stageProgress.actions.open_gate_findings",
        ),
        "analysis_running": ("wait", "stageProgress.actions.wait"),
        "locked": ("none", ""),
    }
    if status_code in fixed_actions:
        kind, label = fixed_actions[status_code]
        return {
            "kind": kind,
            "transition_action": None,
            "route": None,
            "label": label,
        }
    routes = {
        "what": f"/projects/{public_project_id}/what",
        "how": f"/projects/{public_project_id}/flow",
        "scope": f"/projects/{public_project_id}/scope",
    }
    return {
        "kind": "navigate",
        "transition_action": None,
        "route": routes[stage],
        "label": "stageProgress.actions.navigate",
    }


def stage_analysis_status(latest_job, running):
    if latest_job is None:
        return {
            "status": "idle",
            "job_id": None,
            "started_at": None,
            "message": None,
        }
    started_at = (
        latest_job.created_at.isoformat()
        if latest_job.created_at
        else None
    )
    if running:
        return {
            "status": "running",
            "job_id": latest_job.id,
            "started_at": started_at,
            "message": "stageProgress.analysis.running",
        }
    if latest_job.status == "failed":
        return {
            "status": "failed",
            "job_id": latest_job.id,
            "started_at": started_at,
            "message": (
                latest_job.error_message
                or "stageProgress.analysis.failed"
            ),
        }
    return {
        "status": "idle",
        "job_id": None,
        "started_at": None,
        "message": None,
    }
