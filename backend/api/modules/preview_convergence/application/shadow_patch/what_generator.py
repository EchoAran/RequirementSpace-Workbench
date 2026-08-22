
from backend.core.llm_protected_inputs import collect_protected_texts
from backend.schemas import ActorNode, FeatureNode, ScenarioNode


async def _generate_actor_nodes(
    patch: dict,
    user_requirements: str,
    feedback: str,
) -> tuple[list[ActorNode], dict]:
    from backend.core.generators.actors_generator import (
        ActorsGenerator,
        ActorsGeneratorInput,
    )

    raw_actors = await ActorsGenerator().generate(
        ActorsGeneratorInput(
            user_requirements=user_requirements,
            user_feedback=feedback,
        )
    )
    actor_nodes = []
    actor_ref_by_id = {}
    for actor_index, actor in enumerate(raw_actors.get("actors", [])):
        name = actor.get("actor_name") or actor.get("name")
        description = (
            actor.get("actor_description") or actor.get("description")
        )
        temporary_actor_id = f"tmp_actor_{actor_index + 1}"
        raw_actor_id = actor.get("actor_id") or actor.get("id")
        if raw_actor_id is not None:
            actor_ref_by_id[raw_actor_id] = temporary_actor_id
            actor_ref_by_id[str(raw_actor_id)] = temporary_actor_id
        actor_ref_by_id[actor_index + 1] = temporary_actor_id
        actor_ref_by_id[str(actor_index + 1)] = temporary_actor_id
        actor_ref_by_id[temporary_actor_id] = temporary_actor_id
        patch["actors_added"].append({
            "temp_id": temporary_actor_id,
            "name": name,
            "description": description,
        })
        actor_nodes.append(
            ActorNode(
                actorId=actor_index + 1,
                actorName=name,
                actorDescription=description,
            )
        )
    return actor_nodes, actor_ref_by_id

def _resolve_new_actor_ref(
    actor_id,
    actor_ref_by_id: dict,
    actor_nodes: list[ActorNode],
) -> str:
    if not actor_id and actor_id != 0:
        return ""
    actor_id_text = str(actor_id).strip()
    if actor_id_text in actor_ref_by_id:
        return actor_ref_by_id[actor_id_text]
    if actor_id in actor_ref_by_id:
        return actor_ref_by_id[actor_id]

    import re

    match = re.search(r"(\d+)$", actor_id_text)
    if match:
        trailing_id = int(match.group(1))
        if trailing_id in actor_ref_by_id:
            return actor_ref_by_id[trailing_id]
        if str(trailing_id) in actor_ref_by_id:
            return actor_ref_by_id[str(trailing_id)]
    return "tmp_actor_1" if actor_nodes else ""

async def _generate_features(
    feature_generation_service,
    user_requirements: str,
    feedback: str,
    actor_nodes: list[ActorNode],
) -> list[dict]:
    if hasattr(feature_generation_service, "_skill_generator"):
        requirement_text = user_requirements
        if feedback:
            requirement_text = (
                f"{user_requirements}\n\n"
                f"User feedback for regeneration:\n{feedback}"
            )
        actor_names = [actor.actorName for actor in actor_nodes]
        prompt = feature_generation_service._skill_generator._build_prompt(
            requirement_text,
            actor_names,
        )
        raw_feature_tree = (
            await feature_generation_service._llm_json_client.ask_json(
                prompt,
                protected_inputs=collect_protected_texts(
                    user_requirements,
                    feedback,
                    actor_names,
                ),
            )
        )
        return feature_generation_service._adapter.to_current_features(
            raw_feature_tree=raw_feature_tree,
            actors=actor_nodes,
        )

    from backend.core.generators.features_generator import (
        FeaturesGenerator,
        FeaturesGeneratorInput,
    )

    raw_features = await FeaturesGenerator().generate(
        FeaturesGeneratorInput(
            user_requirements=user_requirements,
            actors=actor_nodes,
            user_feedback=feedback,
        )
    )
    return raw_features.get("features", [])

