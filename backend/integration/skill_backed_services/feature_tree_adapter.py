from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.schemas import ActorNode


ROLE_TAG_PATTERN = re.compile(r"\s*\[Role:\s*(?P<role>[^\]]+)\]\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedFeatureTreeItem:
    key: str
    feature_number: str
    name: str
    description: str
    role: str | None
    actor_ids: list[int]


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _sort_key(level_key: str) -> tuple[int, ...]:
    if level_key == "L1":
        return (1,)
    match = re.fullmatch(r"L(?P<level>\d+)(?:\.(?P<parts>[\d.]+))?", level_key)
    if match is None:
        return (999,)
    level = int(match.group("level"))
    parts = [int(part) for part in (match.group("parts") or "").split(".") if part]
    return (level, *parts)


def _to_feature_number(level_key: str) -> str:
    if level_key == "L1":
        return "F001"

    match = re.fullmatch(r"L(?P<level>\d+)\.(?P<parts>[\d.]+)", level_key)
    if match is None:
        raise ValueError("invalid_feature_number_format")

    level = int(match.group("level"))
    parts = [int(part) for part in match.group("parts").split(".")]
    if level < 2 or len(parts) != level - 1:
        raise ValueError("invalid_feature_number_format")

    return "F001-" + "-".join(f"{part:03d}" for part in parts)


def _parent_level_key(level_key: str) -> str | None:
    if level_key == "L1":
        return None

    match = re.fullmatch(r"L(?P<level>\d+)\.(?P<parts>[\d.]+)", level_key)
    if match is None:
        raise ValueError("invalid_feature_number_format")

    level = int(match.group("level"))
    parts = match.group("parts").split(".")
    if level == 2:
        return "L1"
    return f"L{level - 1}." + ".".join(parts[:-1])


def _parse_name_role_description(value: Any) -> tuple[str, str | None, str | None]:
    if isinstance(value, dict):
        name = str(value.get("name") or value.get("feature_name") or value.get("Feature") or "").strip()
        description = value.get("description") or value.get("feature_description")
        role = value.get("role") or value.get("actor") or value.get("Role")
        if not name and value.get("value"):
            name = str(value["value"]).strip()
        name, tag_role = _strip_role_tag(name)
        return name, str(role or tag_role).strip() or None, str(description or "").strip() or None

    name, role = _strip_role_tag(str(value or "").strip())
    return name, role, None


def _strip_role_tag(name: str) -> tuple[str, str | None]:
    match = ROLE_TAG_PATTERN.search(name)
    if match is None:
        return name.strip(), None
    role = match.group("role").strip()
    return ROLE_TAG_PATTERN.sub("", name).strip(), role


def _role_to_actor_ids(role: str | None, actors: list[ActorNode]) -> list[int]:
    if not actors:
        return []

    if role is None or _normalize_name(role) == "common":
        return [actor.actorId for actor in actors]

    role_names = [item.strip() for item in role.split(",") if item.strip()]
    actor_by_name = {
        _normalize_name(actor.actorName): actor.actorId
        for actor in actors
    }

    actor_ids = []
    for role_name in role_names:
        actor_id = actor_by_name.get(_normalize_name(role_name))
        if actor_id is not None and actor_id not in actor_ids:
            actor_ids.append(actor_id)

    if not actor_ids:
        raise ValueError("invalid_actor_reference")

    return actor_ids


def _fallback_description(name: str, level_key: str) -> str:
    if level_key == "L1":
        return f"{name}."
    return f"Support {name}."


class FeatureTreeAdapter:
    def to_current_features(
        self,
        raw_feature_tree: str | dict[str, Any],
        actors: list[ActorNode],
    ) -> list[dict]:
        if isinstance(raw_feature_tree, str):
            try:
                feature_tree = json.loads(raw_feature_tree)
            except json.JSONDecodeError as error:
                raise ValueError("invalid_feature_payload") from error
        else:
            feature_tree = raw_feature_tree

        if not isinstance(feature_tree, dict) or not feature_tree:
            raise ValueError("empty_features")

        if "features" in feature_tree and isinstance(feature_tree["features"], list):
            return self._normalize_current_style_features(feature_tree["features"], actors)

        level_keys = [str(key) for key in feature_tree.keys()]
        if "L1" not in level_keys:
            raise ValueError("invalid_root_feature_count")

        level_key_set = set(level_keys)
        items: list[ParsedFeatureTreeItem] = []
        for level_key in sorted(level_keys, key=_sort_key):
            parent_key = _parent_level_key(level_key)
            if parent_key is not None and parent_key not in level_key_set:
                raise ValueError("missing_parent_feature")

            name, role, description = _parse_name_role_description(feature_tree[level_key])
            if not name:
                raise ValueError("invalid_feature_payload")

            items.append(
                ParsedFeatureTreeItem(
                    key=level_key,
                    feature_number=_to_feature_number(level_key),
                    name=name,
                    description=description or _fallback_description(name, level_key),
                    role=role,
                    actor_ids=_role_to_actor_ids(role, actors),
                )
            )

        root_count = sum(1 for item in items if item.feature_number == "F001")
        if root_count != 1:
            raise ValueError("invalid_root_feature_count")

        return [
            {
                "feature_number": item.feature_number,
                "feature_name": item.name,
                "feature_description": item.description,
                "actor_ids": item.actor_ids,
            }
            for item in items
        ]

    def _normalize_current_style_features(
        self,
        raw_features: list[dict],
        actors: list[ActorNode],
    ) -> list[dict]:
        actor_id_set = {actor.actorId for actor in actors}
        features = []
        for raw_feature in raw_features:
            actor_ids = []
            for raw_actor_id in raw_feature.get("actor_ids", []):
                try:
                    actor_id = int(raw_actor_id)
                except (TypeError, ValueError) as error:
                    raise ValueError("invalid_actor_reference") from error
                if actor_id not in actor_id_set:
                    raise ValueError("invalid_actor_reference")
                actor_ids.append(actor_id)

            feature_name = str(raw_feature.get("feature_name", "")).strip()
            if not feature_name:
                raise ValueError("invalid_feature_payload")

            features.append(
                {
                    "feature_number": raw_feature.get("feature_number"),
                    "feature_name": feature_name,
                    "feature_description": str(
                        raw_feature.get("feature_description") or _fallback_description(feature_name, "")
                    ).strip(),
                    "actor_ids": actor_ids,
                }
            )

        return features

