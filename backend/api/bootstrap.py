import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Import ports
from backend.api.modules.preview_convergence.ports import set_prototype_generation_service
from backend.api.modules.requirements_core.ports import (
    set_actor_generation_service,
    set_feature_generation_service,
    set_scenario_generation_service,
    set_acceptance_criteria_generation_service,
    set_flow_generation_service,
    set_scope_generation_service,
)
from backend.api.modules.project_lifecycle.ports import (
    set_project_creation_service,
    set_project_service,
)

# Import services
from backend.api.modules.requirements_core.public import (
    AcceptanceCriteriaGenerationService,
    ActorGenerationService,
    FeatureGenerationService,
    FlowGenerationService,
    ScenarioGenerationService,
    ScopeGenerationService,
)
from backend.api.modules.project_lifecycle.public import ProjectService, ProjectCreationService
from backend.api.modules.preview_convergence.public import PrototypeGenerationService

logger = logging.getLogger(__name__)


class BootstrapRegistry:
    def __init__(self):
        self.actor_generation_service = None
        self.flow_generation_service = None
        self.project_creation_service = None
        self.feature_generation_service = None
        self.scenario_generation_service = None
        self.acceptance_criteria_generation_service = None
        self.scope_generation_service = None
        self.prototype_generation_service = None
        self.project_service = None
        self.generation_backend = None


registry = BootstrapRegistry()


def bootstrap_services():
    """Instantiate and register all services to their ports."""
    # Ensure env is loaded
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
    
    generation_backend = os.environ.get(
        "REQUIREMENTSPACE_GENERATION_BACKEND",
        "legacy",
    ).strip().lower()
    
    logger.info("Initializing services with backend mode: %s", generation_backend)
    
    actor_gen = ActorGenerationService()
    flow_gen = FlowGenerationService()
    project_srv = ProjectService()
    
    if generation_backend == "skill":
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
        from backend.api.modules.preview_convergence.ports.preview_generator import set_page_generator

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
    else:
        proj_creation = ProjectCreationService()
        feat_gen = FeatureGenerationService()
        scen_gen = ScenarioGenerationService()
        ac_gen = AcceptanceCriteriaGenerationService()
        scope_gen = ScopeGenerationService()
        proto_gen = PrototypeGenerationService()
        
    # Wire to ports
    set_prototype_generation_service(proto_gen)
    set_actor_generation_service(actor_gen)
    set_feature_generation_service(feat_gen)
    set_scenario_generation_service(scen_gen)
    set_acceptance_criteria_generation_service(ac_gen)
    set_flow_generation_service(flow_gen)
    set_scope_generation_service(scope_gen)
    set_project_creation_service(proj_creation)
    set_project_service(project_srv)
    
    # Store instances in registry for legacy shims
    registry.actor_generation_service = actor_gen
    registry.flow_generation_service = flow_gen
    registry.project_creation_service = proj_creation
    registry.feature_generation_service = feat_gen
    registry.scenario_generation_service = scen_gen
    registry.acceptance_criteria_generation_service = ac_gen
    registry.scope_generation_service = scope_gen
    registry.prototype_generation_service = proto_gen
    registry.project_service = project_srv
    registry.generation_backend = generation_backend

    return registry


def register_choice_adapters(registry):
    """Register all built-in choice adapters to the registry."""
    from backend.api.modules.requirements_core.public import (
        ActorGenerationChoiceAdapter,
        ScenarioGenerationChoiceAdapter,
        AcceptanceCriteriaGenerationChoiceAdapter,
        FeatureGenerationChoiceAdapter,
        FlowGenerationChoiceAdapter,
        ScopeGenerationChoiceAdapter,
    )
    from backend.api.modules.project_lifecycle.public import ProjectCreationChoiceAdapter

    registry.register("actor", ActorGenerationChoiceAdapter)
    registry.register("scenario", ScenarioGenerationChoiceAdapter)
    registry.register("acceptance_criteria", AcceptanceCriteriaGenerationChoiceAdapter)
    registry.register("feature", FeatureGenerationChoiceAdapter)
    registry.register("flow", FlowGenerationChoiceAdapter)
    registry.register("scope", ScopeGenerationChoiceAdapter)
    registry.register("project_creation", ProjectCreationChoiceAdapter)

