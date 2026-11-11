import os

import pytest
from sqlalchemy import event

# Seed a valid dummy encryption key for test run stability
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

os.environ["LLM_LOCALE_VALIDATION_MODE"] = "enforce"
os.environ.update(
    LLM_API_URL="https://llm.example.test",
    LLM_API_KEY="test-api-key",
    LLM_MODEL_NAME="test-model",
    LLM_TEMPERATURE="0.7",
)

# Sanitize NO_PROXY for httpx compatibility (httpx has a bug parsing unbracketed ipv6 in NO_PROXY)
if "NO_PROXY" in os.environ:
    no_proxy_parts = [p.strip() for p in os.environ["NO_PROXY"].split(",") if p.strip()]
    sanitized_parts = [p for p in no_proxy_parts if ":" not in p]
    os.environ["NO_PROXY"] = ",".join(sanitized_parts)

# Guard against testing directly against the production/default database
_current_db_url = os.environ.get("DATABASE_URL", "")
if not _current_db_url or "requirement_space.db" in _current_db_url:
    if os.environ.get("ALLOW_PRODUCTION_DB_FOR_TESTS") != "true":
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_requirement_space.db"

from backend.api.bootstrap import bootstrap_services, register_choice_adapters
from backend.api.modules.decision_workflow.ports.ports import ChoiceAdapterRegistry
from backend.api.modules.decision_workflow.public import GenerationChoiceService
from backend.api.modules.requirements_core.ports import set_notifier
from backend.core.issue_resolution.ports import (
    set_choice_group_creator,
    set_choice_group_settings,
    set_generation_draft_creator,
)
from backend.core.llm_context import current_llm_context, is_web_request_ctx
from backend.database.model import UserModel, UserRole, beijing_now
from backend.main import ConcreteGenerationDraftCreator, PerceptionStaleNotifier


@pytest.fixture(autouse=True)
def default_test_user():
    """Seed the owner used by isolated test databases without changing model constructors."""
    def insert_default_user(target, connection, **kwargs):
        connection.execute(
            target.insert().values(
                id=1,
                email="default@requirementspace.internal",
                password_hash="system_locked",
                role=UserRole.USER.value,
                is_active=True,
                created_at=beijing_now(),
                updated_at=beijing_now(),
            )
        )

    event.listen(UserModel.__table__, "after_create", insert_default_user)
    yield
    event.remove(UserModel.__table__, "after_create", insert_default_user)


@pytest.fixture(autouse=True)
def register_ports_before_each_test():
    bootstrap_services()
    set_notifier(PerceptionStaleNotifier())
    register_choice_adapters(ChoiceAdapterRegistry())
    choice_service = GenerationChoiceService()
    set_choice_group_creator(choice_service)
    set_choice_group_settings(choice_service.settings)
    set_generation_draft_creator(ConcreteGenerationDraftCreator())


@pytest.fixture(autouse=True)
def reset_context_vars_before_each_test():
    llm_token = current_llm_context.set(None)
    request_token = is_web_request_ctx.set(False)
    yield
    current_llm_context.reset(llm_token)
    is_web_request_ctx.reset(request_token)
