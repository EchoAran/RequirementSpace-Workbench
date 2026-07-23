from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import re
from typing import Iterable, Literal


LocaleValidationOutcome = Literal["match", "mismatch", "inconclusive"]

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_URL_RE = re.compile(
    r"https?://[^\s`<>]+|www\.[^\s`<>]+",
    re.IGNORECASE,
)
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_CODE_LINE_RE = re.compile(
    r"(?m)^(?:\s{4,}|\s*(?:class|const|def|from|function|import|let|var)\b).+$"
)
_API_PATH_RE = re.compile(r"(?<!\w)/(?:[A-Za-z0-9._{}:-]+/)+[A-Za-z0-9._{}:-]*")
_TECHNICAL_TOKEN_RE = re.compile(
    r"\b(?:[A-Za-z]+_)+[A-Za-z0-9_]+\b|"
    r"\b[A-Fa-f0-9]{8,}\b|"
    r"\b[A-Za-z]+(?:\.[A-Za-z0-9_-]+)+\b"
)
_PURE_NUMBER_RE = re.compile(r"^[\s\d.,:+\-/%()]+$")

_NATURAL_TOKENS = {
    "and",
    "answer",
    "as",
    "assumption",
    "background",
    "benefit",
    "change",
    "content",
    "criterion",
    "criteria",
    "description",
    "detail",
    "explanation",
    "feature",
    "goal",
    "gherkin",
    "given",
    "impact",
    "instruction",
    "label",
    "message",
    "name",
    "narrative",
    "objective",
    "outcome",
    "page",
    "question",
    "rationale",
    "reason",
    "recommendation",
    "reply",
    "response",
    "rule",
    "scenario",
    "step",
    "story",
    "suggestion",
    "summary",
    "system",
    "task",
    "text",
    "then",
    "title",
    "warning",
    "want",
    "when",
}
_TECHNICAL_TOKENS = {
    "category",
    "code",
    "count",
    "enum",
    "file",
    "format",
    "html",
    "id",
    "ids",
    "index",
    "javascript",
    "key",
    "kind",
    "language",
    "locale",
    "mode",
    "model",
    "number",
    "path",
    "position",
    "role",
    "schema",
    "status",
    "style",
    "type",
    "uri",
    "url",
    "version",
}
_NATURAL_KEY_OVERRIDES = {
    "status_detail",
    "positive_summary",
    "negative_summary",
    "reason_summary",
}


class LLMContentLocaleMismatchError(ValueError):
    code = "llm_content_locale_mismatch"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True)
class LocaleValidationResult:
    outcome: LocaleValidationOutcome
    expected_locale: str
    field_count: int
    cjk_count: int
    latin_count: int

    @property
    def cjk_ratio(self) -> float:
        total = self.cjk_count + self.latin_count
        return self.cjk_count / total if total else 0.0


def _key_tokens(key: str) -> set[str]:
    snake_key = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
    return {token for token in re.split(r"[^a-z]+", snake_key) if token}


def is_natural_language_key(key: str) -> bool:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
    if normalized in _NATURAL_KEY_OVERRIDES:
        return True

    tokens = _key_tokens(key)
    if tokens & _TECHNICAL_TOKENS:
        return False
    return bool(tokens & _NATURAL_TOKENS) or bool(re.search(r"\s|[\u4e00-\u9fff]", key))


def _is_user_input(value: str, user_inputs: Iterable[str]) -> bool:
    stripped = value.strip()
    return bool(stripped) and any(stripped in item for item in user_inputs)


def _is_inspectable_text(value: str) -> bool:
    stripped = value.strip()
    if not stripped or _PURE_NUMBER_RE.fullmatch(stripped):
        return False
    if _URL_RE.fullmatch(stripped):
        return False
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:/#-]*", stripped) and (
        "_" in stripped or "/" in stripped or ":" in stripped or "." in stripped
    ):
        return False
    return True


