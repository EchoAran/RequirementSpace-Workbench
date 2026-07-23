import re
from string import Formatter
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.modules.diagnosis_quality.public import FindingService
from backend.api.modules.project_lifecycle.application.project_service import ProjectService
from backend.core.generators.prototype_generator import PrototypeGenerator, PrototypeGeneratorInput
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.core.localized_messages import MESSAGES, localized_message


CJK = re.compile(r"[\u4e00-\u9fff]")


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name}


def _english_context():
    return current_llm_context.set(
        LLMRequestContext("https://llm.example.com", "key", "model", "en-US")
    )


def test_localized_message_catalog_has_locale_and_placeholder_parity():
    for key, translations in MESSAGES.items():
        assert set(translations) == {"zh-CN", "en-US"}, key
        assert _fields(translations["zh-CN"]) == _fields(translations["en-US"]), key


def test_localized_message_uses_request_locale():
    token = _english_context()
    try:
        assert localized_message("prototype_submit") == "Submit"
    finally:
        current_llm_context.reset(token)


@pytest.mark.asyncio
async def test_prototype_defaults_and_controls_follow_english_content_locale():
    token = _english_context()
    try:
        result = await PrototypeGenerator().generate(
            PrototypeGeneratorInput(
                project_id=1,
                project_name="",
                project_description="",
                user_requirements="",
            )
        )
    finally:
        current_llm_context.reset(token)

    output = result["HTML"] + result["Javascript"]
    assert '<html lang="en-US">' in output
    assert "Primary user" in output
    assert "Default prototype user" in output
    assert "Submit" in output
    assert not CJK.search(output)


@pytest.mark.asyncio
async def test_markdown_headings_follow_english_content_locale():
    detail = SimpleNamespace(
        project_name="Inventory",
        project_description="Track warehouse stock",
        user_requirements="Keep quantities accurate",
        actors=[],
        features=[],
        business_objects=[],
        flows=[],
    )
    service = ProjectService()
    service.get_project_detail = AsyncMock(return_value=detail)
    token = _english_context()
    try:
        with patch.object(FindingService, "list_findings", new=AsyncMock(return_value=[])):
            markdown = await service.export_project_markdown(1, AsyncMock())
    finally:
        current_llm_context.reset(token)

    assert "# Requirement Space PRD Report - Inventory" in markdown
    assert "Project information" in markdown
    assert "No actor data." in markdown
    assert not CJK.search(markdown)
