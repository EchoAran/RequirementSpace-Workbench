from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.generators.flows_generator import FlowsGeneratorInput
from backend.database.database import AsyncSessionLocal
from backend.schemas import ActorNode, FeatureNode

from .shadow_patch.common import (
    _append_generated_business_objects,
    _append_generated_scopes,
    _build_generated_reference_map,
    _create_empty_patch,
    _resolve_generated_reference,
    _resolve_preserved_scope_feature_ref,
)
from .shadow_patch.flow_mapper import (
    _append_generated_flows,
    _append_preserved_flows,
)
from .shadow_patch.what_generator import (
    _append_feature_nodes,
    _generate_actor_nodes,
    _generate_features,
    _generate_scenario_patch,
)

def _fill_preserved_what_gaps(patch: dict, base_snapshot: dict) -> None:
    features = base_snapshot.get("features", [])
    actors = base_snapshot.get("actors", [])
    actors_by_id = {}
    for actor in actors:
        actors_by_id.setdefault(actor.get("id"), actor)

    parent_ids = {
        feature.get("parent_id")
        for feature in features
        if feature.get("parent_id") is not None
    }
    leaf_features = [
        feature for feature in features if feature.get("id") not in parent_ids
    ]

    scenario_counter = 1
    for leaf_feature in leaf_features:
        feature_id = leaf_feature.get("id")
        feature_name = leaf_feature.get("name", "未命名功能")
        feature_description = leaf_feature.get("description", "")
        actor_ids = leaf_feature.get("actor_ids", [])

        if not actor_ids and actors:
            patch["feature_actor_links_added"].append({
                "feature_ref": f"feature:{feature_id}",
                "actor_ref": f"actor:{actors[0].get('id')}",
            })
            actor_ids = [actors[0].get("id")]

        feature_scenarios = leaf_feature.get("scenarios", [])
        scenarios_by_actor_id = {}
        for scenario in feature_scenarios:
            scenarios_by_actor_id.setdefault(
                scenario.get("actor_id"),
                [],
            ).append(scenario)

        for actor_id in actor_ids:
            actor = actors_by_id.get(actor_id)
            actor_name = actor.get("name") if actor else f"角色{actor_id}"
            actor_scenarios = scenarios_by_actor_id.get(actor_id, [])

            acceptance_content = (
                f"Given {actor_name} 准备使用 {feature_name} 功能, "
                f"When {actor_name} 触发相关交互操作, "
                f"Then 系统应当正确处理并呈现 {feature_name} 的相关界面与数据元。"
            )
            if not actor_scenarios:
                temporary_scenario_id = f"tmp_scenario_{scenario_counter}"
                scenario_counter += 1
                patch["scenarios_added"].append({
                    "temp_id": temporary_scenario_id,
                    "name": f"验证{feature_name}在{actor_name}视角下的主干业务场景",
                    "content": (
                        f"As a {actor_name}, I want to "
                        f"{feature_description or feature_name}, "
                        f"So that 我可以获得预期的系统产出和服务。"
                    ),
                    "feature_ref": f"feature:{feature_id}",
                    "actor_ref": f"actor:{actor_id}",
                })
                patch["acceptance_criteria_added"].append({
                    "scenario_ref": temporary_scenario_id,
                    "content": acceptance_content,
                    "position": 1,
                })
                continue

            for scenario in actor_scenarios:
                scenario_id = scenario.get("id") or scenario.get("scenario_id")
                if not scenario.get("acceptance_criteria"):
                    patch["acceptance_criteria_added"].append({
                        "scenario_ref": f"scenario:{scenario_id}",
                        "content": acceptance_content,
                        "position": 1,
                    })

async def _generate_preserved_how_patch(
    patch: dict,
    flow_generation_service,
    project_id: int,
    feedback: str,
    session: AsyncSession,
) -> None:
    raw_flows, *_ = await flow_generation_service.generate_raw(
        project_id=project_id,
        user_feedback=feedback,
        session=session,
        validate_result=False,
    )
    _append_generated_business_objects(patch, raw_flows)
    _append_preserved_flows(patch, raw_flows)

