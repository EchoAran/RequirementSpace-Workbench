"""Stable rules and configuration constants for backend core."""

EDITABLE_FIELDS: dict[str, list[str]] = {
    "actor": ["name", "description"],
    "feature": ["name", "description", "actor_ids"],
    "flow": ["name", "description", "feature_ids"],
    "business_object": ["name", "description"],
}
