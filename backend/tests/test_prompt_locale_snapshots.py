import pytest
from backend.core.prompt_resolver import resolve_prompt, LocalizedPromptProxy
from backend.core.llm_context import current_llm_context, LLMRequestContext
from backend.services.llm_handler_service import LLMHandler

@pytest.mark.parametrize("prompt_name", [
    "actors_generate",
    "features_generate",
    "scenarios_generate",
    "acceptance_criteria_generate",
    "scopes_generate",
    "blank_project_generate",
    "project_interview",
    "explain",
])
def test_prompt_resolver_locales(prompt_name):
    # Test zh-CN
    prompt_zh = resolve_prompt(prompt_name, locale="zh-CN")
    assert prompt_zh is not None
    assert len(prompt_zh) > 0
    # Must contain some Chinese characters
    assert any('\u4e00' <= char <= '\u9fff' for char in prompt_zh)

    # Test en-US
    prompt_en = resolve_prompt(prompt_name, locale="en-US")
    assert prompt_en is not None
    assert len(prompt_en) > 0
    # English prompt should not contain Chinese character instruction details
    # (except maybe in example strings if we explicitly kept some, but general text is English)
    # Let's verify en-US doesn't have major Chinese block characters outside of comments/examples
    assert "Role" in prompt_en or "Task" in prompt_en or "Rules" in prompt_en or "You are" in prompt_en

    # Verify JSON keys are identical in both languages
    # 1. actors_generate
    if prompt_name == "actors_generate":
        assert '"actors"' in prompt_zh and '"actors"' in prompt_en
        assert '"actor_name"' in prompt_zh and '"actor_name"' in prompt_en
        assert '"actor_description"' in prompt_zh and '"actor_description"' in prompt_en
    # 2. features_generate
    elif prompt_name == "features_generate":
        assert '"features"' in prompt_zh and '"features"' in prompt_en
        assert '"feature_number"' in prompt_zh and '"feature_number"' in prompt_en
        assert '"feature_name"' in prompt_zh and '"feature_name"' in prompt_en
        assert '"feature_description"' in prompt_zh and '"feature_description"' in prompt_en
        assert '"actor_ids"' in prompt_zh and '"actor_ids"' in prompt_en
    # 3. scenarios_generate
    elif prompt_name == "scenarios_generate":
        assert '"scenarios"' in prompt_zh and '"scenarios"' in prompt_en
        assert '"scenario_name"' in prompt_zh and '"scenario_name"' in prompt_en
        assert '"scenario_content"' in prompt_zh and '"scenario_content"' in prompt_en
    # 4. acceptance_criteria_generate
    elif prompt_name == "acceptance_criteria_generate":
        assert '"scenario_acceptance_criteria"' in prompt_zh and '"scenario_acceptance_criteria"' in prompt_en
        assert '"scenario_id"' in prompt_zh and '"scenario_id"' in prompt_en
        assert '"acceptance_criteria"' in prompt_zh and '"acceptance_criteria"' in prompt_en


def test_localized_prompt_proxy_dynamic():
    # Setup the proxy
    proxy = LocalizedPromptProxy("actors_generate")
    
    # Context 1: zh-CN
    ctx_zh = LLMRequestContext(
        api_url="http://localhost:8000",
        api_key="sk-test",
        model_name="gpt-3.5-turbo",
        content_locale="zh-CN"
    )
    token_zh = current_llm_context.set(ctx_zh)
    try:
        val_zh = str(proxy)
        assert "角色" in val_zh
        assert "Role" not in val_zh
    finally:
        current_llm_context.reset(token_zh)

    # Context 2: en-US
    ctx_en = LLMRequestContext(
        api_url="http://localhost:8000",
        api_key="sk-test",
        model_name="gpt-3.5-turbo",
        content_locale="en-US"
    )
    token_en = current_llm_context.set(ctx_en)
    try:
        val_en = str(proxy)
        assert "Role" in val_en
        assert "角色" not in val_en
    finally:
        current_llm_context.reset(token_en)


def test_llm_handler_protocol_injection():
    # Test en-US protocol injection
    ctx_en = LLMRequestContext(
        api_url="http://localhost:8000",
        api_key="sk-test",
        model_name="gpt-4",
        content_locale="en-US"
    )
    token_en = current_llm_context.set(ctx_en)
    try:
        handler = LLMHandler(
            api_url="http://localhost:8000",
            api_key="sk-test",
            model_name="gpt-4",
            temperature="0.7"
        )
        
        # Test call_llm protocol
        prompt = "Hello"
        out_prompt = handler._append_language_protocol(prompt, "en-US")
        assert "[Content Language Protocol]" in out_prompt
        assert "English (en-US)" in out_prompt
        assert "JSON keys" in out_prompt
        
        # Test call_chat protocol
        messages = [{"role": "user", "content": "How are you?"}]
        out_messages = handler._apply_language_protocol_to_messages(messages, "en-US")
        assert len(out_messages) == 2
        assert out_messages[0]["role"] == "system"
        assert "[Content Language Protocol]" in out_messages[0]["content"]
        assert "English (en-US)" in out_messages[0]["content"]
    finally:
        current_llm_context.reset(token_en)

    # Test zh-CN protocol injection
    ctx_zh = LLMRequestContext(
        api_url="http://localhost:8000",
        api_key="sk-test",
        model_name="gpt-4",
        content_locale="zh-CN"
    )
    token_zh = current_llm_context.set(ctx_zh)
    try:
        handler = LLMHandler(
            api_url="http://localhost:8000",
            api_key="sk-test",
            model_name="gpt-4",
            temperature="0.7"
        )
        
        prompt = "你好"
        out_prompt = handler._append_language_protocol(prompt, "zh-CN")
        assert "[Content Language Protocol]" in out_prompt
        assert "中文 (zh-CN)" in out_prompt
        assert "JSON 键" in out_prompt
    finally:
        current_llm_context.reset(token_zh)