async def _generate_preserved_scope_patch(
    patch: dict,
    service,
    scope_generation_service,
    project_id: int,
    feedback: str,
    session: AsyncSession,
) -> None:
    (
        user_requirements,
        feature_nodes,
        leaf_feature_nodes,
    ) = await scope_generation_service._load_project_context(
        project_id=project_id,
        session=session,
    )
    scopes = await service._generate_scopes_for_features(
        scope_service=scope_generation_service,
        user_requirements=user_requirements,
        feature_nodes=feature_nodes,
        leaf_feature_nodes=leaf_feature_nodes,
        user_feedback=feedback,
    )
    _append_generated_scopes(
        patch,
        scopes,
        _resolve_preserved_scope_feature_ref,
    )

async def _generate_new_how_patch(
    patch: dict,
    user_requirements: str,
    feedback: str,
    actor_nodes: list[ActorNode],
    feature_nodes: list[FeatureNode],
    temporary_feature_id_to_int: dict[str, int],
    actor_ref_by_id: dict,
) -> None:
    from backend.core.generators.flows_generator import FlowsGenerator

    raw_flows = await FlowsGenerator().generate(
        FlowsGeneratorInput(
            user_requirements=user_requirements,
            actors=actor_nodes,
            features=feature_nodes,
            user_feedback=feedback,
        )
    )
    _append_generated_business_objects(patch, raw_flows)
    feature_ref_by_id = _build_generated_reference_map(
        temporary_feature_id_to_int
    )
    temporary_business_object_id_to_raw_id = {
        f"tmp_bo_gen_{business_object_index + 1}": (
            business_object.get("business_object_number")
            or business_object.get("id")
            or f"gen_{business_object_index + 1}"
        )
        for business_object_index, business_object in enumerate(
            raw_flows.get("business_objects", [])
        )
    }
    business_object_ref_by_id = _build_generated_reference_map(
        temporary_business_object_id_to_raw_id
    )
    _append_generated_flows(
        patch,
        raw_flows,
        feature_ref_by_id,
        actor_ref_by_id,
        business_object_ref_by_id,
    )

async def _generate_new_scope_patch(
    patch: dict,
    service,
    scope_generation_service,
    user_requirements: str,
    feedback: str,
    feature_nodes: list[FeatureNode],
    temporary_feature_id_to_int: dict[str, int],
) -> None:
    leaf_feature_nodes = [
        feature for feature in feature_nodes if not feature.childrenIds
    ]
    scopes = await service._generate_scopes_for_features(
        scope_service=scope_generation_service,
        user_requirements=user_requirements,
        feature_nodes=feature_nodes,
        leaf_feature_nodes=leaf_feature_nodes,
        user_feedback=feedback,
        temp_feat_to_int=temporary_feature_id_to_int,
    )
    feature_ref_by_id = _build_generated_reference_map(
        temporary_feature_id_to_int
    )

    def resolve_feature_ref(feature_id: Any) -> str:
        return _resolve_generated_reference(
            feature_id,
            feature_ref_by_id,
            "feature",
            "tmp_feature_",
        )

    _append_generated_scopes(
        patch,
        scopes,
        resolve_feature_ref,
    )

@asynccontextmanager
async def _use_session(session: AsyncSession | None):
    if session is not None:
        yield session
    else:
        async with AsyncSessionLocal() as created_session:
            yield created_session

def _has_preservable_what_assets(base_snapshot: dict) -> bool:
    features = base_snapshot.get("features", [])
    actors = base_snapshot.get("actors", [])
    parent_ids = {
        feature.get("parent_id")
        for feature in features
        if feature.get("parent_id") is not None
    }
    leaf_features = [
        feature for feature in features if feature.get("id") not in parent_ids
    ]
    return bool(actors) and bool(leaf_features)

