from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.api.modules.version_control.domain.uuid_generator import (
    ensure_logical_uuid,
)
from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    ChoiceGroupModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    ScenarioModel,
    ScopeModel,
)


def _has_table(db: Session, table_name: str) -> bool:
    """动态检查当前数据库链接中目标表是否存在。"""
    try:
        bind = db.get_bind()
        return bind.dialect.has_table(db.connection(), table_name)
    except Exception:
        return False


def _backfill_actors(
    db: Session,
    project_id: int,
    workspace_id: int,
) -> list[dict[str, Any]]:
    """为项目中的所有 Actor 实体回填 logical_uuid 与 workspace_id。"""
    if not _has_table(db, "actors"):
        return []
    actors = db.scalars(
        select(ActorModel).where(
            ActorModel.project_id == project_id,
            or_(ActorModel.workspace_id.is_(None), ActorModel.workspace_id == workspace_id),
        )
    ).all()
    actor_dicts = []
    for actor in actors:
        ensure_logical_uuid(actor)
        actor.workspace_id = workspace_id
        actor_dicts.append({
            "logical_uuid": actor.logical_uuid,
            "name": actor.name,
            "description": actor.description,
            "confirmation_status": actor.confirmation_status,
        })
    return actor_dicts


def _backfill_features_and_relations(
    db: Session,
    project_id: int,
    workspace_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, str]]:
    """为 Feature 与 FeatureRelation 回填 UUID 与 workspace_id。"""
    if not _has_table(db, "features"):
        return [], [], {}
    features = db.scalars(
        select(FeatureModel).where(
            FeatureModel.project_id == project_id,
            or_(FeatureModel.workspace_id.is_(None), FeatureModel.workspace_id == workspace_id),
        )
    ).all()
    feat_map = {}
    for feat in features:
        ensure_logical_uuid(feat)
        feat.workspace_id = workspace_id
        feat_map[feat.id] = feat.logical_uuid

    feat_dicts = []
    has_fa_table = _has_table(db, "feature_actor")
    for feat in features:
        bound_uuids = (
            [a.logical_uuid for a in feat.actors if getattr(a, "logical_uuid", None)]
            if has_fa_table and hasattr(feat, "actors")
            else []
        )
        feat_dicts.append({
            "logical_uuid": feat.logical_uuid,
            "name": feat.name,
            "description": feat.description,
            "confirmation_status": feat.confirmation_status,
            "actor_logical_uuids": bound_uuids,
        })

    rel_dicts = []
    if _has_table(db, "feature_relations"):
        all_rels = db.scalars(
            select(FeatureRelationModel).where(
                or_(
                    FeatureRelationModel.workspace_id.is_(None),
                    FeatureRelationModel.workspace_id == workspace_id,
                )
            )
        ).all()
        relations = [r for r in all_rels if r.parent_feature_id in feat_map]
        for rel in relations:
            ensure_logical_uuid(rel)
            rel.workspace_id = workspace_id
            p_uuid = feat_map.get(rel.parent_feature_id)
            c_uuid = feat_map.get(rel.child_feature_id)
            if p_uuid and c_uuid:
                rel_dicts.append({
                    "logical_uuid": rel.logical_uuid,
                    "parent_feature_logical_uuid": p_uuid,
                    "child_feature_logical_uuid": c_uuid,
                    "position": rel.position,
                })
    return feat_dicts, rel_dicts, feat_map


