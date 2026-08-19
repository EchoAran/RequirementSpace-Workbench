"""
Workspace State Reader & Serializer.
负责把某个 BranchWorkspace 中的正式需求实体读取为与 Commit state_json 同构的规范化状态字典。
这是提交创建、未提交变更摘要和语义 Diff 的公共前置能力：任何“把当前工作区变成一份可哈希快照”的
路径都必须经由本模块，避免不同调用方各自从表结构拼装状态而出现契约漂移。
"""
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database.model import (
    BranchWorkspaceModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    FlowModel,
    FlowStepModel,
    ScopeModel,
)
from backend.api.modules.version_control.domain.serializer import (
    serialize_requirement_space,
)


def _read_actors(db: Session, ws_id: int) -> Tuple[List[Dict[str, Any]], Dict[int, str]]:
    """读取工作区内的参与者，返回 (原始字典列表, id→logical_uuid 映射)。"""
    actors = db.scalars(
        select(ActorModel).where(ActorModel.workspace_id == ws_id)
    ).all()
    uuid_by_id = {a.id: a.logical_uuid for a in actors}
    dicts = [
        {
            "logical_uuid": a.logical_uuid,
            "name": a.name,
            "description": a.description,
            "confirmation_status": a.confirmation_status,
        }
        for a in actors
    ]
    return dicts, uuid_by_id


def _read_features(db: Session, ws_id: int) -> Tuple[List[Dict[str, Any]], Dict[int, str]]:
    """读取工作区内的功能及其参与者关联，返回 (原始字典列表, id→logical_uuid 映射)。"""
    stmt = (
        select(FeatureModel)
        .where(FeatureModel.workspace_id == ws_id)
        .options(selectinload(FeatureModel.actors))
    )
    features = db.scalars(stmt).all()
    uuid_by_id = {f.id: f.logical_uuid for f in features}
    dicts = [
        {
            "logical_uuid": f.logical_uuid,
            "name": f.name,
            "description": f.description,
            "confirmation_status": f.confirmation_status,
            "actor_logical_uuids": sorted({a.logical_uuid for a in f.actors}),
        }
        for f in features
    ]
    return dicts, uuid_by_id


def _read_feature_relations(
    db: Session,
    ws_id: int,
    feat_uuid_by_id: Dict[int, str],
) -> List[Dict[str, Any]]:
    """读取功能树父子边；端点功能必须落在同一工作区，否则跳过悬挂边。"""
    relations = db.scalars(
        select(FeatureRelationModel).where(FeatureRelationModel.workspace_id == ws_id)
    ).all()
    dicts: List[Dict[str, Any]] = []
    for rel in relations:
        parent_uuid = feat_uuid_by_id.get(rel.parent_feature_id)
        child_uuid = feat_uuid_by_id.get(rel.child_feature_id)
        if not parent_uuid or not child_uuid:
            # 跨工作区或悬挂的功能树边属于数据完整性错误；跳过避免生成不可恢复的状态快照。
            continue
        dicts.append(
            {
                "logical_uuid": rel.logical_uuid,
                "parent_feature_logical_uuid": parent_uuid,
                "child_feature_logical_uuid": child_uuid,
                "position": rel.position,
            }
        )
    return dicts


def _read_scenarios(
    db: Session,
    ws_id: int,
    feat_uuid_by_id: Dict[int, str],
    actor_uuid_by_id: Dict[int, str],
) -> List[Dict[str, Any]]:
    """读取工作区内的场景及其验收标准；场景两端引用必须闭合。"""
    stmt = (
        select(ScenarioModel)
        .where(ScenarioModel.workspace_id == ws_id)
        .options(selectinload(ScenarioModel.acceptance_criteria))
    )
    scenarios = db.scalars(stmt).all()
    dicts: List[Dict[str, Any]] = []
    for sc in scenarios:
        feat_uuid = feat_uuid_by_id.get(sc.feature_id)
        actor_uuid = actor_uuid_by_id.get(sc.actor_id)
        if not feat_uuid or not actor_uuid:
            continue
        ac_list = [
            {
                "logical_uuid": ac.logical_uuid,
                "position": ac.position,
                "content": ac.content,
                "confirmation_status": ac.confirmation_status,
            }
            for ac in sc.acceptance_criteria
        ]
        dicts.append(
            {
                "logical_uuid": sc.logical_uuid,
                "feature_logical_uuid": feat_uuid,
                "actor_logical_uuid": actor_uuid,
                "name": sc.name,
                "content": sc.content,
                "confirmation_status": sc.confirmation_status,
                "acceptance_criteria": ac_list,
            }
        )
    return dicts


def _read_business_objects(
    db: Session,
    ws_id: int,
) -> Tuple[List[Dict[str, Any]], Dict[int, str]]:
    """读取工作区内的业务对象及其属性。"""
    stmt = (
        select(BusinessObjectModel)
        .where(BusinessObjectModel.workspace_id == ws_id)
        .options(selectinload(BusinessObjectModel.attributes))
    )
    objects = db.scalars(stmt).all()
    uuid_by_id = {b.id: b.logical_uuid for b in objects}
    dicts = [
        {
            "logical_uuid": b.logical_uuid,
            "name": b.name,
            "description": b.description,
            "confirmation_status": b.confirmation_status,
            "attributes": [
                {
                    "logical_uuid": attr.logical_uuid,
                    "name": attr.name,
                    "data_type": attr.data_type,
                    "description": attr.description,
                    "example": attr.example,
                    "confirmation_status": attr.confirmation_status,
                }
                for attr in b.attributes
            ],
        }
        for b in objects
    ]
    return dicts, uuid_by_id