def _stable_feature_id(value) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        import hashlib

        return int(
            hashlib.md5(str(value).encode()).hexdigest(),
            16,
        ) % 100000

def _resolve_feature_parent(
    feature: dict,
    feature_number,
) -> tuple[str | None, int | None]:
    parent_value = feature.get("parent_id") or feature.get("parent_ref")
    if parent_value:
        parent_ref = (
            parent_value
            if str(parent_value).startswith("tmp_")
            else f"tmp_feature_{parent_value}"
        )
        return parent_ref, _stable_feature_id(parent_value)
    if isinstance(feature_number, str) and "-" in feature_number:
        parent_number = feature_number.rsplit("-", 1)[0]
        return (
            f"tmp_feature_{parent_number}",
            _stable_feature_id(parent_number),
        )
    return None, None

def _append_feature_actor_links(
    patch: dict,
    temporary_feature_id: str,
    raw_actor_ids: list,
    actor_nodes: list[ActorNode],
    actor_ref_by_id: dict,
) -> list[int]:
    if not raw_actor_ids and actor_nodes:
        raw_actor_ids = [actor_nodes[0].actorId]
    feature_actor_ids = []
    for actor_id in raw_actor_ids:
        actor_ref = _resolve_new_actor_ref(
            actor_id,
            actor_ref_by_id,
            actor_nodes,
        )
        if actor_ref:
            patch["feature_actor_links_added"].append({
                "feature_ref": temporary_feature_id,
                "actor_ref": actor_ref,
            })
        try:
            parsed_actor_id = int(
                (actor_ref or "tmp_actor_1").rsplit("_", 1)[-1]
            )
        except (ValueError, IndexError):
            parsed_actor_id = 1
        feature_actor_ids.append(parsed_actor_id)
    return feature_actor_ids

def _link_feature_tree(feature_nodes: list[FeatureNode]) -> None:
    feature_node_by_id = {
        feature_node.featureId: feature_node
        for feature_node in feature_nodes
    }
    for feature_node in feature_nodes:
        if (
            feature_node.parentId is not None
            and feature_node.parentId in feature_node_by_id
        ):
            parent_node = feature_node_by_id[feature_node.parentId]
            if feature_node.featureId not in parent_node.childrenIds:
                parent_node.childrenIds.append(feature_node.featureId)

def _append_feature_nodes(
    patch: dict,
    features: list[dict],
    actor_nodes: list[ActorNode],
    actor_ref_by_id: dict,
) -> tuple[list[FeatureNode], dict[str, int], dict[int, str]]:
    feature_nodes = []
    temporary_feature_id_to_int = {}
    for feature_index, feature in enumerate(features):
        feature_number = (
            feature.get("feature_number")
            or feature.get("id")
            or f"gen_{feature_index + 1}"
        )
        temporary_feature_id = f"tmp_feature_{feature_number}"
        name = feature.get("feature_name") or feature.get("name")
        description = (
            feature.get("feature_description")
            or feature.get("description")
        )
        parent_ref, parent_node_id = _resolve_feature_parent(
            feature,
            feature_number,
        )
        patch["features_added"].append({
            "temp_id": temporary_feature_id,
            "name": name,
            "description": description,
            "parent_ref": parent_ref,
        })

        feature_actor_ids = _append_feature_actor_links(
            patch,
            temporary_feature_id,
            feature.get("actor_ids", []),
            actor_nodes,
            actor_ref_by_id,
        )

        feature_id = _stable_feature_id(feature_number)
        temporary_feature_id_to_int[temporary_feature_id] = feature_id
        feature_nodes.append(
            FeatureNode(
                featureId=feature_id,
                featureName=name,
                featureDescription=description,
                actorIds=feature_actor_ids,
                parentId=parent_node_id,
                childrenIds=feature.get("children_ids", []),
            )
        )

    feature_id_to_temporary_id = {
        feature_node.featureId: feature_data["temp_id"]
        for feature_data, feature_node in zip(
            patch["features_added"],
            feature_nodes, strict=False,
        )
    }
    _link_feature_tree(feature_nodes)

    return (
        feature_nodes,
        temporary_feature_id_to_int,
        feature_id_to_temporary_id,
    )

