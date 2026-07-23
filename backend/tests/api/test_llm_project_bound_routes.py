from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api.dependencies import llm as llm_dependency
from backend.api.modules.ai_interaction.ai_add import routes as ai_add_routes
from backend.api.modules.diagnosis_quality.perception import routes as perception_routes
from backend.api.modules.requirements_core.feature import routes as feature_routes
from backend.api.modules.requirements_core.flow import routes as flow_routes
from backend.api.modules.requirements_core.scenario import routes as scenario_routes
from backend.api.modules.requirements_core.scope import routes as scope_routes
from backend.api.modules.project_lifecycle.routes import project as project_routes
from backend.core.llm_context import current_llm_context


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _Session:
    async def execute(self, _statement):
        return _ScalarResult("en-US")


PROJECT_BOUND_ROUTES = [
    (feature_routes, "create_feature_generation_draft", "feature_generation_service", "create_draft"),
    (flow_routes, "create_flow_generation_draft", "flow_generation_service", "create_draft"),
    (scope_routes, "create_scope_generation_draft", "scope_generation_service", "create_draft"),
    (scenario_routes, "create_full_scenario_generation_draft", "scenario_generation_service", "create_full_draft"),
    (scenario_routes, "create_single_scenario_generation_draft", "scenario_generation_service", "create_single_draft"),
    (scenario_routes, "create_full_acceptance_criteria_generation_draft", "acceptance_criteria_generation_service", "create_full_draft"),
    (scenario_routes, "create_single_acceptance_criteria_generation_draft", "acceptance_criteria_generation_service", "create_single_draft"),
    (scenario_routes, "create_batch_acceptance_criteria_generation_draft", "acceptance_criteria_generation_service", "create_batch_draft"),
    (perception_routes, "create_actor_slot_filling_draft", "perception_slot_filling_service", "create_actor_draft"),
    (perception_routes, "create_feature_slot_filling_draft", "perception_slot_filling_service", "create_feature_draft"),
    (perception_routes, "create_scenario_slot_filling_draft", "perception_slot_filling_service", "create_scenario_draft"),
    (perception_routes, "create_acceptance_criteria_slot_filling_draft", "perception_slot_filling_service", "create_acceptance_criteria_draft"),
    (perception_routes, "create_flow_slot_filling_draft", "perception_slot_filling_service", "create_flow_draft"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route_module", "route_name", "service_name", "method_name"),
    PROJECT_BOUND_ROUTES,
    ids=[item[1] for item in PROJECT_BOUND_ROUTES],
)
async def test_body_project_routes_resolve_project_content_locale(
    monkeypatch,
    route_module,
    route_name,
    service_name,
    method_name,
):
    user = SimpleNamespace(id=7, preferred_locale="zh-CN")
    project = SimpleNamespace(id=42)
    session = _Session()
    request = SimpleNamespace(
        project_id="project-public-id",
        feature_id=11,
        scenario_id=12,
        scenario_ids=[12, 13],
        perception_job_id=14,
    )
    monkeypatch.setattr(
        llm_dependency.llm_config_service,
        "resolve_for_user",
        AsyncMock(
            return_value={
                "api_url": "https://llm.example.test",
                "api_key": "secret",
                "model_name": "test-model",
            }
        ),
    )
    monkeypatch.setattr(
        route_module,
        "require_owned_project",
        AsyncMock(return_value=project),
    )

    captured = {}

    async def capture_context(**_kwargs):
        context = current_llm_context.get()
        captured["locale"] = context.content_locale
        captured["source"] = context.content_locale_source
        return {}

    service = getattr(route_module, service_name)
    monkeypatch.setattr(service, method_name, capture_context)

    await getattr(route_module, route_name)(request, user, session)

    assert captured == {"locale": "en-US", "source": "project"}


@pytest.mark.asyncio
async def test_ai_explain_resolves_project_content_locale(monkeypatch):
    from backend.api.dependencies import project_access
    from backend.api.modules.ai_interaction.ai_explain import routes as explain_routes

    user = SimpleNamespace(id=7, preferred_locale="zh-CN")
    project = SimpleNamespace(id=42)
    session = _Session()
    request = SimpleNamespace(
        project_id="project-public-id",
        scope=SimpleNamespace(model_dump=lambda: {"kind": "workspace"}),
        question="Explain this project",
    )
    monkeypatch.setattr(
        llm_dependency.llm_config_service,
        "resolve_for_user",
        AsyncMock(
            return_value={
                "api_url": "https://llm.example.test",
                "api_key": "secret",
                "model_name": "test-model",
            }
        ),
    )
    monkeypatch.setattr(
        project_access,
        "require_project_member",
        AsyncMock(return_value=project),
    )

    captured = {}

    class _ExplainService:
        async def explain(self, **_kwargs):
            context = current_llm_context.get()
            captured["locale"] = context.content_locale
            captured["source"] = context.content_locale_source
            return {"answer": "ok", "context_summary": {"scope_label": "", "objects_loaded": []}}

    monkeypatch.setattr(explain_routes, "_get_service", lambda: _ExplainService())

    await explain_routes.explain(request, user, session)

    assert captured == {"locale": "en-US", "source": "project"}


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["message", "draft"])
async def test_ai_add_session_routes_resolve_session_project_content_locale(
    monkeypatch,
    action,
):
    user = SimpleNamespace(id=7, preferred_locale="zh-CN")
    ai_session = SimpleNamespace(id=81, project_id=42)
    session = _Session()
    monkeypatch.setattr(
        llm_dependency.llm_config_service,
        "resolve_for_user",
        AsyncMock(
            return_value={
                "api_url": "https://llm.example.test",
                "api_key": "secret",
                "model_name": "test-model",
            }
        ),
    )

    captured = {}

    async def capture_context(**_kwargs):
        context = current_llm_context.get()
        captured["locale"] = context.content_locale
        captured["source"] = context.content_locale_source
        return {}

    service = SimpleNamespace(
        append_user_message=capture_context,
        generate_draft=capture_context,
    )
    monkeypatch.setattr(ai_add_routes, "_get_service", lambda: service)

    if action == "message":
        await ai_add_routes.send_ai_add_message(
            SimpleNamespace(content="Continue"),
            user,
            ai_session,
            session,
        )
    else:
        await ai_add_routes.generate_ai_add_draft(user, ai_session, session)

    assert captured == {"locale": "en-US", "source": "project"}


@pytest.mark.asyncio
async def test_markdown_export_resolves_project_content_locale(monkeypatch):
    user = SimpleNamespace(id=7, preferred_locale="zh-CN")
    project = SimpleNamespace(id=42)
    session = _Session()
    monkeypatch.setattr(
        llm_dependency.llm_config_service,
        "resolve_for_user",
        AsyncMock(
            return_value={
                "api_url": "https://llm.example.test",
                "api_key": "secret",
                "model_name": "test-model",
            }
        ),
    )

    captured = {}

    async def capture_context(**_kwargs):
        context = current_llm_context.get()
        captured["locale"] = context.content_locale
        captured["source"] = context.content_locale_source
        return "markdown"

    monkeypatch.setattr(
        project_routes.project_service,
        "export_project_markdown",
        capture_context,
    )

    result = await project_routes.export_project_markdown(
        "project-public-id",
        project,
        user,
        session,
    )

    assert result == "markdown"
    assert captured == {"locale": "en-US", "source": "project"}
