from backend.api.services.project_creation_service import ProjectCreationService
from backend.api.services.project_creation_choice_service import (
    ProjectCreationChoiceGroupService,
    ProjectCreationChoiceAdapter,
)
from backend.api.services.blank_project_service import BlankProjectService
from backend.api.services.actor_generation_service import ActorGenerationService
from backend.api.services.feature_generation_service import FeatureGenerationService
from backend.api.services.flow_generation_service import FlowGenerationService
from backend.api.services.scenario_generation_service import ScenarioGenerationService
from backend.api.services.acceptance_criteria_generation_service import AcceptanceCriteriaGenerationService
from backend.api.services.scope_generation_service import ScopeGenerationService
from backend.api.services.issue_service import IssueService
from backend.api.services.next_suggestion_service import NextSuggestionService
from backend.api.services.perception_job_service import PerceptionJobService
from backend.api.services.perception_slot_filling_service import PerceptionSlotFillingService
from backend.api.services.perception_job_invalidation_service import (
    mark_perception_jobs_stale,
)
from backend.api.services.choice_service import ChoiceService
# Phase 3: import adapters to trigger @register_adapter decorators
from backend.api.services import generation_choice_adapters  # noqa: F401

from backend.api.services.generation_choice_service import (
    GenerationChoiceService,
    GenerationChoiceSettings,
    GenerationCandidate,
    CandidateContext,
    CandidateRunResult,
    BaseGenerationChoiceAdapter,
    register_adapter,
    get_adapter,
    get_generation_choice_applier,
    run_candidate_generation,
)

__all__ = [
    "ProjectCreationService",
    "BlankProjectService",
    "ActorGenerationService",
    "FeatureGenerationService",
    "FlowGenerationService",
    "ScenarioGenerationService",
    "AcceptanceCriteriaGenerationService",
    "ScopeGenerationService",
    "IssueService",
    "NextSuggestionService",
    "PerceptionJobService",
    "PerceptionSlotFillingService",
    "mark_perception_jobs_stale",
    "ChoiceService",
    # Phase 1: generation choice
    "GenerationChoiceService",
    "GenerationChoiceSettings",
    "GenerationCandidate",
    "CandidateContext",
    "CandidateRunResult",
    "BaseGenerationChoiceAdapter",
    "register_adapter",
    "get_adapter",
    "get_generation_choice_applier",
    "run_candidate_generation",
    # Phase 2: project creation choice
    "ProjectCreationChoiceGroupService",
    "ProjectCreationChoiceAdapter",
]
