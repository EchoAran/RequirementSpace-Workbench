import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from .shadow_snapshot import (
    load_snapshot_data,
    remap_snapshot_to_pydantic,
    serialize_snapshot,
)


def calculate_stable_snapshot_hash(snapshot: dict) -> str:
    """
    Compute a SHA-256 hash from canonical JSON.
    """
    dumped = json.dumps(
        snapshot,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


async def build_project_snapshot(
    project_id: int,
    session: AsyncSession,
) -> dict:
    """
    Build a stable structural snapshot for a project.
    """
    data = await load_snapshot_data(project_id, session)
    return serialize_snapshot(data)


class PreviewShadowProjectCreator:
    pass
