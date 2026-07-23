from pathlib import Path
from typing import Optional, cast

from backend.core.llm_context import current_llm_context
from backend.core.locale import DEFAULT_LOCALE, SUPPORTED_LOCALES, SupportedLocale

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

def get_content_locale() -> SupportedLocale:
    """Get the active supported content locale."""
    ctx = current_llm_context.get()
    locale = ctx.content_locale if ctx else None
    return cast(
        SupportedLocale,
        locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE.value,
    )

def resolve_prompt(name: str, locale: Optional[str] = None) -> str:
    """Resolve a prompt without silently crossing supported languages."""
    if locale is None:
        locale = get_content_locale()
    elif locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE.value
    matches = list((PROMPTS_DIR / locale).rglob(f"{name}.txt"))
    if not matches:
        raise FileNotFoundError(
            f"Prompt template '{name}' not found for locale '{locale}'."
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Prompt template '{name}' is ambiguous for locale '{locale}'."
        )
    return matches[0].read_text(encoding="utf-8").strip()


class LocalizedPromptProxy(str):
    """A proxy class that behaves like a string but resolves its value
    dynamically at runtime based on the current context's locale.
    """
    def __new__(cls, name: str):
        # Initialize base str as empty, we override all retrieval methods
        obj = super().__new__(cls, "")
        obj._prompt_name = name
        return obj

    def _resolve(self) -> str:
        return resolve_prompt(self._prompt_name)

    def replace(self, old: str, new: str, count: int = -1) -> str:
        return self._resolve().replace(old, new, count)

    def format(self, *args, **kwargs) -> str:
        return self._resolve().format(*args, **kwargs)

    def strip(self, chars: Optional[str] = None) -> str:
        return self._resolve().strip(chars)

    def split(self, sep: Optional[str] = None, maxsplit: int = -1) -> list[str]:
        return self._resolve().split(sep, maxsplit)

    def startswith(self, prefix, start=0, end=None) -> bool:
        return self._resolve().startswith(prefix, start, end)

    def endswith(self, suffix, start=0, end=None) -> bool:
        return self._resolve().endswith(suffix, start, end)

    def __add__(self, other: str) -> str:
        return self._resolve() + other

    def __radd__(self, other: str) -> str:
        return other + self._resolve()

    def __str__(self) -> str:
        return self._resolve()

    def __repr__(self) -> str:
        return repr(self._resolve())

    def __len__(self) -> int:
        return len(self._resolve())

    def __bool__(self) -> bool:
        return bool(self._resolve())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LocalizedPromptProxy):
            return self._resolve() == other._resolve()
        return self._resolve() == other

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, str):
            return False
        return item in self._resolve()

    def __hash__(self) -> int:
        return hash(self._resolve())

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)
