import logging
from pathlib import Path

from dotenv import load_dotenv

# Import ports
from backend.api.modules.preview_convergence.ports import set_prototype_generation_service
from backend.api.modules.preview_convergence.public import PrototypeGenerationService
from backend.api.modules.project_lifecycle.ports import (
    set_project_creation_service,
    set_project_service,
)
from backend.api.modules.project_lifecycle.public import ProjectCreationService, ProjectService
from backend.api.modules.requirements_core.ports import (
    set_acceptance_criteria_generation_service,
    set_actor_generation_service,
    set_feature_generation_service,
    set_flow_generation_service,
    set_flow_refinement_service,
    set_rule_generation_service,
    set_scenario_generation_service,
    set_scope_generation_service,
)

# Import services
from backend.api.modules.requirements_core.public import (
    ActorGenerationService,
    FlowGenerationService,
    FlowRefinementService,
    RuleGenerationService,
)

logger = logging.getLogger(__name__)


class BootstrapRegistry:
    def __init__(self):
        self.generation_backend = None
        self.scope_generation_service = None


registry = BootstrapRegistry()


def bootstrap_services():
    """Instantiate and register all services to their ports."""
    # Ensure env is loaded
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

    logger.info("Initializing generation services")

    actor_gen = ActorGenerationService()
    flow_gen = FlowGenerationService()
    flow_refinement_gen = FlowRefinementService()
    rule_gen = RuleGenerationService()
    project_srv = ProjectService()

    from backend.api.modules.preview_convergence.ports.preview_generator import set_page_generator
    from backend.integration.skill_backed_services.acceptance_criteria_generation_service import (
        SkillBackedAcceptanceCriteriaGenerationService,
    )
    from backend.integration.skill_backed_services.feature_generation_service import (
        SkillBackedFeatureGenerationService,
    )
    from backend.integration.skill_backed_services.project_creation_service import (
        SkillBackedActorFeaturePreviewGenerator,
    )
    from backend.integration.skill_backed_services.prototype_generation_service import (
        SkillBackedPrototypePageGenerator,
    )
    from backend.integration.skill_backed_services.scenario_generation_service import (
        SkillBackedScenarioGenerationService,
    )
    from backend.integration.skill_backed_services.scope_generation_service import (
        SkillBackedScopeGenerationService,
    )

    proj_creation = ProjectCreationService(
        preview_generator=SkillBackedActorFeaturePreviewGenerator()
    )
    feat_gen = SkillBackedFeatureGenerationService()
    scen_gen = SkillBackedScenarioGenerationService()
    ac_gen = SkillBackedAcceptanceCriteriaGenerationService()
    scope_gen = SkillBackedScopeGenerationService()

    page_gen = SkillBackedPrototypePageGenerator()
    set_page_generator(page_gen)
    proto_gen = PrototypeGenerationService(page_generator=page_gen)
    # Wire to ports
    set_prototype_generation_service(proto_gen)
    set_actor_generation_service(actor_gen)
    set_feature_generation_service(feat_gen)
    set_scenario_generation_service(scen_gen)
    set_acceptance_criteria_generation_service(ac_gen)
    set_flow_generation_service(flow_gen)
    set_flow_refinement_service(flow_refinement_gen)
    set_rule_generation_service(rule_gen)
    set_scope_generation_service(scope_gen)
    set_project_creation_service(proj_creation)
    set_project_service(project_srv)

    registry.generation_backend = "skill"
    registry.scope_generation_service = scope_gen

    return registry


def register_choice_adapters(registry):
    """Register all built-in choice adapters to the registry."""
    from backend.api.modules.project_lifecycle.public import ProjectCreationChoiceAdapter
    from backend.api.modules.requirements_core.public import (
        AcceptanceCriteriaGenerationChoiceAdapter,
        ActorGenerationChoiceAdapter,
        FeatureGenerationChoiceAdapter,
        FlowGenerationChoiceAdapter,
        FlowRefinementChoiceAdapter,
        RuleGenerationChoiceAdapter,
        ScenarioGenerationChoiceAdapter,
        ScopeGenerationChoiceAdapter,
    )

    registry.register("actor", ActorGenerationChoiceAdapter)
    registry.register("scenario", ScenarioGenerationChoiceAdapter)
    registry.register("acceptance_criteria", AcceptanceCriteriaGenerationChoiceAdapter)
    registry.register("feature", FeatureGenerationChoiceAdapter)
    registry.register("flow", FlowGenerationChoiceAdapter)
    registry.register("flow_refinement", FlowRefinementChoiceAdapter)
    registry.register("rule", RuleGenerationChoiceAdapter)
    registry.register("scope", ScopeGenerationChoiceAdapter)
    registry.register("project_creation", ProjectCreationChoiceAdapter)
