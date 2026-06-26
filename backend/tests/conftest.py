import os
import pytest
from sqlalchemy import event

# Seed a valid dummy encryption key for test run stability
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

# Sanitize NO_PROXY for httpx compatibility (httpx has a bug parsing unbracketed ipv6 in NO_PROXY)
if "NO_PROXY" in os.environ:
    no_proxy_parts = [p.strip() for p in os.environ["NO_PROXY"].split(",") if p.strip()]
    sanitized_parts = [p for p in no_proxy_parts if ":" not in p]
    os.environ["NO_PROXY"] = ",".join(sanitized_parts)

os.environ["REQUIREMENTSPACE_GENERATION_BACKEND"] = "legacy"

pytest_plugins = ("pytest_asyncio",)

# Setup event listeners for legacy test compatibility
# This ensures that during tests, UserModel creates a default user with ID 1
# and any project/draft created without owner_user_id gets populated with 1.
from backend.database.model import UserModel, ProjectModel, GenerativeDraftModel, UserRole
from backend.database.model import beijing_now

@event.listens_for(UserModel.__table__, "after_create")
def insert_default_user_for_tests(target, connection, **kw):
    connection.execute(
        target.insert().values(
            id=1,
            email="default@requirementspace.internal",
            password_hash="system_locked",
            role=UserRole.USER.value,
            is_active=True,
            created_at=beijing_now(),
            updated_at=beijing_now()
        )
    )

@event.listens_for(ProjectModel, "init")
def set_default_project_owner_for_tests(target, args, kwargs):
    if "owner_user_id" not in kwargs:
        kwargs["owner_user_id"] = 1

@event.listens_for(GenerativeDraftModel, "init")
def set_default_draft_owner_for_tests(target, args, kwargs):
    if "owner_user_id" not in kwargs:
        kwargs["owner_user_id"] = 1


# Monkeypatch AIAddSessionService, ProjectCreationChoiceGroupService, and GenerativeDraftStore
# to inject owner_user_id=1 for legacy test compatibility.
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService
from backend.api.modules.project_lifecycle.application.creation_choice_service import ProjectCreationChoiceGroupService
from backend.api.modules.decision_workflow.draft_store import GenerativeDraftStore

# 1. GenerativeDraftStore patcher
_orig_store_save_draft = GenerativeDraftStore.save_draft
_orig_store_get_draft = GenerativeDraftStore.get_draft
_orig_store_delete_draft = GenerativeDraftStore.delete_draft
_orig_store_discard_draft_locally = GenerativeDraftStore.discard_draft_locally

async def patch_store_save_draft(project_id, draft_id, draft_type, payload, owner_user_id=1, session=None):
    return await _orig_store_save_draft(project_id, draft_id, draft_type, payload, owner_user_id, session)

async def patch_store_get_draft(draft_id, owner_user_id=1, session=None):
    return await _orig_store_get_draft(draft_id, owner_user_id, session)

async def patch_store_delete_draft(draft_id, owner_user_id=1, session=None):
    return await _orig_store_delete_draft(draft_id, owner_user_id, session)

async def patch_store_discard_draft_locally(draft_id, owner_user_id=1):
    return await _orig_store_discard_draft_locally(draft_id, owner_user_id)

GenerativeDraftStore.save_draft = patch_store_save_draft
GenerativeDraftStore.get_draft = patch_store_get_draft
GenerativeDraftStore.delete_draft = patch_store_delete_draft
GenerativeDraftStore.discard_draft_locally = patch_store_discard_draft_locally


# 2. AIAddSessionService patcher
_orig_ai_create_session = AIAddSessionService.create_session
_orig_ai_generate_draft = AIAddSessionService.generate_draft
_orig_ai_confirm_draft = AIAddSessionService.confirm_draft
_orig_ai_discard_draft = AIAddSessionService.discard_draft

async def patch_ai_create_session(self, project_id, target_type, anchor, session, owner_user_id=1):
    return await _orig_ai_create_session(self, project_id, target_type, anchor, session, owner_user_id)

async def patch_ai_generate_draft(self, session_id, db_session, owner_user_id=1):
    return await _orig_ai_generate_draft(self, session_id, db_session, owner_user_id)

async def patch_ai_confirm_draft(self, draft_id, db_session, owner_user_id=1):
    return await _orig_ai_confirm_draft(self, draft_id, db_session, owner_user_id)

