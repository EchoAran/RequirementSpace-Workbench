from backend.api.routes.project_creation_routes import (
    router as project_creation_router,
)
from backend.api.routes.blank_project_routes import (
    router as blank_project_router,
)
from backend.api.routes.actor_generation_routes import (
    router as actor_generation_router,
)
from backend.api.routes.feature_generation_routes import (
    router as feature_generation_router,
)
from backend.api.routes.flow_generation_routes import (
    router as flow_generation_router,
)
from backend.api.routes.scenario_generation_routes import (
    router as scenario_generation_router,
)
from backend.api.routes.acceptance_criteria_generation_routes import (
    router as acceptance_criteria_generation_router,
)
from backend.api.routes.scope_generation_routes import (
    router as scope_generation_router,
)
from backend.api.routes.issue_routes import (
    router as issue_router,
)
from backend.api.routes.next_suggestion_routes import (
    router as next_suggestion_router,
)
from backend.api.routes.perception_slot_filling_routes import (
    router as perception_slot_filling_router,
)
from backend.api.routes.actor_routes import (
    router as actor_router,
)
from backend.api.routes.feature_routes import (
    router as feature_router,
)
from backend.api.routes.scenario_routes import (
    router as scenario_router,
)
from backend.api.routes.business_object_routes import (
    router as business_object_router,
)
from backend.api.routes.flow_routes import (
    router as flow_router,
)
from backend.api.routes.scope_routes import (
    router as scope_router,
)
from backend.api.routes.choice_routes import (
    router as choice_router,
)
from backend.api.routes.project_requirements_routes import (
    router as project_requirements_router,
)
from backend.api.routes.ai_add_session_routes import (
    router as ai_add_session_router,
    draft_router as ai_object_generation_draft_router,
)
from backend.api.routes.node_status_routes import (
    router as node_status_router,
)
from backend.api.routes.project_creation_choice_routes import (
    router as project_creation_choice_router,
)

__all__ = [
    "choice_router",
    "project_creation_router",
    "project_creation_choice_router",
    "blank_project_router",
    "actor_generation_router",
    "feature_generation_router",
    "flow_generation_router",
    "scenario_generation_router",
    "acceptance_criteria_generation_router",
    "scope_generation_router",
    "issue_router",
    "next_suggestion_router",
    "perception_slot_filling_router",
    "actor_router",
    "feature_router",
    "scenario_router",
    "business_object_router",
    "flow_router",
    "scope_router",
    "project_requirements_router",
    "ai_add_session_router",
    "ai_object_generation_draft_router",
    "node_status_router",
]