def _resolve_generated_actor_ref(
    actor,
    actor_nodes: list[ActorNode],
    patch: dict,
) -> str:
    try:
        actor_index = actor_nodes.index(actor)
        return patch["actors_added"][actor_index]["temp_id"]
    except Exception:
        return "tmp_actor_1"

def _append_llm_scenarios(
    patch: dict,
    scenarios: list[dict],
    scenario_counter: int,
    actor: ActorNode,
    feature: FeatureNode,
    feature_ref: str,
    actor_ref: str,
) -> tuple[list[ScenarioNode], int]:
    scenario_nodes = []
    for scenario in scenarios:
        temporary_scenario_id = f"tmp_scenario_{scenario_counter}"
        scenario_counter += 1
        scenario_name = (
            scenario.get("scenario_name")
            or scenario.get("name")
            or "主干业务流转"
        )
        scenario_content = (
            scenario.get("scenario_content")
            or scenario.get("content")
            or (
                f"As a {actor.actorName}, I want to "
                f"{feature.featureDescription}, "
                f"So that 我可以实现对应的业务价值"
            )
        )
        patch["scenarios_added"].append({
            "temp_id": temporary_scenario_id,
            "name": scenario_name,
            "content": scenario_content,
            "feature_ref": feature_ref,
            "actor_ref": actor_ref,
        })
        scenario_nodes.append(
            ScenarioNode(
                scenarioId=scenario_counter - 1,
                scenarioName=scenario_name,
                scenarioContent=scenario_content,
                featureId=feature.featureId,
                actorId=actor.actorId,
                acceptanceCriteria=[],
            )
        )
    return scenario_nodes, scenario_counter

def _append_llm_acceptance_criteria(
    patch: dict,
    acceptance_criteria: list,
) -> None:
    for criterion_index, criterion in enumerate(acceptance_criteria):
        if isinstance(criterion, dict) and "acceptance_criteria" in criterion:
            scenario_id = criterion.get("scenario_id") or 1
            scenario_ref = f"tmp_scenario_{scenario_id}"
            for nested_index, nested_criterion in enumerate(
                criterion["acceptance_criteria"]
            ):
                content = (
                    nested_criterion.get("criterion_content")
                    or nested_criterion.get("content")
                    if isinstance(nested_criterion, dict)
                    else nested_criterion
                )
                patch["acceptance_criteria_added"].append({
                    "scenario_ref": scenario_ref,
                    "content": content,
                    "position": nested_index + 1,
                })
            continue

        content = (
            criterion.get("criterion_content") or criterion.get("content")
            if isinstance(criterion, dict)
            else criterion
        )
        position = (
            criterion.get("position") or (criterion_index + 1)
            if isinstance(criterion, dict)
            else (criterion_index + 1)
        )
        patch["acceptance_criteria_added"].append({
            "scenario_ref": "tmp_scenario_1",
            "content": content,
            "position": position,
        })

def _append_template_scenario(
    patch: dict,
    scenario_counter: int,
    actor: ActorNode,
    feature: FeatureNode,
    feature_ref: str,
    actor_ref: str,
) -> int:
    temporary_scenario_id = f"tmp_scenario_{scenario_counter}"
    patch["scenarios_added"].append({
        "temp_id": temporary_scenario_id,
        "name": (
            f"验证{feature.featureName}在"
            f"{actor.actorName}视角下的主干业务场景"
        ),
        "content": (
            f"As a {actor.actorName}, I want to "
            f"{feature.featureDescription}, "
            f"So that 我可以获得预期的系统产出和服务。"
        ),
        "feature_ref": feature_ref,
        "actor_ref": actor_ref,
    })
    patch["acceptance_criteria_added"].append({
        "scenario_ref": temporary_scenario_id,
        "content": (
            f"Given {actor.actorName} 准备使用 {feature.featureName} 功能, "
            f"When {actor.actorName} 触发相关交互操作, "
            f"Then 系统应当正确处理并呈现 "
            f"{feature.featureName} 的相关界面与数据元。"
        ),
        "position": 1,
    })
    return scenario_counter + 1