async def patch_ai_discard_draft(self, draft_id, db_session, owner_user_id=1):
    return await _orig_ai_discard_draft(self, draft_id, db_session, owner_user_id)

AIAddSessionService.create_session = patch_ai_create_session
AIAddSessionService.generate_draft = patch_ai_generate_draft
AIAddSessionService.confirm_draft = patch_ai_confirm_draft
AIAddSessionService.discard_draft = patch_ai_discard_draft


# 3. ProjectCreationChoiceGroupService patcher
_orig_pcg_create_choice_group = ProjectCreationChoiceGroupService.create_choice_group
_orig_pcg_get_choice_group = ProjectCreationChoiceGroupService.get_choice_group
_orig_pcg_list_open_choice_groups = ProjectCreationChoiceGroupService.list_open_choice_groups
_orig_pcg_accept_choice = ProjectCreationChoiceGroupService.accept_choice
_orig_pcg_discard_choice_group = ProjectCreationChoiceGroupService.discard_choice_group
_orig_pcg_defer_choice_group = ProjectCreationChoiceGroupService.defer_choice_group

async def patch_pcg_create_choice_group(self, user_requirements, owner_user_id=1, candidate_count=None, user_feedback=None, session=None):
    return await _orig_pcg_create_choice_group(self, user_requirements, owner_user_id, candidate_count, user_feedback, session)

async def patch_pcg_get_choice_group(self, group_id, owner_user_id=1, session=None):
    return await _orig_pcg_get_choice_group(self, group_id, owner_user_id, session)

async def patch_pcg_list_open_choice_groups(self, owner_user_id=1, session=None):
    return await _orig_pcg_list_open_choice_groups(self, owner_user_id, session)

async def patch_pcg_accept_choice(self, group_id, choice_id, owner_user_id=1, session=None):
    return await _orig_pcg_accept_choice(self, group_id, choice_id, owner_user_id, session)

async def patch_pcg_discard_choice_group(self, group_id, owner_user_id=1, session=None):
    return await _orig_pcg_discard_choice_group(self, group_id, owner_user_id, session)

async def patch_pcg_defer_choice_group(self, group_id, owner_user_id=1, session=None):
    return await _orig_pcg_defer_choice_group(self, group_id, owner_user_id, session)

ProjectCreationChoiceGroupService.create_choice_group = patch_pcg_create_choice_group
ProjectCreationChoiceGroupService.get_choice_group = patch_pcg_get_choice_group
ProjectCreationChoiceGroupService.list_open_choice_groups = patch_pcg_list_open_choice_groups
ProjectCreationChoiceGroupService.accept_choice = patch_pcg_accept_choice
ProjectCreationChoiceGroupService.discard_choice_group = patch_pcg_discard_choice_group
ProjectCreationChoiceGroupService.defer_choice_group = patch_pcg_defer_choice_group


class TestPerceptionStaleNotifier:
    async def mark_stale(
        self,
        project_id: int,
        stages: set[str],
        session,
        perception_kinds: set[str] | None = None,
        clear_active_slot: bool = True,
    ) -> None:
        from backend.api.modules.diagnosis_quality.public import (
            mark_perception_jobs_stale,
        )
        await mark_perception_jobs_stale(
            project_id=project_id,
            stages=stages,
            session=session,
            perception_kinds=perception_kinds,
            clear_active_slot=clear_active_slot,
        )

from backend.api.modules.requirements_core.ports import set_notifier
set_notifier(TestPerceptionStaleNotifier())

# Setup ChoiceAdapterRegistry for testing
from backend.api.modules.decision_workflow.ports.ports import ChoiceAdapterRegistry
from backend.api.bootstrap import register_choice_adapters
register_choice_adapters(ChoiceAdapterRegistry())

# Blocker 2: Setup ChoiceGroupCreator and GenerationDraftCreator for testing
from backend.main import ConcreteGenerationDraftCreator
from backend.api.modules.decision_workflow.public import GenerationChoiceService
from backend.core.issue_resolution.ports import (
    set_choice_group_creator,
    set_choice_group_settings,
    set_generation_draft_creator,
)
choice_service_test = GenerationChoiceService()
set_choice_group_creator(choice_service_test)
set_choice_group_settings(choice_service_test.settings)
set_generation_draft_creator(ConcreteGenerationDraftCreator())


# Setup ports for testing before each test
@pytest.fixture(autouse=True)
def register_ports_before_each_test():
    from backend.api.bootstrap import bootstrap_services
    bootstrap_services()