def _read_flows(
    db: Session,
    ws_id: int,
    feat_uuid_by_id: Dict[int, str],
    actor_uuid_by_id: Dict[int, str],
    bo_uuid_by_id: Dict[int, str],
) -> List[Dict[str, Any]]:
    """读取工作区内的流程及其步骤、步骤参与者和输入输出业务对象、next 边。"""
    stmt = (
        select(FlowModel)
        .where(FlowModel.workspace_id == ws_id)
        .options(
            selectinload(FlowModel.features),
            selectinload(FlowModel.steps).selectinload(FlowStepModel.actors),
            selectinload(FlowModel.steps).selectinload(FlowStepModel.input_business_objects),
            selectinload(FlowModel.steps).selectinload(FlowStepModel.output_business_objects),
            selectinload(FlowModel.steps).selectinload(FlowStepModel.next_steps),
        )
    )
    flows = db.scalars(stmt).all()
    dicts: List[Dict[str, Any]] = []
    for flow in flows:
        step_dicts = []
        for step in flow.steps:
            step_dicts.append(
                {
                    "logical_uuid": step.logical_uuid,
                    "position": step.position,
                    "name": step.name,
                    "description": step.description,
                    "step_type": step.step_type,
                    "confirmation_status": step.confirmation_status,
                    "actor_logical_uuids": sorted({a.logical_uuid for a in step.actors}),
                    "input_business_object_logical_uuids": sorted(
                        {b.logical_uuid for b in step.input_business_objects}
                    ),
                    "output_business_object_logical_uuids": sorted(
                        {b.logical_uuid for b in step.output_business_objects}
                    ),
                    "next_step_logical_uuids": sorted({s.logical_uuid for s in step.next_steps}),
                }
            )
        dicts.append(
            {
                "logical_uuid": flow.logical_uuid,
                "name": flow.name,
                "description": flow.description,
                "confirmation_status": flow.confirmation_status,
                "feature_logical_uuids": sorted({f.logical_uuid for f in flow.features}),
                "steps": step_dicts,
            }
        )
    return dicts


def _read_scopes(
    db: Session,
    ws_id: int,
    feat_uuid_by_id: Dict[int, str],
) -> List[Dict[str, Any]]:
    """读取工作区内的范围决策；范围必须归属本工作区的功能。"""
    scopes = db.scalars(
        select(ScopeModel).where(ScopeModel.workspace_id == ws_id)
    ).all()
    dicts: List[Dict[str, Any]] = []
    for sc in scopes:
        feat_uuid = feat_uuid_by_id.get(sc.feature_id)
        if not feat_uuid:
            continue
        dicts.append(
            {
                "logical_uuid": sc.logical_uuid,
                "feature_logical_uuid": feat_uuid,
                "status": sc.status,
                "positive_summary": sc.positive_summary,
                "negative_summary": sc.negative_summary,
                "reason": sc.reason,
                "kano_category": sc.kano_category,
                "kano_category_name": sc.kano_category_name,
                "confirmation_status": sc.confirmation_status,
            }
        )
    return dicts


def build_workspace_state_dict(
    db: Session,
    workspace: BranchWorkspaceModel,
) -> Dict[str, Any]:
    """
    把 BranchWorkspace 的全部正式需求实体读取为 raw 状态字典（尚未规范化排序）。

    :param db: 同步 SQLAlchemy Session（经 run_sync 或测试用同步会话）
    :param workspace: 目标分支工作区实体
    :return: 与 serialize_requirement_space 输入同构的原始字典
    """
    ws_id = workspace.id
    actor_dicts, actor_uuid_by_id = _read_actors(db, ws_id)
    feat_dicts, feat_uuid_by_id = _read_features(db, ws_id)
    rel_dicts = _read_feature_relations(db, ws_id, feat_uuid_by_id)
    sc_dicts = _read_scenarios(db, ws_id, feat_uuid_by_id, actor_uuid_by_id)
    bo_dicts, bo_uuid_by_id = _read_business_objects(db, ws_id)
    flow_dicts = _read_flows(db, ws_id, feat_uuid_by_id, actor_uuid_by_id, bo_uuid_by_id)
    scope_dicts = _read_scopes(db, ws_id, feat_uuid_by_id)

    return {
        "project_metadata": {
            "user_requirements": workspace.user_requirements or "",
            "kano_status": workspace.kano_status or "missing",
            "unlocked_stages": workspace.unlocked_stages or "",
        },
        "actors": actor_dicts,
        "features": feat_dicts,
        "feature_relations": rel_dicts,
        "scenarios": sc_dicts,
        "business_objects": bo_dicts,
        "flows": flow_dicts,
        "scopes": scope_dicts,
    }


def serialize_workspace(
    db: Session,
    workspace: BranchWorkspaceModel,
) -> Dict[str, Any]:
    """
    返回 BranchWorkspace 的规范化状态字典（与 Commit state_json 完全同构，可直接比较/哈希）。

    :param db: 同步 SQLAlchemy Session
    :param workspace: 目标分支工作区实体
    :return: 规范化、确定性排序的完整需求空间状态字典
    """
    raw = build_workspace_state_dict(db, workspace)
    return serialize_requirement_space(raw)
