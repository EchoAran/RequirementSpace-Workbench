from collections.abc import Iterable
from typing import Any


def canonicalize_rule_source_links(
    links: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collapse repeated rule-source relationships while preserving the strongest evidence text."""
    canonical: dict[tuple[str, str], dict[str, Any]] = {}
    for link in links:
        normalized = dict(link)
        normalized["context_text"] = str(link.get("context_text") or "").strip()
        key = (
            str(link.get("target_kind") or "").strip(),
            str(link.get("target_logical_uuid") or "").strip(),
        )
        normalized["target_kind"] = key[0]
        normalized["target_logical_uuid"] = key[1]

        existing = canonical.get(key)
        if existing is None:
            canonical[key] = normalized
            continue

        if len(normalized["context_text"]) > len(existing["context_text"]):
            existing["context_text"] = normalized["context_text"]

    return list(canonical.values())
