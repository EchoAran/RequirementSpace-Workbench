import os
import logging
from pathlib import Path

from dotenv import load_dotenv

from backend.api.services.acceptance_criteria_generation_service import (
    AcceptanceCriteriaGenerationService,
)
from backend.api.services.actor_generation_service import ActorGenerationService
from backend.api.services.feature_generation_service import (
    FeatureGenerationService,
)
from backend.api.services.flow_generation_service import FlowGenerationService
from backend.api.services.project_creation_service import ProjectCreationService
from backend.api.services.prototype_generation_service import PrototypeGenerationService
from backend.api.services.scenario_generation_service import (
    ScenarioGenerationService,
)
from backend.api.services.scope_generation_service import ScopeGenerationService
from backend.api.services.project_service import ProjectService


# Draft services keep in-memory draft state. Routes and issue resolvers must
# share these instances, otherwise a resolver-created draft cannot be confirmed
# through the normal draft API.
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")

actor_generation_service = ActorGenerationService()
flow_generation_service = FlowGenerationService()

generation_backend = os.environ.get(
    "REQUIREMENTSPACE_GENERATION_BACKEND",
    "legacy",
).strip().lower()

logger.info(
    "RequirementSpace generation backend: %s",
    generation_backend,
)

if generation_backend == "skill":
    from backend.integration.skill_backed_services.acceptance_criteria_generation_service import (
        SkillBackedAcceptanceCriteriaGenerationService,
    )
    from backend.integration.skill_backed_services.feature_generation_service import (
        SkillBackedFeatureGenerationService,
    )
    from backend.integration.skill_backed_services.project_creation_service import (
        SkillBackedProjectCreationService,
    )
    from backend.integration.skill_backed_services.prototype_generation_service import (
        SkillBackedPrototypeGenerationService,
    )
    from backend.integration.skill_backed_services.scenario_generation_service import (
        SkillBackedScenarioGenerationService,
    )
    from backend.integration.skill_backed_services.scope_generation_service import (
        SkillBackedScopeGenerationService,
    )

    project_creation_service = SkillBackedProjectCreationService()
    feature_generation_service = SkillBackedFeatureGenerationService()
    scenario_generation_service = SkillBackedScenarioGenerationService()
    acceptance_criteria_generation_service = (
        SkillBackedAcceptanceCriteriaGenerationService()
    )
    scope_generation_service = SkillBackedScopeGenerationService()
    prototype_generation_service = SkillBackedPrototypeGenerationService()
else:
    project_creation_service = ProjectCreationService()
    feature_generation_service = FeatureGenerationService()
    scenario_generation_service = ScenarioGenerationService()
    acceptance_criteria_generation_service = AcceptanceCriteriaGenerationService()
    scope_generation_service = ScopeGenerationService()
    prototype_generation_service = PrototypeGenerationService()

project_service = ProjectService()
