import pytest
from backend.core.locale import (
    DEFAULT_LOCALE,
    LOCALE_DISPLAY_NAMES,
    SUPPORTED_LOCALES,
    LocaleCode,
    is_valid_locale,
    resolve_effective_locale,
)

def test_locale_constants():
    assert DEFAULT_LOCALE == LocaleCode.ZH_CN
    assert "zh-CN" in SUPPORTED_LOCALES
    assert "en-US" in SUPPORTED_LOCALES
    assert len(SUPPORTED_LOCALES) == 2
    
    assert LOCALE_DISPLAY_NAMES[LocaleCode.ZH_CN] == "简体中文"
    assert LOCALE_DISPLAY_NAMES[LocaleCode.EN_US] == "English (US)"

def test_is_valid_locale():
    assert is_valid_locale("zh-CN") is True
    assert is_valid_locale("en-US") is True
    
    assert is_valid_locale("zh") is False
    assert is_valid_locale("en") is False
    assert is_valid_locale("auto") is False
    assert is_valid_locale("") is False
    assert is_valid_locale(None) is False


def test_resolve_effective_locale_priority_and_validation():
    assert resolve_effective_locale("en-US", "zh-CN") == ("en-US", "project")
    assert resolve_effective_locale(None, "en-US") == ("en-US", "user")
    assert resolve_effective_locale("invalid", "invalid") == ("zh-CN", "default")