def extract_natural_language_fields(
    payload: object,
    *,
    user_inputs: Iterable[str] = (),
) -> list[str]:
    fields: list[str] = []
    source_inputs = tuple(user_inputs)

    def visit(value: object, inspect_strings: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(key, str):
                    visit(child, is_natural_language_key(key))
            return
        if isinstance(value, list):
            for child in value:
                visit(child, inspect_strings)
            return
        if (
            inspect_strings
            and isinstance(value, str)
            and _is_inspectable_text(value)
            and not _is_user_input(value, source_inputs)
        ):
            fields.append(value)

    visit(payload)
    return fields


def detect_content_locale(
    fields: Iterable[str],
    expected_locale: str,
) -> LocaleValidationResult:
    field_list = list(fields)
    inspectable_text = "\n".join(field_list)
    inspectable_text = _FENCED_CODE_RE.sub("", inspectable_text)
    inspectable_text = _INLINE_CODE_RE.sub("", inspectable_text)
    inspectable_text = _URL_RE.sub("", inspectable_text)
    inspectable_text = _TECHNICAL_TOKEN_RE.sub("", inspectable_text)

    cjk_count = len(_CJK_RE.findall(inspectable_text))
    latin_count = len(_LATIN_RE.findall(inspectable_text))
    total = cjk_count + latin_count

    if total < 10:
        outcome: LocaleValidationOutcome = "inconclusive"
    elif expected_locale == "en-US":
        outcome = "mismatch" if cjk_count / total > 0.10 else "match"
    else:
        outcome = "mismatch" if cjk_count == 0 else "match"

    return LocaleValidationResult(
        outcome=outcome,
        expected_locale=expected_locale,
        field_count=len(field_list),
        cjk_count=cjk_count,
        latin_count=latin_count,
    )


def validate_response_locale(
    content: str,
    expected_locale: str,
    *,
    messages: Iterable[dict] = (),
    protected_inputs: Iterable[str] = (),
    structured_response: bool = False,
) -> LocaleValidationResult:
    explicit_inputs = tuple(
        value for value in protected_inputs if isinstance(value, str)
    )
    user_inputs = _protected_inputs(messages, explicit_inputs)

    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        inspectable_content = content
        for fragment in _referenced_input_fragments(
            content,
            user_inputs,
            short_inputs=explicit_inputs,
        ):
            inspectable_content = inspectable_content.replace(fragment, "")
        fields = (
            []
            if structured_response or not inspectable_content.strip()
            else [inspectable_content]
        )
    else:
        fields = extract_natural_language_fields(payload, user_inputs=user_inputs)

    return detect_content_locale(fields, expected_locale)


def correction_preserves_structure(
    original_content: str,
    corrected_content: str,
    *,
    messages: Iterable[dict] = (),
    protected_inputs: Iterable[str] = (),
) -> bool:
    explicit_inputs = tuple(
        value for value in protected_inputs if isinstance(value, str)
    )
    user_inputs = _protected_inputs(messages, explicit_inputs)

    try:
        original = json.loads(original_content)
    except (json.JSONDecodeError, TypeError):
        original_is_json = False
        original = None
    else:
        original_is_json = True

    try:
        corrected = json.loads(corrected_content)
    except (json.JSONDecodeError, TypeError):
        corrected_is_json = False
        corrected = None
    else:
        corrected_is_json = True

    if original_is_json != corrected_is_json:
        return False
    if not original_is_json:
        referenced_user_inputs = _referenced_input_fragments(
            original_content,
            user_inputs,
            short_inputs=explicit_inputs,
        )
        return (
            _protected_fragments(original_content)
            == _protected_fragments(corrected_content)
            and all(value in corrected_content for value in referenced_user_inputs)
        )

    def preserved(before: object, after: object, natural: bool = False) -> bool:
        if type(before) is not type(after):
            return False
        if isinstance(before, dict):
            if list(before) != list(after):
                return False
            return all(
                preserved(value, after[key], is_natural_language_key(str(key)))
                for key, value in before.items()
            )
        if isinstance(before, list):
            return len(before) == len(after) and all(
                preserved(left, right, natural)
                for left, right in zip(before, after)
            )
        if isinstance(before, str) and natural and not _is_user_input(before, user_inputs):
            return _protected_fragments(before) == _protected_fragments(after)
        return before == after

    return preserved(original, corrected)


def _protected_fragments(value: str) -> tuple[str, ...]:
    fragments: list[str] = []
    for pattern in (
        _FENCED_CODE_RE,
        _INLINE_CODE_RE,
        _CODE_LINE_RE,
        _URL_RE,
        _API_PATH_RE,
        _TECHNICAL_TOKEN_RE,
    ):
        matches = pattern.findall(value)
        if pattern is _URL_RE:
            matches = [match.rstrip(".,;:!?，。；：！？、)]}") for match in matches]
        fragments.extend(matches)
    return tuple(fragments)


def _protected_inputs(
    messages: Iterable[dict],
    explicit_inputs: Iterable[str],
) -> tuple[str, ...]:
    user_inputs = tuple(
        message.get("content", "")
        for message in messages
        if message.get("role") == "user"
        and isinstance(message.get("content"), str)
    )
    return (*user_inputs, *(value for value in explicit_inputs if isinstance(value, str)))


def _referenced_input_fragments(
    response: str,
    protected_inputs: Iterable[str],
    *,
    short_inputs: Iterable[str] = (),
) -> tuple[str, ...]:
    fragments: list[str] = []
    short_names = {
        source
        for source in short_inputs
        if 2 <= len(_CJK_RE.findall(source)) + len(_LATIN_RE.findall(source)) <= 3
    }
    for source in protected_inputs:
        minimum_chars = 2 if source in short_names else 4
        for block in SequenceMatcher(None, source, response, autojunk=False).get_matching_blocks():
            fragment = source[block.a:block.a + block.size].strip(
                " \t\r\n.,;:!?，。；：！？、()[]{}"
            )
            if (
                len(_CJK_RE.findall(fragment)) + len(_LATIN_RE.findall(fragment))
                >= minimum_chars
            ):
                fragments.append(fragment)
    return tuple(dict.fromkeys(fragments))