async def _generate_llm_scenarios_and_criteria(
    patch: dict,
    scenarios_generator,
    acceptance_criteria_generator,
    user_requirements: str,
    feedback: str,
    scenario_counter: int,
    actor: ActorNode,
    feature: FeatureNode,
    feature_ref: str,
    actor_ref: str,
) -> int:
    from backend.core.generators.acceptance_criteria_generator import (
        AcceptanceCriteriaGeneratorInput,
    )
    from backend.core.generators.scenarios_generator import (
        ScenariosGeneratorInput,
    )

    raw_scenarios = await scenarios_generator.generate(
        ScenariosGeneratorInput(
            user_requirements=user_requirements,
            actor=actor,
            feature=feature,
            user_feedback=feedback,
        )
    )
    scenario_nodes, scenario_counter = _append_llm_scenarios(
        patch,
        raw_scenarios.get("scenarios", []),
        scenario_counter,
        actor,
        feature,
        feature_ref,
        actor_ref,
    )
    if not scenario_nodes:
        return scenario_counter

    raw_acceptance_criteria = await acceptance_criteria_generator.generate(
        AcceptanceCriteriaGeneratorInput(
            user_requirements=user_requirements,
            actor=actor,
            feature=feature,
            scenarios=scenario_nodes,
            user_feedback=feedback,
        )
    )
    _append_llm_acceptance_criteria(
        patch,
        raw_acceptance_criteria.get(
            "scenario_acceptance_criteria",
            raw_acceptance_criteria.get("acceptance_criteria", []),
        ),
    )
    return scenario_counter

async def _generate_scenario_patch(
    patch: dict,
    user_requirements: str,
    feedback: str,
    actor_nodes: list[ActorNode],
    feature_nodes: list[FeatureNode],
    feature_id_to_temporary_id: dict[int, str],
) -> None:
    from backend.core.generators.acceptance_criteria_generator import (
        AcceptanceCriteriaGenerator,
    )
    from backend.core.generators.scenarios_generator import (
        ScenariosGenerator,
    )

    scenarios_generator = ScenariosGenerator()
    acceptance_criteria_generator = AcceptanceCriteriaGenerator()
    actor_by_id = {actor.actorId: actor for actor in actor_nodes}
    leaf_features = [
        feature for feature in feature_nodes if not feature.childrenIds
    ]
    primary_leaf = (
        leaf_features[0]
        if leaf_features
        else (feature_nodes[0] if feature_nodes else None)
    )
    scenario_counter = 1
    llm_scenarios_generated = False

    for leaf_feature in leaf_features:
        actor_ids = (
            leaf_feature.actorIds
            if leaf_feature.actorIds
            else [actor_nodes[0].actorId if actor_nodes else 1]
        )
        feature_ref = feature_id_to_temporary_id.get(
            leaf_feature.featureId,
            "tmp_feature_1",
        )
        for actor_id in actor_ids:
            actor = actor_by_id.get(actor_id) or actor_nodes[0]
            actor_ref = _resolve_generated_actor_ref(
                actor,
                actor_nodes,
                patch,
            )
            use_llm = (
                leaf_feature == primary_leaf
                and not llm_scenarios_generated
                and actor_id == actor_ids[0]
            )
            if not use_llm:
                scenario_counter = _append_template_scenario(
                    patch,
                    scenario_counter,
                    actor,
                    leaf_feature,
                    feature_ref,
                    actor_ref,
                )
                continue

            llm_scenarios_generated = True
            scenario_counter = await _generate_llm_scenarios_and_criteria(
                patch,
                scenarios_generator,
                acceptance_criteria_generator,
                user_requirements,
                feedback,
                scenario_counter,
                actor,
                leaf_feature,
                feature_ref,
                actor_ref,
            )
