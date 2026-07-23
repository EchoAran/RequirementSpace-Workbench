import enum
from typing import Literal, Set, TypeAlias, cast

SupportedLocale: TypeAlias = Literal["zh-CN", "en-US"]
ContentLocaleSource: TypeAlias = Literal["project", "user", "default"]

class LocaleCode(str, enum.Enum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"

DEFAULT_LOCALE = LocaleCode.ZH_CN

SUPPORTED_LOCALES: Set[str] = {locale.value for locale in LocaleCode}

LOCALE_DISPLAY_NAMES = {
    LocaleCode.ZH_CN: "简体中文",
    LocaleCode.EN_US: "English (US)",
}

def is_valid_locale(locale: str | None) -> bool:
    if locale is None:
        return False
    return locale in SUPPORTED_LOCALES


def resolve_effective_locale(
    project_locale: str | None,
    user_locale: str | None,
) -> tuple[SupportedLocale, ContentLocaleSource]:
    if is_valid_locale(project_locale):
        return cast(SupportedLocale, project_locale), "project"
    if is_valid_locale(user_locale):
        return cast(SupportedLocale, user_locale), "user"
    return DEFAULT_LOCALE.value, "default"
