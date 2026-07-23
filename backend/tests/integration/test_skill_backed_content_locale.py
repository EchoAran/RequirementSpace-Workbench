from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

from backend.api.modules.project_lifecycle.schemas.project import (
    BusinessObjectDetail,
    ProjectDetailResponse,
)
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.integration.skill_backed_services.scope_generation_service import (
    BackendLLMKanoSkill,
    SkillBackedScopeGenerationService,
)
from backend.integration.skill_backed_services.kano_scope_adapter import KanoScopeAdapter
from backend.integration.skill_backed_services.skill_imports import import_skill_module
from backend.integration.skill_backed_services.spl_semantic_export_service import (
    SplSemanticExportService,
    _SEMANTIC_EXPORT_CACHE,
)
from backend.services.llm_handler_service import CONTENT_LANGUAGE_PROTOCOL_MARKER, LLMHandler


def _context(locale: str, source: str = "default") -> LLMRequestContext:
    return LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="sk-test",
        model_name="test-model",
        content_locale=locale,
        content_locale_source=source,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("locale", "expected_protocol"),
    [("zh-CN", "中文 (zh-CN)"), ("en-US", "English (en-US)")],
)
async def test_scope_generation_preserves_content_locale_in_skill_thread(locale, expected_protocol):
    captured = {}

    class KanoSkill:
        def analyze(self, _requirement_text, _feature_tree):
            return self._ask_json("Analyze the supplied features and return the required JSON.")

    async def capture_call(self, request_data, **_kwargs):
        captured["messages"] = request_data["messages"]
        captured["thread_locale"] = current_llm_context.get().content_locale
        return "{}"

    service = object.__new__(SkillBackedScopeGenerationService)
    service._kano_skill = BackendLLMKanoSkill(KanoSkill())
    service._kano_skill._sync_llm_json_client._async_client._llm_handler.temperature = "0.7"
    service._adapter = MagicMock()
    service._adapter.build_kano_feature_tree.return_value = {"features": []}
    service._adapter.to_current_scopes.return_value = []
    service._load_project_context = AsyncMock(return_value=("Requirements", [], []))
    service._normalize_generated_scopes = MagicMock(return_value=[])
    service._build_response_payload = MagicMock(return_value={})

    token = current_llm_context.set(_context(locale))
    try:
        with patch.object(LLMHandler, "_call_api", capture_call):
            await service._generate_preview(project_id=1, user_feedback=None, session=MagicMock())
    finally:
        current_llm_context.reset(token)

    outbound_content = "\n".join(message["content"] for message in captured["messages"])
    assert captured["thread_locale"] == locale
    assert outbound_content.count(CONTENT_LANGUAGE_PROTOCOL_MARKER) == 1
    assert expected_protocol in outbound_content
    assert "必须全部且只能使用中文" not in outbound_content


@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_kano_parallel_map_preserves_content_locale(locale):
    kano_core = import_skill_module("kano-skill", "kano_skill.core")
    token = current_llm_context.set(_context(locale))
    try:
        observed = kano_core._parallel_map(
            [1, 2],
            lambda _item: current_llm_context.get().content_locale,
        )
    finally:
        current_llm_context.reset(token)

    assert observed == [locale, locale]


def test_kano_reason_uses_configured_language():
    chinese = KanoScopeAdapter._reason(
        category="O",
        category_name="Performance",
        scope_status="CURRENT",
        better_worse={"Better": 1.0, "Worse": -1.0},
        reason_summary={
            "functional_viewpoint": "能够节省时间",
            "dysfunctional_viewpoint": "需要手动收集信息",
        },
        locale="zh-CN",
    )
    english = KanoScopeAdapter._reason(
        category="O",
        category_name="Performance",
        scope_status="CURRENT",
        better_worse={"Better": 1.0, "Worse": -1.0},
        reason_summary={
            "functional_viewpoint": "it saves time",
            "dysfunctional_viewpoint": "information must be collected manually",
        },
        locale="en-US",
    )

    assert "Kano 类别 期望型(O) 对应当前范围" in chinese
    assert "Users valued its presence" not in chinese
    assert "Kano category Performance(O) maps to CURRENT" in english
    assert "用户重视该功能" not in english


@pytest.mark.asyncio
async def test_spl_semantic_export_propagates_locale_and_separates_cache():
    captured = []

    class Skill:
        def __init__(self, ask_json):
            self._ask_json = ask_json

        def export(self, payload):
            captured.append({
                "payload_locale": payload["export_options"]["language"],
                "thread_locale": current_llm_context.get().content_locale,
                "thread_locale_source": current_llm_context.get().content_locale_source,
            })
            return {
                "spl_text": f"SPL-{payload['export_options']['language']}",
                "quality": "semantic_verified",
                "warnings": [],
                "trace_links": [],
            }

    class Core:
        SplSemanticExportSkill = Skill

    service = object.__new__(SplSemanticExportService)
    service._core = Core
    service._skill = Skill(ask_json=MagicMock())
    service._available = True
    detail = ProjectDetailResponse(
        project_id="locale-cache-project",
        project_name="Project",
        project_description="Description",
        user_requirements="Requirements",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
        unresolved_gates=[],
    )

    _SEMANTIC_EXPORT_CACHE.clear()
    try:
        assert await service.export(detail, _context("en-US", "project")) == "SPL-en-US"
        assert await service.export(detail, _context("zh-CN", "user")) == "SPL-zh-CN"
        assert await service.export(detail, _context("en-US", "project")) == "SPL-en-US"
    finally:
        _SEMANTIC_EXPORT_CACHE.clear()

    assert captured == [
        {
            "payload_locale": "en-US",
            "thread_locale": "en-US",
            "thread_locale_source": "project",
        },
        {
            "payload_locale": "zh-CN",
            "thread_locale": "zh-CN",
            "thread_locale_source": "user",
        },
    ]


@pytest.mark.asyncio
async def test_spl_semantic_nested_threads_keep_locale_and_use_locale_neutral_prompts():
    observed = []

    def mock_ask_json(prompt: str) -> dict:
        observed.append((current_llm_context.get().content_locale, prompt))
        if "translating a database-backed" in prompt:
            return {"type_name": "Order", "fields": []}
        return {"coverage_passed": True, "semantic_risks": []}

    detail = ProjectDetailResponse(
        project_id="semantic-locale-thread-project",
        project_name="English Project",
        project_description="Description",
        user_requirements="Requirements",
        business_objects=[BusinessObjectDetail(
            business_object_id=1,
            business_object_name="Order",
            business_object_description="An order",
            updated_at=datetime.now(),
        )],
    )
    _SEMANTIC_EXPORT_CACHE.clear()
    try:
        with patch(
            "backend.integration.skill_backed_services.spl_semantic_export_service.SyncSkillBackedLLMJsonClient.ask_json",
            side_effect=mock_ask_json,
        ):
            await SplSemanticExportService().export(detail, _context("en-US", "project"))
    finally:
        _SEMANTIC_EXPORT_CACHE.clear()

    assert observed
    assert all(locale == "en-US" for locale, _ in observed)
    assert all("[Output Language]\nen-US" in prompt for _, prompt in observed)
    assert all("entirely in Chinese" not in prompt for _, prompt in observed)
