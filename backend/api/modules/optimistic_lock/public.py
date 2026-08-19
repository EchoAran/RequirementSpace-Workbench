"""
Optimistic Lock & Node Snapshot Public Facade.
对外提供稳定的乐观锁与快照能力入口，供 requirements_core、collaboration 等模块导入。
"""
from backend.api.modules.optimistic_lock.snapshot_service import (
    NodeSnapshotService,
    snapshot_service,
)
from backend.api.modules.optimistic_lock.node_snapshot_builders import (
    build_node_snapshot,
)
from backend.api.modules.optimistic_lock.superseder import (
    supersede_tasks_for_node_update,
)

__all__ = [
    "NodeSnapshotService",
    "snapshot_service",
    "build_node_snapshot",
    "supersede_tasks_for_node_update",
]