def _backfill_scenarios(
    db: Session,
    project_id: int,
    workspace_id: int,
    feat_map: dict[int, str],
) -> list[dict[str, Any]]:
    """为 Scenario 及 ScenarioAcceptanceCriterion 回填 UUID 与 workspace_id。"""
    if not _has_table(db, "scenarios"):
        return []
    scenarios = db.scalars(
        select(ScenarioModel).where(
            ScenarioModel.project_id == project_id,
            or_(ScenarioModel.workspace_id.is_(None), ScenarioModel.workspace_id == workspace_id),
        )
    ).all()
    sc_dicts = []
    has_ac_table = _has_table(db, "scenario_acceptance_criteria")
    for sc in scenarios:
        ensure_logical_uuid(sc)
        sc.workspace_id = workspace_id

        ac_list = []
        if has_ac_table and hasattr(sc, "acceptance_criteria"):
            for ac in sc.acceptance_criteria:
                ensure_logical_uuid(ac)
                ac.workspace_id = workspace_id
                ac_list.append({
                    "logical_uuid": ac.logical_uuid,
                    "position": ac.position,
                    "content": ac.content,
                    "confirmation_status": ac.confirmation_status,
                })

        feat_uuid = feat_map.get(sc.feature_id)
        actor_uuid = getattr(sc.actor, "logical_uuid", None) if sc.actor else None
        sc_dicts.append({
            "logical_uuid": sc.logical_uuid,
            "feature_logical_uuid": feat_uuid,
            "actor_logical_uuid": actor_uuid,
            "name": sc.name,
            "content": sc.content,
            "confirmation_status": sc.confirmation_status,
            "acceptance_criteria": ac_list,
        })
    return sc_dicts


