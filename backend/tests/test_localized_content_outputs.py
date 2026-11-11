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
        with patch("backend.api.modules.project_lifecycle.application.project_service._resolve_branch_context", new=AsyncMock(return_value=(None, SimpleNamespace(id=2), {"can_write": True}))), patch.object(FindingService, "list_findings", new=AsyncMock(return_value=[])):
            markdown = await service.export_project_markdown(1, AsyncMock())
    finally:
        current_llm_context.reset(token)

    assert "# Requirement Space PRD Report - Inventory" in markdown
    assert "Project information" in markdown
    assert "No actor data." in markdown
    assert not CJK.search(markdown)


@pytest.mark.asyncio
async def test_markdown_preserves_nested_requirement_content():
    actor = SimpleNamespace(
        actor_id=1,
        actor_name="Clerk",
        actor_description="Handles orders",
    )
    criterion = SimpleNamespace(
        criterion_content="Order is saved",
    )
    scenario = SimpleNamespace(
        scenario_name="Create order",
        scenario_content="Given a valid request",
        acceptance_criteria=[criterion],
    )
    parent_feature = SimpleNamespace(
        feature_id=10,
        parent_id=None,
        feature_name="Order management",
        feature_description="Manage orders",
        scope=SimpleNamespace(scope_status="current"),
        scenarios=[],
    )
    child_feature = SimpleNamespace(
        feature_id=11,
        parent_id=10,
        feature_name="Create order",
        feature_description="Create a new order",
        scope=None,
        scenarios=[scenario],
    )
    attribute = SimpleNamespace(
        business_object_attribute_name="Order number",
        business_object_attribute_description="Unique identifier",
        business_object_attribute_type="string",
        business_object_attribute_example="SO-1",
    )
    business_object = SimpleNamespace(
        business_object_id=20,
        business_object_name="Order",
        business_object_description="Order data",
        business_object_attributes=[attribute],
    )
    step = SimpleNamespace(
        step_name="Save order",
        step_type="task",
        step_description="Persist order data",
        actor_ids=[1],
        input_business_object_ids=[20],
        output_business_object_ids=[20],
    )
    flow = SimpleNamespace(
        flow_name="Order flow",
        flow_description="Create an order",
        flow_steps=[step],
    )
    detail = SimpleNamespace(
        project_name="Orders",
        project_description="Order project",
        user_requirements="Create orders",
        actors=[actor],
        features=[parent_feature, child_feature],
        business_objects=[business_object],
        flows=[flow],
    )
    service = ProjectService()
    service.get_project_detail = AsyncMock(return_value=detail)
    token = _english_context()
    try:
        with patch("backend.api.modules.project_lifecycle.application.project_service._resolve_branch_context", new=AsyncMock(return_value=(None, SimpleNamespace(id=2), {"can_write": True}))), patch.object(
            FindingService,
            "list_findings",
            new=AsyncMock(return_value=[]),
        ):
            markdown = await service.export_project_markdown(
                1,
                AsyncMock(),
            )
    finally:
        current_llm_context.reset(token)

    for expected in (
        "- **Order management**: Manage orders [Scope: Current]",
        "  - **Create order**: Create a new order",
        "Order is saved",
        "| Order number | Unique identifier | string | SO-1 |",
        "Clerk",
        "Order",
    ):
        assert expected in markdown
