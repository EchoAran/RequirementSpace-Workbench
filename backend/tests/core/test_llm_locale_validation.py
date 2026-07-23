import json

import pytest

from backend.core.llm_locale_validation import (
    correction_preserves_structure,
    detect_content_locale,
    extract_natural_language_fields,
    validate_response_locale,
)


@pytest.mark.parametrize(
    ("fields", "locale", "expected"),
    [
        (["这是用于验证输出语言的完整中文描述。"], "zh-CN", "match"),
        (["This is a complete English description for locale validation."], "en-US", "match"),
        (["Short"], "en-US", "inconclusive"),
        (["abcdefghij"], "zh-CN", "mismatch"),
        (["中abcdefghi"], "en-US", "match"),
        (["中文abcdefgh"], "en-US", "mismatch"),
        (["English text with 中文内容混合 in the response."], "en-US", "mismatch"),
    ],
)
def test_detector_boundaries(fields, locale, expected):
    assert detect_content_locale(fields, locale).outcome == expected


def test_structured_extractor_ignores_technical_fields_and_fragments():
    payload = {
        "feature_id": "feature_12345678",
        "scope_status": "in_scope",
        "url": "https://example.com/english-only-path",
        "code": "const englishOnlyValue = true;",
        "description": (
            "这是有效的中文说明，相关地址为 https://example.com/english-only-path，"
            "代码为 `const englishOnlyValue = true;`。"
        ),
    }

    fields = extract_natural_language_fields(payload)
    result = detect_content_locale(fields, "zh-CN")

    assert fields == [payload["description"]]
    assert result.outcome == "match"


def test_pure_technical_payload_is_inconclusive():
    content = json.dumps(
        {
            "feature_id": "feature_12345678",
            "scope_status": "in_scope",
            "url": "https://example.com/api/v1/resource",
            "code": "const language = 'English';",
            "count": 12,
        }
    )

    result = validate_response_locale(content, "zh-CN")

    assert result.outcome == "inconclusive"
    assert result.field_count == 0


def test_dynamic_scenario_mapping_values_are_inspected_but_keys_are_not():
    payload = {
        "Feature F001 - Music playback": "This user story is entirely in English.",
        "gherkin": {
            "Narrative": {
                "I want": "to play local music without a network connection",
            }
        },
    }

    fields = extract_natural_language_fields(payload)
    result = detect_content_locale(fields, "zh-CN")

    assert "Feature F001 - Music playback" not in fields
    assert result.outcome == "mismatch"


def test_original_input_is_not_used_for_language_rejection():
    original_name = "English Product Name"
    content = json.dumps({"project_name": original_name})

    result = validate_response_locale(
        content,
        "zh-CN",
        messages=[{"role": "user", "content": f"Original project name: {original_name}"}],
    )

    assert result.outcome == "inconclusive"
    assert result.field_count == 0


def test_assistant_and_system_history_are_not_treated_as_user_input():
    description = "This prior assistant response is still entirely in English."
    content = json.dumps({"description": description})

    result = validate_response_locale(
        content,
        "zh-CN",
        messages=[
            {"role": "system", "content": "Answer in the requested project language."},
            {"role": "assistant", "content": description},
            {"role": "user", "content": "Continue."},
        ],
    )

    assert result.outcome == "mismatch"
    assert result.field_count == 1


def test_plain_response_that_repeats_actual_user_input_is_excluded():
    user_input = "Keep This English Product Name Unchanged"

    result = validate_response_locale(
        user_input,
        "zh-CN",
        messages=[{"role": "user", "content": user_input}],
    )

    assert result.outcome == "inconclusive"
    assert result.field_count == 0


def test_correction_may_change_natural_text_but_not_schema_or_identifiers():
    original = json.dumps(
        {
            "feature_id": "feature_1",
            "scope_status": "in_scope",
            "description": "This is an English feature description for the project.",
        }
    )
    corrected = json.dumps(
        {
            "feature_id": "feature_1",
            "scope_status": "in_scope",
            "description": "这是该项目功能的完整中文说明。",
        }
    )
    changed_id = json.dumps(
        {
            "feature_id": "feature_2",
            "scope_status": "in_scope",
            "description": "这是该项目功能的完整中文说明。",
        }
    )

    assert correction_preserves_structure(original, corrected)
    assert not correction_preserves_structure(original, changed_id)


def test_correction_preserves_user_input_and_embedded_technical_fragments():
    original = json.dumps(
        {
            "project_name": "English Product Name",
            "description": "Use `POST /api/items` and https://example.com/items for this feature.",
        }
    )
    changed_user_input = json.dumps(
        {
            "project_name": "中文产品名",
            "description": "该功能使用 `POST /api/items` 和 https://example.com/items。",
        }
    )
    changed_code = json.dumps(
        {
            "project_name": "English Product Name",
            "description": "该功能使用 `GET /api/items` 和 https://example.com/items。",
        }
    )
    messages = [{"role": "user", "content": "Project name: English Product Name"}]

    assert not correction_preserves_structure(original, changed_user_input, messages=messages)
    assert not correction_preserves_structure(original, changed_code, messages=messages)


@pytest.mark.parametrize(
    "corrected",
    [
        "请改用 https://example.com/v2/items、`POST /api/items` 和 client_id 处理 Acme API。",
        "请使用 https://example.com/items?mode=other、`POST /api/items` 和 client_id 处理 Acme API。",
        "请使用 https://example.com/items、`GET /api/items` 和 client_id 处理 Acme API。",
        "请使用 https://example.com/items、`POST /api/v2/items` 和 client_id 处理 Acme API。",
        "请使用 https://example.com/items、`POST /api/items` 和 account_id 处理 Acme API。",
        "请使用 https://example.com/items、`POST /api/items` 和 client_id 处理 Other API。",
    ],
)
def test_plain_text_correction_rejects_protected_fragment_changes(corrected):
    original = (
        "Use https://example.com/items, `POST /api/items`, and client_id "
        "when calling Acme API."
    )
    messages = [{"role": "user", "content": "Acme API"}]

    assert not correction_preserves_structure(original, corrected, messages=messages)


def test_plain_text_correction_allows_language_only_rewrite():
    original = (
        "Use https://example.com/items, `POST /api/items`, and client_id "
        "when calling Acme API."
    )
    corrected = (
        "调用 Acme API 时，请使用 https://example.com/items、`POST /api/items` 和 client_id。"
    )
    messages = [{"role": "user", "content": "Acme API"}]

    assert correction_preserves_structure(original, corrected, messages=messages)


def test_plain_text_correction_preserves_partially_referenced_protected_input():
    protected_input = "Please keep the project name English Product Name unchanged."
    original = "English Product Name is currently described using an English explanation."
    corrected = "中文产品名现在已经使用完整中文进行描述。"

    assert not correction_preserves_structure(
        original,
        corrected,
        protected_inputs=(protected_input,),
    )


@pytest.mark.parametrize("protected_name", ["微信", "音乐盒", "AI", "ERP"])
def test_plain_text_correction_preserves_explicit_short_names(protected_name):
    original = f"{protected_name} is described using an English explanation."
    corrected = "替代名称现在已经使用完整中文进行描述。"

    assert not correction_preserves_structure(
        original,
        corrected,
        protected_inputs=(protected_name,),
    )
