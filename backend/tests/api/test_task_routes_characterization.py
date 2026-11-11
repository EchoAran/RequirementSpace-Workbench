from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api.modules.collaboration.routes import tasks as tasks_routes


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


@pytest.mark.asyncio
async def test_list_my_tasks_preserves_composite_summary_shape(monkeypatch):
    task = SimpleNamespace(
        project_id=7,
        target_type="feature",
        target_id="not-an-integer",
        task_type="confirm_node",
        created_by_user_id=11,
        assigned_to_user_id=12,
        creator=SimpleNamespace(email="creator@example.com"),
        assignee=SimpleNamespace(email="assignee@example.com"),
    )
    project = SimpleNamespace(
        id=7,
        public_id="project-public-id",
        name="Project Name",
    )
    mapped_task = SimpleNamespace(
        node_name="Feature Name",
        content_changed=True,
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarResult([task]),
                _ScalarResult([project]),
            ]
        )
    )
    monkeypatch.setattr(
        tasks_routes,
        "_map_task",
        AsyncMock(return_value=mapped_task),
    )

    result = await tasks_routes.list_my_tasks(
        role="both",
        status="open,rejected",
        task_type="confirm_node",
        project_id=None,
        limit=10,
        offset=0,
        session=session,
        current_user=SimpleNamespace(id=12),
    )

    assert result == [
        {
            "task": mapped_task,
            "project_summary": {
                "project_id": "project-public-id",
                "project_name": "Project Name",
            },
            "target_summary": {
                "node_kind": "feature",
                "node_id": None,
                "node_name": "Feature Name",
            },
            "creator_summary": {
                "user_id": 11,
                "email": "creator@example.com",
            },
            "assignee_summary": {
                "user_id": 12,
                "email": "assignee@example.com",
            },
            "content_changed": True,
        }
    ]
