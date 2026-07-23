import asyncio
import os
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse
import time
import traceback

import httpx
from dotenv import load_dotenv

from backend.core.llm_context import (
    current_llm_context,
    is_web_request_ctx,
    LLMContextMissingError,
    LLMConfigError,
)
from backend.core.ai_operation_monitor import monitor_ai_operation
from backend.core import config as core_config
from backend.core.llm_locale_validation import (
    LLMContentLocaleMismatchError,
    correction_preserves_structure,
    validate_response_locale,
)
from backend.core.llm_language_protocol import (
    CONTENT_LANGUAGE_PROTOCOL_MARKER,
    append_language_protocol,
    apply_language_protocol_to_messages,
    language_protocol,
    remove_language_protocol,
)
from backend.core.locale import DEFAULT_LOCALE
from backend.core.logging import (
    category_enabled,
    get_logger,
    log_event,
    preview_text,
    sanitize_message,
)
from backend.core.logging.events import (
    LLM_API_CALL_ALL_ATTEMPTS_FAILED,
    LLM_API_CALL_ATTEMPT,
    LLM_API_CALL_COMPLETED,
    LLM_API_CALL_FAILED,
    LLM_PROMPT_SAMPLE,
    LLM_LOCALE_CORRECTION_REQUESTED,
    LLM_LOCALE_CORRECTION_COMPLETED,
    LLM_LOCALE_VALIDATION_COMPLETED,
    LLM_LOCALE_VALIDATION_REJECTED,
    LLM_RESPONSE_INVALID,
    LLM_RESPONSE_SAMPLE,
    LLM_RETRY_SCHEDULED,
)

import logging

logger = get_logger(__name__)
LLM_CONTENT_PREVIEW_CHARS = 200


class LLMCallFailedError(RuntimeError):
    pass


def load_llm_config() -> dict[str, str] | None:
    """Load LLM configuration from backend .env."""

    root_dir = Path(__file__).resolve().parents[2]
    env_path = root_dir / ".env"
    load_dotenv(dotenv_path=env_path)

    config = {
        "api_url": os.getenv("LLM_API_URL", "").strip(),
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
        "model_name": os.getenv("LLM_MODEL_NAME", "").strip(),
        "temperature": os.getenv("LLM_TEMPERATURE", "").strip(),
    }

    if any(not value for value in config.values()):
        return None

    return config


