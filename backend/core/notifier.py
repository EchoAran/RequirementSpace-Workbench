"""Notifier ports for requirements changed events.

This module is placed in backend/core to serve as a shared interface,
breaking circular dependencies between API modules.
"""
from typing import Protocol


class RequirementsChangedNotifier(Protocol):
    async def mark_stale(
        self,
        project_id: int,
        stages: set[str],
        session,
        perception_kinds: set[str] | None = None,
        clear_active_slot: bool = True,
        workspace_id: int | None = None,
    ) -> None:
        """Mark affected perception jobs as stale when requirement elements change."""
        ...


# Global notifier registry
_notifier: RequirementsChangedNotifier | None = None


def get_notifier() -> RequirementsChangedNotifier:
    if _notifier is None:
        raise RuntimeError("RequirementsChangedNotifier has not been registered! Please call set_notifier() at startup.")
    return _notifier


def set_notifier(notifier: RequirementsChangedNotifier) -> None:
    global _notifier
    _notifier = notifier