async def _generate_missing_downstream_patch(
    patch: dict,
    service,
    scope_generation_service,
    user_requirements: str,
    feedback: str,
    draft_id: str,
    how_passed: bool,
    scope_passed: bool,
    actor_nodes: list[ActorNode],
    feature_nodes: list[FeatureNode],
    temporary_feature_id_to_int: dict[str, int],
    actor_ref_by_id: dict,
) -> None:
    if not how_passed:
        await service._update_progress(
            draft_id,
            50,
            "preview.full.progressHow",
        )
        await _generate_new_how_patch(
            patch,
            user_requirements,
            feedback,
            actor_nodes,
            feature_nodes,
            temporary_feature_id_to_int,
            actor_ref_by_id,
        )
    if not scope_passed:
        await service._update_progress(
            draft_id,
            75,
            "preview.full.progressScope",
        )
        await _generate_new_scope_patch(
            patch,
            service,
            scope_generation_service,
            user_requirements,
            feedback,
            feature_nodes,
            temporary_feature_id_to_int,
        )

async def _generate_missing_what_patch(
    patch: dict,
    service,
    feature_generation_service,
    scope_generation_service,
    base_snapshot: dict,
    feedback: str,
    draft_id: str,
    how_passed: bool,
    scope_passed: bool,
) -> None:
    user_requirements = base_snapshot.get("user_requirements", "")
    await service._update_progress(
        draft_id,
        15,
        "preview.full.progressWhat",
    )
    actor_nodes, actor_ref_by_id = await _generate_actor_nodes(
        patch,
        user_requirements,
        feedback,
    )
    await service._update_progress(
        draft_id,
        25,
        "preview.full.progressWhat",
    )
    features = await _generate_features(
        feature_generation_service,
        user_requirements,
        feedback,
        actor_nodes,
    )
    (
        feature_nodes,
        temporary_feature_id_to_int,
        feature_id_to_temporary_id,
    ) = _append_feature_nodes(
        patch,
        features,
        actor_nodes,
        actor_ref_by_id,
    )
    await service._update_progress(
        draft_id,
        35,
        "preview.full.progressWhat",
    )
    await _generate_scenario_patch(
        patch,
        user_requirements,
        feedback,
        actor_nodes,
        feature_nodes,
        feature_id_to_temporary_id,
    )
    await _generate_missing_downstream_patch(
        patch,
        service,
        scope_generation_service,
        user_requirements,
        feedback,
        draft_id,
        how_passed,
        scope_passed,
        actor_nodes,
        feature_nodes,
        temporary_feature_id_to_int,
        actor_ref_by_id,
    )

async def _generate_preserved_assets_patch(
    patch: dict,
    service,
    flow_generation_service,
    scope_generation_service,
    project_id: int,
    base_snapshot: dict,
    session: AsyncSession | None,
    feedback: str,
    draft_id: str,
    how_passed: bool,
    scope_passed: bool,
) -> None:
    await service._update_progress(
        draft_id,
        25,
        "preview.full.progressWhat",
    )
    _fill_preserved_what_gaps(patch, base_snapshot)
    if not how_passed:
        await service._update_progress(
            draft_id,
            50,
            "preview.full.progressHow",
        )
        async with _use_session(session) as active_session:
            await _generate_preserved_how_patch(
                patch,
                flow_generation_service,
                project_id,
                feedback,
                active_session,
            )
    if not scope_passed:
        await service._update_progress(
            draft_id,
            75,
            "preview.full.progressScope",
        )
        async with _use_session(session) as active_session:
            await _generate_preserved_scope_patch(
                patch,
                service,
                scope_generation_service,
                project_id,
                feedback,
                active_session,
            )

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

        async with _use_session(session) as active_session:
            gates = await service.gate_evaluator.evaluate_gates(project_id, active_session)
        what_passed = gates["what"]
        how_passed = gates["how"]
        scope_passed = gates["scope"]
        patch = _create_empty_patch()
        if not what_passed and not _has_preservable_what_assets(base_snapshot):
            await _generate_missing_what_patch(
                patch,
                service,
                feature_generation_service,
                scope_generation_service,
                base_snapshot,
                feedback,
                draft_id,
                how_passed,
                scope_passed,
            )
            return patch

        await _generate_preserved_assets_patch(
            patch,
            service,
            flow_generation_service,
            scope_generation_service,
            project_id,
            base_snapshot,
            session,
            feedback,
            draft_id,
            how_passed,
            scope_passed,
        )
        return patch