def _backfill_business_objects(
    db: Session,
    project_id: int,
    workspace_id: int,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    """为 BusinessObject 及 BusinessObjectAttribute 回填 UUID 与 workspace_id。"""
    if not _has_table(db, "business_objects"):
        return [], {}
    bos = db.scalars(
        select(BusinessObjectModel).where(
            BusinessObjectModel.project_id == project_id,
            or_(
                BusinessObjectModel.workspace_id.is_(None),
                BusinessObjectModel.workspace_id == workspace_id,
            ),
        )
    ).all()
    bo_map = {}
    for bo in bos:
        ensure_logical_uuid(bo)
        bo.workspace_id = workspace_id
        bo_map[bo.id] = bo.logical_uuid

    bo_dicts = []
    has_attr_table = _has_table(db, "business_object_attributes")
    for bo in bos:
        attr_list = []
        if has_attr_table and hasattr(bo, "attributes"):
            for attr in bo.attributes:
                ensure_logical_uuid(attr)
                attr.workspace_id = workspace_id
                attr_list.append({
                    "logical_uuid": attr.logical_uuid,
                    "name": attr.name,
                    "data_type": attr.data_type,
                    "description": attr.description,
                    "example": attr.example,
                    "confirmation_status": attr.confirmation_status,
                })
        bo_dicts.append({
            "logical_uuid": bo.logical_uuid,
            "name": bo.name,
            "description": bo.description,
            "confirmation_status": bo.confirmation_status,
            "attributes": attr_list,
        })
    return bo_dicts, bo_map


def _backfill_flows(
    db: Session,
    project_id: int,
    workspace_id: int,
    feat_map: dict[int, str],
    bo_map: dict[int, str],
) -> list[dict[str, Any]]:
    """为 Flow 及 FlowStep 回填 UUID 与 workspace_id。"""
    if not _has_table(db, "flows"):
        return []
    flows = db.scalars(
        select(FlowModel).where(
            FlowModel.project_id == project_id,
            or_(FlowModel.workspace_id.is_(None), FlowModel.workspace_id == workspace_id),
        )
    ).all()
    step_map = {}
    has_steps_table = _has_table(db, "flow_steps")
    for f in flows:
        ensure_logical_uuid(f)
        f.workspace_id = workspace_id
        if has_steps_table and hasattr(f, "steps"):
            for st in f.steps:
                ensure_logical_uuid(st)
                st.workspace_id = workspace_id
                step_map[st.id] = st.logical_uuid

    flow_dicts = []
    has_ff_table = _has_table(db, "flow_feature")
    has_fsa_table = _has_table(db, "flow_step_actor")
    has_in_bo_table = _has_table(db, "flow_step_input_business_object")
    has_out_bo_table = _has_table(db, "flow_step_output_business_object")
    has_next_table = _has_table(db, "flow_step_next")

    for f in flows:
        bound_feat_uuids = (
            [feat_map[feat.id] for feat in f.features if feat.id in feat_map]
            if has_ff_table and hasattr(f, "features")
            else []
        )
        step_list = []
        if has_steps_table and hasattr(f, "steps"):
            for st in f.steps:
                st_actor_uuids = [a.logical_uuid for a in st.actors if getattr(a, "logical_uuid", None)] if has_fsa_table and hasattr(st, "actors") else []
                st_in_bo_uuids = [bo_map[bo.id] for bo in st.input_business_objects if bo.id in bo_map] if has_in_bo_table and hasattr(st, "input_business_objects") else []
                st_out_bo_uuids = [bo_map[bo.id] for bo in st.output_business_objects if bo.id in bo_map] if has_out_bo_table and hasattr(st, "output_business_objects") else []
                st_next_uuids = [step_map[nxt.id] for nxt in st.next_steps if nxt.id in step_map] if has_next_table and hasattr(st, "next_steps") else []

                step_list.append({
                    "logical_uuid": st.logical_uuid,
                    "position": st.position,
                    "name": st.name,
                    "description": st.description,
                    "step_type": st.step_type,
                    "confirmation_status": st.confirmation_status,
                    "actor_logical_uuids": st_actor_uuids,
                    "input_business_object_logical_uuids": st_in_bo_uuids,
                    "output_business_object_logical_uuids": st_out_bo_uuids,
                    "next_step_logical_uuids": st_next_uuids,
                })
        flow_dicts.append({
            "logical_uuid": f.logical_uuid,
            "name": f.name,
            "description": f.description,
            "confirmation_status": f.confirmation_status,
            "feature_logical_uuids": bound_feat_uuids,
            "steps": step_list,
        })
    return flow_dicts


def _backfill_scopes(
    db: Session,
    project_id: int,
    workspace_id: int,
    feat_map: dict[int, str],
) -> list[dict[str, Any]]:
    """为 Scope 决策补齐 logical_uuid 与 workspace_id。"""
    if not _has_table(db, "feature_scopes") or not _has_table(db, "features"):
        return []
    scopes = db.scalars(
        select(ScopeModel)
        .join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
        .where(
            FeatureModel.project_id == project_id,
            or_(FeatureModel.workspace_id.is_(None), FeatureModel.workspace_id == workspace_id),
            or_(ScopeModel.workspace_id.is_(None), ScopeModel.workspace_id == workspace_id),
        )
    ).all()
    scope_dicts = []
    for sc in scopes:
        ensure_logical_uuid(sc)
        sc.workspace_id = workspace_id
        feat_uuid = feat_map.get(sc.feature_id)
        scope_dicts.append({
            "logical_uuid": sc.logical_uuid,
            "feature_logical_uuid": feat_uuid,
            "status": sc.status,
            "positive_summary": sc.positive_summary,
            "negative_summary": sc.negative_summary,
            "reason": sc.reason,
            "kano_category": sc.kano_category,
            "kano_category_name": sc.kano_category_name,
            "confirmation_status": sc.confirmation_status,
        })
    return scope_dicts


def _backfill_choice_groups(
    db: Session,
    project_id: int,
    workspace_id: int,
) -> None:
    """为 ChoiceGroup 及 Choice 补齐 UUID 与 workspace_id。"""
    if not _has_table(db, "choice_groups"):
        return
    cgs = db.scalars(
        select(ChoiceGroupModel).where(
            ChoiceGroupModel.project_id == project_id,
            or_(ChoiceGroupModel.workspace_id.is_(None), ChoiceGroupModel.workspace_id == workspace_id),
        )
    ).all()
    has_choices_table = _has_table(db, "choices")
    for cg in cgs:
        ensure_logical_uuid(cg)
        cg.workspace_id = workspace_id
        if has_choices_table and hasattr(cg, "choices"):
            for c in cg.choices:
                ensure_logical_uuid(c)
                c.workspace_id = workspace_id
