from unittest.mock import AsyncMock

import pytest

from backend.api.modules.preview_convergence.application.shadow_patch_generator import (
    PreviewShadowPatchGenerator,
)


EMPTY_PATCH = {
    "actors_added": [],
    "features_added": [],
    "feature_actor_links_added": [],
    "scenarios_added": [],
    "acceptance_criteria_added": [],
    "business_objects_added": [],
    "business_object_attributes_added": [],
    "flows_added": [],
    "flow_steps_added": [],
    "scopes_added": [],
}


class _GateEvaluator:
    def __init__(self, gates: dict[str, bool]) -> None:
        self.gates = gates
        self.calls = []

    async def evaluate_gates(self, project_id, session):
        self.calls.append((project_id, session))
        return self.gates


class _Service:
    def __init__(self, gates: dict[str, bool]) -> None:
        self.gate_evaluator = _GateEvaluator(gates)
        self._update_progress = AsyncMock()


@pytest.fixture(autouse=True)
def registered_generation_services(monkeypatch):
    ports = "backend.api.modules.requirements_core.ports"
    monkeypatch.setattr(f"{ports}.get_flow_generation_service", lambda: object())
    monkeypatch.setattr(f"{ports}.get_scope_generation_service", lambda: object())
    monkeypatch.setattr(f"{ports}.get_feature_generation_service", lambda: object())


@pytest.mark.asyncio
async def test_generate_shadow_patch_returns_stable_empty_patch_when_all_gates_pass():
    service = _Service({"what": True, "how": True, "scope": True})
    provided_session = object()

    result = await PreviewShadowPatchGenerator.generate_shadow_patch(
        service=service,
        project_id=7,
        base_snapshot={},
        session=provided_session,
        draft_id="draft-7",
    )

    assert result == EMPTY_PATCH
    assert service.gate_evaluator.calls == [(7, provided_session)]
    service._update_progress.assert_awaited_once_with(
        "draft-7",
        25,
        "preview.full.progressWhat",
    )


@pytest.mark.asyncio
async def test_generate_shadow_patch_preserves_what_assets_and_fills_scenario_gap():
    service = _Service({"what": False, "how": True, "scope": True})
    base_snapshot = {
        "actors": [{"id": 1, "name": "用户"}],
        "features": [
            {
                "id": 10,
                "name": "订单管理",
                "description": "处理订单",
                "parent_id": None,
                "actor_ids": [1],
                "scenarios": [],
            }
        ],
    }

    result = await PreviewShadowPatchGenerator.generate_shadow_patch(
        service=service,
        project_id=7,
        base_snapshot=base_snapshot,
        session=object(),
    )

    assert result == {
        **EMPTY_PATCH,
        "scenarios_added": [
            {
                "temp_id": "tmp_scenario_1",
                "name": "验证订单管理在用户视角下的主干业务场景",
                "content": (
                    "As a 用户, I want to 处理订单, "
                    "So that 我可以获得预期的系统产出和服务。"
                ),
                "feature_ref": "feature:10",
                "actor_ref": "actor:1",
            }
        ],
        "acceptance_criteria_added": [
            {
                "scenario_ref": "tmp_scenario_1",
                "content": (
                    "Given 用户 准备使用 订单管理 功能, "
                    "When 用户 触发相关交互操作, "
                    "Then 系统应当正确处理并呈现 订单管理 的相关界面与数据元。"
                ),
                "position": 1,
            }
        ],
    }


@pytest.mark.asyncio
async def test_generate_shadow_patch_adds_only_missing_acceptance_criteria():
    service = _Service({"what": True, "how": True, "scope": True})
    base_snapshot = {
        "actors": [{"id": 2, "name": "管理员"}],
        "features": [
            {
                "id": 20,
                "name": "权限管理",
                "description": "配置权限",
                "parent_id": None,
                "actor_ids": [2],
                "scenarios": [
                    {
                        "id": 30,
                        "actor_id": 2,
                        "acceptance_criteria": [],
                    }
                ],
            }
        ],
    }

    result = await PreviewShadowPatchGenerator.generate_shadow_patch(
        service=service,
        project_id=8,
        base_snapshot=base_snapshot,
        session=object(),
    )

    assert result["scenarios_added"] == []
    assert result["acceptance_criteria_added"] == [
        {
            "scenario_ref": "scenario:30",
            "content": (
                "Given 管理员 准备使用 权限管理 功能, "
                "When 管理员 触发相关交互操作, "
                "Then 系统应当正确处理并呈现 权限管理 的相关界面与数据元。"
            ),
            "position": 1,
        }
    ]