class LLMHandler:
    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: str | None = None,
    ):
        self._explicit_api_url = api_url
        self._explicit_api_key = api_key
        self._explicit_model_name = model_name

        config = load_llm_config() or {}
        self.temperature = temperature or config.get("temperature") or ""

    @property
    def api_url(self) -> str:
        ctx = current_llm_context.get()
        if ctx is not None:
            return ctx.api_url.rstrip("/")

        if self._explicit_api_url is not None:
            return self._explicit_api_url.rstrip("/")

        if is_web_request_ctx.get():
            raise LLMContextMissingError("LLMRequestContext is missing in Web request")

        config = load_llm_config() or {}
        return (config.get("api_url") or "").rstrip("/")

    @property
    def api_key(self) -> str:
        ctx = current_llm_context.get()
        if ctx is not None:
            return ctx.api_key

        if self._explicit_api_key is not None:
            return self._explicit_api_key

        if is_web_request_ctx.get():
            raise LLMContextMissingError("LLMRequestContext is missing in Web request")

        config = load_llm_config() or {}
        return config.get("api_key") or ""

    @property
    def model_name(self) -> str:
        ctx = current_llm_context.get()
        if ctx is not None:
            return ctx.model_name

        if self._explicit_model_name is not None:
            return self._explicit_model_name

        if is_web_request_ctx.get():
            raise LLMContextMissingError("LLMRequestContext is missing in Web request")

        config = load_llm_config() or {}
        return config.get("model_name") or ""

    @property
    def content_locale(self) -> str:
        ctx = current_llm_context.get()
        if ctx is not None:
            return ctx.content_locale
        return DEFAULT_LOCALE.value

    @property
    def content_locale_source(self) -> str:
        ctx = current_llm_context.get()
        if ctx is not None:
            return ctx.content_locale_source
        return "default"

    def _append_language_protocol(self, prompt: str, locale: str) -> str:
        return append_language_protocol(prompt, locale)

    @staticmethod
    def _remove_language_protocol(content: str) -> str:
        return remove_language_protocol(content)

    @staticmethod
    def _language_protocol(locale: str) -> str:
        return language_protocol(locale)

    def _apply_language_protocol_to_messages(self, messages: list[dict], locale: str) -> list[dict]:
        return apply_language_protocol_to_messages(messages, locale)

    def _validate_settings(self) -> bool:
        required_fields = [
            self.api_url,
            self.api_key,
            self.model_name,
            self.temperature,
        ]
        return all(field and str(field).strip() for field in required_fields)

    @staticmethod
    def _log(enabled: bool, message: str) -> None:
        if enabled and category_enabled("llm_content"):
            log_event(
                logger,
                logging.INFO,
                "llm_content",
                LLM_PROMPT_SAMPLE,
                "LLM content diagnostic",
                content_preview=preview_text(message, LLM_CONTENT_PREVIEW_CHARS),
                truncated=len(sanitize_message(message)) > LLM_CONTENT_PREVIEW_CHARS,
                preview_chars=LLM_CONTENT_PREVIEW_CHARS,
            )

    def _build_request_data(self, prompt: str, query: str) -> dict:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ]

        return {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(self.temperature),
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def call_llm(
        self,
        prompt: str,
        query: str | None = "",
        print_log: bool = True,
        response_format: dict | None = None,
        protected_inputs: Iterable[str] = (),
        raise_on_failure: bool = False,
        timeout_seconds: float = 100.0,
    ) -> Optional[str]:
        query = query or ""
        locale = self.content_locale
        prompt = self._append_language_protocol(prompt, locale)
        query = self._remove_language_protocol(query)

        if not self._validate_settings():
            raise LLMConfigError("The LLM settings are incomplete. Please ensure LLM_API_URL, LLM_API_KEY, LLM_MODEL_NAME, and LLM_TEMPERATURE are set correctly.")

        try:
            request_data = self._build_request_data(prompt, query)
        except ValueError as exc:
            self._log(print_log, f"Invalid LLM temperature value: {self.temperature} \n{exc}")
            if raise_on_failure:
                raise LLMCallFailedError("Invalid LLM temperature value") from exc
            return None

        if response_format is not None:
            request_data["response_format"] = response_format

        content = await self._call_api(
            request_data=request_data,
            print_log=print_log,
            prompt_label=prompt,
            query_label=query,
            raise_on_failure=raise_on_failure,
            timeout_seconds=timeout_seconds,
        )
        return await self._validate_or_correct_locale(
            content,
            request_data=request_data,
            expected_locale=locale,
            structured_response=response_format is not None,
            protected_inputs=tuple(protected_inputs),
            call_type="call_llm",
            timeout_seconds=timeout_seconds,
        )

    async def call_chat(
        self,
        messages: list[dict],
        print_log: bool = True,
        response_format: dict | None = None,
        protected_inputs: Iterable[str] = (),
    ) -> Optional[str]:
        """
        Multi-turn chat LLM call.
        Accepts a full list of messages (system + user + assistant history)
        instead of the single prompt+query pattern used by call_llm.

        Designed for InterviewStrategy where conversation history needs to be preserved.
        """
        if not self._validate_settings():
            raise LLMConfigError("The LLM settings are incomplete. Please ensure LLM_API_URL, LLM_API_KEY, LLM_MODEL_NAME, and LLM_TEMPERATURE are set correctly.")

        locale = self.content_locale
        messages = self._apply_language_protocol_to_messages(messages, locale)

        request_data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(self.temperature),
        }

        if response_format is not None:
            request_data["response_format"] = response_format

        content = await self._call_api(
            request_data=request_data,
            print_log=print_log,
            prompt_label=messages[0]["content"] if messages else "",
            query_label=messages[-1]["content"] if messages else "",
        )
        return await self._validate_or_correct_locale(
            content,
            request_data=request_data,
            expected_locale=locale,
            structured_response=response_format is not None,
            protected_inputs=tuple(protected_inputs),
            call_type="call_chat",
            timeout_seconds=100.0,
        )

    async def _validate_or_correct_locale(
        self,
        content: str | None,
        *,
        request_data: dict,
        expected_locale: str,
        structured_response: bool,
        protected_inputs: tuple[str, ...],
        call_type: str,
        timeout_seconds: float,
    ) -> str | None:
        if content is None:
            return None

        messages = request_data.get("messages") or []
        validation_mode = core_config.LLM_LOCALE_VALIDATION_MODE
        locale_source = self.content_locale_source
        initial = self._validate_locale_attempt(
            content,
            expected_locale=expected_locale,
            messages=messages,
            structured_response=structured_response,
            protected_inputs=protected_inputs,
            call_type=call_type,
            locale_source=locale_source,
            validation_mode=validation_mode,
            attempt=1,
        )
        if initial.outcome != "mismatch":
            return content
        if validation_mode == "observe":
            return content

        log_event(
            logger,
            logging.INFO,
            "llm",
            LLM_LOCALE_CORRECTION_REQUESTED,
            "LLM locale correction requested",
            attempt=2,
            expected_locale=expected_locale,
            detector_outcome=initial.outcome,
            field_count=initial.field_count,
            call_type=call_type,
            content_locale_source=locale_source,
            validation_mode=validation_mode,
            model=self.model_name,
        )
        correction_request = dict(request_data)
        correction_request["messages"] = [
            *[dict(message) for message in messages],
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": self._locale_correction_instruction(expected_locale),
            },
        ]
        correction_started = time.perf_counter()
        corrected = await self._call_api(
            request_data=correction_request,
            print_log=False,
            prompt_label="",
            query_label="",
            timeout_seconds=timeout_seconds,
        )
        correction_duration_ms = int(
            (time.perf_counter() - correction_started) * 1000
        )
        corrected_result = self._validate_locale_attempt(
            corrected or "",
            expected_locale=expected_locale,
            messages=messages,
            structured_response=structured_response,
            protected_inputs=protected_inputs,
            call_type=call_type,
            locale_source=locale_source,
            validation_mode=validation_mode,
            attempt=2,
        )
        structure_preserved = corrected is not None and correction_preserves_structure(
            content,
            corrected,
            messages=messages,
            protected_inputs=protected_inputs,
        )
        correction_succeeded = (
            corrected_result.outcome == "match" and structure_preserved
        )
        log_event(
            logger,
            logging.INFO if correction_succeeded else logging.WARNING,
            "llm",
            LLM_LOCALE_CORRECTION_COMPLETED,
            "LLM locale correction completed",
            attempt=2,
            expected_locale=expected_locale,
            detector_outcome=corrected_result.outcome,
            field_count=corrected_result.field_count,
            structure_preserved=structure_preserved,
            correction_succeeded=correction_succeeded,
            correction_duration_ms=correction_duration_ms,
            correction_request_count=1,
            call_type=call_type,
            content_locale_source=locale_source,
            validation_mode=validation_mode,
            model=self.model_name,
        )
        if correction_succeeded:
            return corrected

        log_event(
            logger,
            logging.ERROR,
            "llm",
            LLM_LOCALE_VALIDATION_REJECTED,
            "LLM response rejected after locale correction",
            attempt=2,
            expected_locale=expected_locale,
            detector_outcome=corrected_result.outcome,
            field_count=corrected_result.field_count,
            structure_preserved=structure_preserved,
            call_type=call_type,
            content_locale_source=locale_source,
            validation_mode=validation_mode,
            model=self.model_name,
        )
        raise LLMContentLocaleMismatchError()

    @staticmethod
    def _validate_locale_attempt(
        content: str,
        *,
        expected_locale: str,
        messages: list[dict],
        structured_response: bool,
        protected_inputs: tuple[str, ...],
        call_type: str,
        locale_source: str,
        validation_mode: str,
        attempt: int,
    ):
        started = time.perf_counter()
        result = validate_response_locale(
            content,
            expected_locale,
            messages=messages,
            protected_inputs=protected_inputs,
            structured_response=structured_response,
        )
        log_event(
            logger,
            logging.INFO,
            "llm",
            LLM_LOCALE_VALIDATION_COMPLETED,
            "LLM locale validation completed",
            attempt=attempt,
            expected_locale=expected_locale,
            detector_outcome=result.outcome,
            field_count=result.field_count,
            cjk_count=result.cjk_count,
            latin_count=result.latin_count,
            cjk_ratio=round(result.cjk_ratio, 4),
            duration_ms=int((time.perf_counter() - started) * 1000),
            call_type=call_type,
            content_locale_source=locale_source,
            validation_mode=validation_mode,
        )
        return result

    @staticmethod
    def _locale_correction_instruction(locale: str) -> str:
        if locale == "en-US":
            return (
                "Rewrite only the user-visible natural-language values that do not comply with en-US, "
                "then return the complete response. Preserve the original JSON schema, key order, enum "
                "values, IDs, object relationships, user-provided text, URLs, code, and technical identifiers exactly."
            )
        return (
            "仅将不符合 zh-CN 的用户可见自然语言值改写为中文，然后返回完整响应。"
            "必须原样保留 JSON schema、键顺序、枚举值、ID、对象关系、用户原始输入、URL、代码和技术标识。"
        )

    async def _call_api(
        self,
        request_data: dict,
        print_log: bool,
        prompt_label: str,
        query_label: str,
        raise_on_failure: bool = False,
        timeout_seconds: float = 100.0,
    ) -> Optional[str]:
        """Shared HTTP call + retry logic for call_llm and call_chat."""
        attempts = 3
        base_delay = 0.8
        last_error_text: str | None = None

        headers = self._build_headers()
        url = f"{self.api_url}/v1/chat/completions"
        host = urlparse(self.api_url).hostname or self.api_url
        model = request_data.get("model")
        messages = request_data.get("messages")
        message_count = len(messages) if isinstance(messages, list) else None
        has_response_format = "response_format" in request_data

        for attempt in range(1, attempts + 1):
            self._log_prompt_sample(
                print_log=print_log,
                prompt_label=prompt_label,
                query_label=query_label,
            )

            log_event(
                logger,
                logging.INFO,
                "llm",
                LLM_API_CALL_ATTEMPT,
                "LLM API call attempt started",
                provider_host=host,
                model=model,
                attempt=attempt,
                attempts=attempts,
                timeout_seconds=timeout_seconds,
                has_response_format=has_response_format,
                message_count=message_count,
            )
            start_time = time.perf_counter()

            try:
                with monitor_ai_operation("llm_api_call", attempt=attempt):
                    timeout = httpx.Timeout(
                        connect=10.0,
                        read=timeout_seconds,
                        write=30.0,
                        pool=10.0,
                    )
                    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                        response = await client.post(url, json=request_data, headers=headers)

                duration_ms = int((time.perf_counter() - start_time) * 1000)

                if response.status_code != 200:
                    last_error_text = f"API call failed: status_code={response.status_code}"
                    log_event(
                        logger,
                        logging.ERROR,
                        "llm",
                        LLM_API_CALL_FAILED,
                        "LLM API call failed",
                        provider_host=host,
                        model=model,
                        attempt=attempt,
                        attempts=attempts,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        response_chars=len(response.text),
                        error_type="http_status",
                        has_response_format=has_response_format,
                        message_count=message_count,
                    )
                    await self._sleep_before_retry(
                        attempt,
                        attempts,
                        base_delay,
                        provider_host=host,
                        model=model,
                    )
                    continue

                result = response.json()
                content = self._extract_content(result)

                if content is None:
                    last_error_text = "LLM response format exception (invalid structure)"
                    provider_request_id = response.headers.get("x-request-id") or None
                    invalid_fields: dict[str, object] = {
                        "provider_host": host,
                        "model": model,
                        "attempt": attempt,
                        "attempts": attempts,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "response_chars": len(response.text),
                        "error_type": "invalid_response_structure",
                        "has_response_format": has_response_format,
                        "message_count": message_count,
                    }
                    if provider_request_id:
                        invalid_fields["provider_request_id"] = provider_request_id
                    log_event(
                        logger,
                        logging.ERROR,
                        "llm",
                        LLM_RESPONSE_INVALID,
                        "LLM response returned invalid structure",
                        **invalid_fields,
                    )
                    await self._sleep_before_retry(
                        attempt,
                        attempts,
                        base_delay,
                        provider_host=host,
                        model=model,
                    )
                    continue

                self._log_response_sample(print_log=print_log, content=content)
                completed_fields: dict[str, object] = {
                    "provider_host": host,
                    "model": model,
                    "attempt": attempt,
                    "attempts": attempts,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "response_chars": len(content),
                    "has_response_format": has_response_format,
                    "message_count": message_count,
                }
                provider_request_id = response.headers.get("x-request-id") or None
                if provider_request_id:
                    completed_fields["provider_request_id"] = provider_request_id
                log_event(
                    logger,
                    logging.INFO,
                    "llm",
                    LLM_API_CALL_COMPLETED,
                    "LLM API call completed",
                    **completed_fields,
                )

                return content

            except httpx.ConnectError as exc:
                last_error_text = sanitize_message(str(exc)) or type(exc).__name__
                self._log_llm_exception(
                    event=LLM_API_CALL_FAILED,
                    message="LLM API connection failed",
                    host=host,
                    model=model,
                    attempt=attempt,
                    attempts=attempts,
                    started=start_time,
                    error_type=type(exc).__name__,
                    error_message=last_error_text,
                    has_response_format=has_response_format,
                    message_count=message_count,
                )

            except httpx.TimeoutException as exc:
                last_error_text = sanitize_message(str(exc)) or type(exc).__name__
                self._log_llm_exception(
                    event=LLM_API_CALL_FAILED,
                    message="LLM API request timed out",
                    host=host,
                    model=model,
                    attempt=attempt,
                    attempts=attempts,
                    started=start_time,
                    error_type=type(exc).__name__,
                    error_message=last_error_text,
                    has_response_format=has_response_format,
                    message_count=message_count,
                )

            except Exception as exc:
                last_error_text = sanitize_message(f"{exc} ({type(exc).__name__})")
                tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                sanitized_tb = sanitize_message(tb_str)
                self._log_llm_exception(
                    event=LLM_API_CALL_FAILED,
                    message="Unexpected error during LLM API call",
                    host=host,
                    model=model,
                    attempt=attempt,
                    attempts=attempts,
                    started=start_time,
                    error_type=type(exc).__name__,
                    error_message=last_error_text,
                    has_response_format=has_response_format,
                    message_count=message_count,
                    sanitized_traceback=sanitized_tb,
                )

            await self._sleep_before_retry(
                attempt,
                attempts,
                base_delay,
                provider_host=host,
                model=model,
            )

        log_event(
            logger,
            logging.ERROR,
            "llm",
            LLM_API_CALL_ALL_ATTEMPTS_FAILED,
            "All LLM API call attempts failed",
            provider_host=host,
            model=model,
            attempts=attempts,
            error_type="all_attempts_failed",
            error_message=last_error_text,
            has_response_format=has_response_format,
            message_count=message_count,
        )
        if raise_on_failure:
            raise LLMCallFailedError(last_error_text or "LLM API call failed")
        return None

    @staticmethod
    def _extract_content(result: dict) -> str | None:
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

        if not isinstance(content, str):
            return None

        content = content.strip()
        return content or None

    @staticmethod
    async def _sleep_before_retry(
        attempt: int,
        attempts: int,
        base_delay: float,
        *,
        provider_host: str | None = None,
        model: object | None = None,
    ) -> None:
        if attempt >= attempts:
            return

        delay = base_delay * (2 ** (attempt - 1))
        log_event(
            logger,
            logging.INFO,
            "llm",
            LLM_RETRY_SCHEDULED,
            "LLM API retry scheduled",
            provider_host=provider_host,
            model=model,
            attempt=attempt,
            attempts=attempts,
            retry_delay_seconds=delay,
        )
        await asyncio.sleep(delay)

    @staticmethod
    def _log_prompt_sample(
        *,
        print_log: bool,
        prompt_label: str,
        query_label: str,
    ) -> None:
        if not print_log or not category_enabled("llm_content"):
            return

        prompt_preview = preview_text(prompt_label, LLM_CONTENT_PREVIEW_CHARS)
        query_preview = preview_text(query_label, LLM_CONTENT_PREVIEW_CHARS) if query_label.strip() else ""
        log_event(
            logger,
            logging.INFO,
            "llm_content",
            LLM_PROMPT_SAMPLE,
            "LLM prompt/query preview",
            prompt_preview=prompt_preview,
            query_preview=query_preview,
            truncated=(
                len(sanitize_message(prompt_label)) > LLM_CONTENT_PREVIEW_CHARS
                or len(sanitize_message(query_label)) > LLM_CONTENT_PREVIEW_CHARS
            ),
            preview_chars=LLM_CONTENT_PREVIEW_CHARS,
        )

    @staticmethod
    def _log_response_sample(*, print_log: bool, content: str) -> None:
        if not print_log or not category_enabled("llm_content"):
            return

        log_event(
            logger,
            logging.INFO,
            "llm_content",
            LLM_RESPONSE_SAMPLE,
            "LLM response preview",
            response_preview=preview_text(content, LLM_CONTENT_PREVIEW_CHARS),
            truncated=len(sanitize_message(content)) > LLM_CONTENT_PREVIEW_CHARS,
            preview_chars=LLM_CONTENT_PREVIEW_CHARS,
        )

    @staticmethod
    def _log_llm_exception(
        *,
        event: str,
        message: str,
        host: str,
        model: object,
        attempt: int,
        attempts: int,
        started: float,
        error_type: str,
        error_message: str,
        has_response_format: bool,
        message_count: int | None,
        sanitized_traceback: str | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "provider_host": host,
            "model": model,
            "attempt": attempt,
            "attempts": attempts,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error_type": error_type,
            "error_message": error_message,
            "has_response_format": has_response_format,
            "message_count": message_count,
        }
        if sanitized_traceback:
            fields["sanitized_traceback"] = sanitized_traceback

        log_event(
            logger,
            logging.ERROR,
            "llm",
            event,
            message,
            **fields,
        )
