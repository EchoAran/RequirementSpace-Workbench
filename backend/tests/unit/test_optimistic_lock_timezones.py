from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.api.modules.optimistic_lock.snapshot_service import NodeSnapshotService
from backend.database.model import BEIJING_TZ

UPDATED_AT = datetime(2026, 11, 11, 20, 30, tzinfo=BEIJING_TZ)


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_time", [UPDATED_AT.replace(tzinfo=None), UPDATED_AT.astimezone(UTC)])
@pytest.mark.parametrize("client_time", [
    UPDATED_AT,
    UPDATED_AT.isoformat(),
    UPDATED_AT.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    UPDATED_AT.astimezone(timezone(timedelta(hours=-4))).isoformat(),
    str(UPDATED_AT.timestamp()),
    UPDATED_AT.replace(tzinfo=None),
    UPDATED_AT.replace(tzinfo=None).isoformat(),
])
async def test_equivalent_timestamps_do_not_conflict(stored_time, client_time):
    service = NodeSnapshotService()
    service.get_snapshot_and_hash = AsyncMock()
    node = SimpleNamespace(id=1, updated_at=stored_time)

    await service.check_optimistic_lock(None, "actor", node, client_time)

    service.get_snapshot_and_hash.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_time", [UPDATED_AT.replace(tzinfo=None), UPDATED_AT.astimezone(UTC)])
async def test_stale_timestamp_still_returns_current_snapshot(stored_time):
    service = NodeSnapshotService()
    service.get_snapshot_and_hash = AsyncMock(return_value={"snapshot": {"name": "Current actor"}})
    node = SimpleNamespace(id=1, updated_at=stored_time)
    stale_time = (UPDATED_AT - timedelta(seconds=1)).astimezone(UTC).isoformat()

    with pytest.raises(HTTPException) as error:
        await service.check_optimistic_lock(None, "actor", node, stale_time)

    assert error.value.status_code == 409
    assert error.value.detail == {
        "message": "node_content_changed",
        "current_snapshot": {"name": "Current actor"},
    }
    service.get_snapshot_and_hash.assert_awaited_once_with(None, "actor", 1)
