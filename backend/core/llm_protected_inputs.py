from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Any


def collect_protected_texts(*values: Any) -> tuple[str, ...]:
    """Collect distinct user/project text from explicit LLM input objects."""
    texts: list[str] = []
    seen: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text and text not in seen:
                seen.add(text)
                texts.append(text)
            return
        if isinstance(value, Mapping):
            for item in value.values():
                visit(item)
            return
        if is_dataclass(value) and not isinstance(value, type):
            for field in fields(value):
                visit(getattr(value, field.name))
            return
        if isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                visit(item)

    for value in values:
        visit(value)
    return tuple(texts)
