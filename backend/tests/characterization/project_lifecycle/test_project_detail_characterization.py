from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.modules.project_lifecycle.application.project_service import (
    ProjectService,
)


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _ProjectDetailSession:
    def __init__(self, project, perception_job=None):
        self.project = project
        self.perception_job = perception_job

    async def execute(self, statement):
        stmt_str = str(statement).lower()
        if "domain_rule" in stmt_str:
            return _ScalarResult([])
        return _ScalarResult(self.project)

    async def get(self, _model, _identifier):
        return self.perception_job

    async def run_sync(self, fn, *args, **kwargs):
        # get_project_detail 通过 run_sync 解析分支上下文；测试中直接同步执行回调。
        return fn(self)


def _node(timestamp, **values):
    return SimpleNamespace(
        logical_uuid=f"node-{values['id']}",
        confirmation_status="confirmed",
        updated_at=timestamp,
        **values,
    )


@pytest.mark.asyncio
async def test_get_project_detail_preserves_nested_mapping_and_status():
    timestamp = datetime(2026, 7, 30, 8, 0, tzinfo=UTC)
    actor = _node(timestamp, id=11, name="客户", description="下单人")
    criterion = _node(timestamp, id=41, content="库存被扣减")
    scenario = _node(
        timestamp,
        id=31,
        name="创建订单",
        content="Given 商品有库存",
        feature_id=21,
        actor_id=11,
        acceptance_criteria=[criterion],
    )
    scope = _node(
        timestamp,
        id=51,
        status="in_scope",
        reason="核心能力",
        positive_summary="支持下单",
        negative_summary="不支持退款",
        positive_picture=b"positive",
        negative_picture=None,
        kano_category="must_be",
        kano_category_name="基本型",
    )
    feature = _node(
        timestamp,
        id=21,
        name="订单管理",
        description="创建并管理订单",
        actors=[actor],
        parent_relation=SimpleNamespace(parent_feature_id=20),
        child_relations=[SimpleNamespace(child_feature_id=22)],
        scenarios=[scenario],
        scope=scope,
    )
    attribute = _node(
        timestamp,
        id=61,
        name="订单号",
        description="唯一编号",
        data_type="string",
        example="SO-1",
    )
    business_object = _node(
        timestamp,
        id=60,
        name="订单",
        description="订单数据",
        attributes=[attribute],
    )
    flow_step = _node(
        timestamp,
        id=72,
        name="提交订单",
        description="保存订单",
        step_type="action",
        position=1,
        actors=[actor],
        input_business_objects=[business_object],
        output_business_objects=[business_object],
    )
    flow_transition = _node(
        timestamp,
        id=85,
        flow_id=71,
        source_step_id=72,
        target_step_id=73,
        label="",
        condition_text="",
        is_default=True,
        position=0,
        semantic_tags=["confirmed"],
        origin="manual",
    )
    flow = _node(
        timestamp,
        id=71,
        name="下单流程",
        description="完成下单",
        features=[feature],
        steps=[flow_step],
        transitions=[flow_transition],
    )
    project = SimpleNamespace(
        id=1,
        public_id="project-public-id",
        name="订单项目",
        description="订单需求空间",
        user_requirements="支持在线下单",
        perception_slot=SimpleNamespace(
            id=81,
            perception_kind="requirements",
            description="需求感知",
        ),
        actors=[actor],
        features=[feature],
        business_objects=[business_object],
        flows=[flow],
        domain_rules=[],
        kano_status="completed",
        unlocked_stages=" what, how ,,",
    )
    perception_job = SimpleNamespace(stage="what")
    gate = SimpleNamespace(
        findingId="what:GATE:feature:21",
        title="导出门禁",
        description="仍有问题",
        stage=SimpleNamespace(value="what"),
        code="GATE",
    )
    service = ProjectService()
    service._count_visible_open_issues = AsyncMock(return_value=3)
    service._derive_project_status = lambda **_kwargs: (
        "in_progress",
        "建模中",
    )

    with patch(
        "backend.api.modules.diagnosis_quality.public."
        "FindingService.list_findings",
        new=AsyncMock(return_value=[gate]),
    ), patch(
        # get_project_detail 会按分支解析工作区；此测试只验证项目详情构建，因此跳过分支解析。
        "backend.api.modules.version_control.public.resolve_branch_context",
        return_value=(None, SimpleNamespace(id=2, user_requirements=project.user_requirements, kano_status=project.kano_status, unlocked_stages=project.unlocked_stages), {"can_write": True}),
    ), patch("backend.api.modules.project_lifecycle.application.project_service.load_project_detail_model", new=AsyncMock(return_value=project)), patch("backend.api.modules.project_lifecycle.application.project_service.build_visible_perception_slot", new=AsyncMock(return_value=SimpleNamespace(perception_slot_id=81, perception_kind="requirements", perception_description="需求感知", stage="what"))):
        detail = await service.get_project_detail(
            project.id,
            _ProjectDetailSession(project, perception_job),
        )

    assert detail.project_id == "project-public-id"
    assert detail.unlocked_stages == ["what", "how"]
    assert detail.perception_slot.stage == "what"
    assert detail.actors[0].actor_id == 11
    assert detail.features[0].parent_id == 20
    assert detail.features[0].children_ids == [22]
    assert detail.features[0].scope.positive_picture_base64 == "cG9zaXRpdmU="
    assert detail.features[0].scenarios[0].acceptance_criteria[0].criterion_id == 41
    assert (
        detail.business_objects[0]
        .business_object_attributes[0]
        .business_object_attribute_id
        == 61
    )
    assert detail.flows[0].transitions[0].target_step_id == 73
    assert detail.issue_count == 3
    assert detail.status_code == "in_progress"
    assert detail.status == "建模中"
    assert detail.unresolved_gates[0].finding_id == "what:GATE:feature:21"


@pytest.mark.asyncio
async def test_get_project_detail_preserves_missing_project_error():
    service = ProjectService()

    with pytest.raises(ValueError, match="^project_not_found$"):
        await service.get_project_detail(
            999,
            _ProjectDetailSession(None),
        )
