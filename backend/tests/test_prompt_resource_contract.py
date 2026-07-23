import re

import pytest

from backend.core.prompt_resolver import PROMPTS_DIR, resolve_prompt


PLACEHOLDER_PATTERN = re.compile(r"\{+([A-Za-z_][A-Za-z0-9_]*)\}+")


def _prompt_files(locale: str) -> dict[str, str]:
    return {
        str(path.relative_to(PROMPTS_DIR / locale)): path.read_text(encoding="utf-8")
        for path in (PROMPTS_DIR / locale).rglob("*.txt")
    }


def test_supported_prompt_resources_have_matching_files_and_placeholders():
    zh_prompts = _prompt_files("zh-CN")
    en_prompts = _prompt_files("en-US")

    assert en_prompts.keys() == zh_prompts.keys()
    for name, zh_prompt in zh_prompts.items():
        assert en_prompts[name].strip()
        assert set(PLACEHOLDER_PATTERN.findall(en_prompts[name])) == set(
            PLACEHOLDER_PATTERN.findall(zh_prompt)
        ), name


def test_english_prompt_resources_do_not_contain_cjk_instructions():
    for name, prompt in _prompt_files("en-US").items():
        assert not re.search(r"[\u4e00-\u9fff]", prompt), name


def test_supported_locale_does_not_fall_back_to_another_language():
    with pytest.raises(FileNotFoundError, match="en-US"):
        resolve_prompt("missing_prompt", locale="en-US")


def test_scenario_prompt_caps_output_per_feature_actor_pair():
    assert "不得超过 5" in resolve_prompt("generation/scenarios_generate", locale="zh-CN")
    assert "never exceed 5" in resolve_prompt("generation/scenarios_generate", locale="en-US")
