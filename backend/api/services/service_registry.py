from backend.api.services.acceptance_criteria_generation_service import (
    AcceptanceCriteriaGenerationService,
)
from backend.api.services.actor_generation_service import ActorGenerationService
from backend.api.services.feature_generation_service import (
    FeatureGenerationService,
)
from backend.api.services.flow_generation_service import FlowGenerationService
from backend.api.services.scenario_generation_service import (
    ScenarioGenerationService,
)
from backend.api.services.scope_generation_service import ScopeGenerationService


# Draft services keep in-memory draft state. Routes and issue resolvers must
# share these instances, otherwise a resolver-created draft cannot be confirmed
# through the normal draft API.
actor_generation_service = ActorGenerationService()
feature_generation_service = FeatureGenerationService()
scenario_generation_service = ScenarioGenerationService()
acceptance_criteria_generation_service = AcceptanceCriteriaGenerationService()
flow_generation_service = FlowGenerationService()
scope_generation_service = ScopeGenerationService()
