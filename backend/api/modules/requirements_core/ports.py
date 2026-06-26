from backend.core.notifier import (
    RequirementsChangedNotifier,
    get_notifier,
    set_notifier,
)


_feature_generation_service = None
_scope_generation_service = None
_flow_generation_service = None


def get_feature_generation_service():
    if _feature_generation_service is None:
        raise RuntimeError("FeatureGenerationService has not been registered! Please call set_feature_generation_service() at startup.")
    return _feature_generation_service


def set_feature_generation_service(service) -> None:
    global _feature_generation_service
    _feature_generation_service = service


def get_scope_generation_service():
    if _scope_generation_service is None:
        raise RuntimeError("ScopeGenerationService has not been registered! Please call set_scope_generation_service() at startup.")
    return _scope_generation_service


def set_scope_generation_service(service) -> None:
    global _scope_generation_service
    _scope_generation_service = service


def get_flow_generation_service():
    if _flow_generation_service is None:
        raise RuntimeError("FlowGenerationService has not been registered! Please call set_flow_generation_service() at startup.")
    return _flow_generation_service


def set_flow_generation_service(service) -> None:
    global _flow_generation_service
    _flow_generation_service = service


_actor_generation_service = None
_scenario_generation_service = None
_acceptance_criteria_generation_service = None


def get_actor_generation_service():
    if _actor_generation_service is None:
        raise RuntimeError("ActorGenerationService has not been registered! Please call set_actor_generation_service() at startup.")
    return _actor_generation_service


def set_actor_generation_service(service) -> None:
    global _actor_generation_service
    _actor_generation_service = service


def get_scenario_generation_service():
    if _scenario_generation_service is None:
        raise RuntimeError("ScenarioGenerationService has not been registered! Please call set_scenario_generation_service() at startup.")
    return _scenario_generation_service


def set_scenario_generation_service(service) -> None:
    global _scenario_generation_service
    _scenario_generation_service = service


def get_acceptance_criteria_generation_service():
    if _acceptance_criteria_generation_service is None:
        raise RuntimeError("AcceptanceCriteriaGenerationService has not been registered! Please call set_acceptance_criteria_generation_service() at startup.")
    return _acceptance_criteria_generation_service


def set_acceptance_criteria_generation_service(service) -> None:
    global _acceptance_criteria_generation_service
    _acceptance_criteria_generation_service = service


