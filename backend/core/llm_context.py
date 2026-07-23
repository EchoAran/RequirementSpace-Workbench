from contextvars import ContextVar
from typing import Optional
from dataclasses import dataclass

from backend.core.locale import ContentLocaleSource, DEFAULT_LOCALE, SupportedLocale

@dataclass
class LLMRequestContext:
    api_url: str
    api_key: str
    model_name: str
    content_locale: SupportedLocale = DEFAULT_LOCALE.value
    content_locale_source: ContentLocaleSource = "default"

current_llm_context: ContextVar[Optional[LLMRequestContext]] = ContextVar("current_llm_context", default=None)
is_web_request_ctx: ContextVar[bool] = ContextVar("is_web_request", default=False)

class LLMContextMissingError(RuntimeError):
    """Raised when LLMRequestContext is missing within a web request lifecycle."""
    pass

class LLMConfigError(ValueError):
    """Raised when LLM configuration properties are incomplete or invalid."""
    pass
