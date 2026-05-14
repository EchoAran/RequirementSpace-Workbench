from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .. import models


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def append_operation(
    ws: models.Workspace,
    *,
    actionType: str,
    targetIds: list[str] | None = None,
    actor: dict[str, Any] | None = None,
    summary: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    audit = dict(ws.audit or {})
    log = list(audit.get("operationLog") or [])
    log.append(
        {
            "id": _new_id("op"),
            "timestamp": _now_iso(),
            "actionType": actionType,
            "targetIds": targetIds or [],
            "actor": actor or {"type": "system"},
            "summary": summary,
            "details": details or {},
        }
    )
    audit["operationLog"] = log
    audit["updatedAt"] = _now_iso()
    ws.audit = audit
    ws.updated_at = datetime.utcnow()

