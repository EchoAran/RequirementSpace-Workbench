"""
Workspace Model Restoration & Copying Service.
负责从 Commit 快照 state_dict 恢复工作区，或在创建分支时复制现有 BranchWorkspace，
确保物理主键重构、逻辑 UUID 继承以及所有跨实体关系在目标工作区内正确闭合。
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.modules.version_control.application.workspace_lifecycle.rules import (
    copy_rule_aggregate,
    restore_rule_aggregate,
)
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    ChoiceGroupModel,
    ChoiceModel,
    DomainRuleModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)


def restore_workspace_from_state(
    db: Session,
    target_workspace: BranchWorkspaceModel,
    state_dict: dict[str, Any],
) -> None:
    """
    根据规范化的 state_dict 快照字典，在目标 BranchWorkspace 中重建完整的需求模型图谱。
    继承 logical_uuid，生成全新物理 ID，并重构所有关联映射。
    """
    proj_id = target_workspace.project_id
    ws_id = target_workspace.id

    # Workspace metadata belongs to the restored branch state.
    meta = state_dict.get("project_metadata", {})
    target_workspace.user_requirements = meta.get("user_requirements", "")
    target_workspace.kano_status = meta.get("kano_status", "missing")
    target_workspace.unlocked_stages = meta.get("unlocked_stages", "")

    # Actors establish references used by later aggregates.
    actor_uuid_map: dict[str, ActorModel] = {}
    for a_data in state_dict.get("actors", []):
        actor = ActorModel(
            project_id=proj_id,
            workspace_id=ws_id,
            logical_uuid=a_data["logical_uuid"],
            name=a_data.get("name", ""),
            description=a_data.get("description", ""),
            confirmation_status=a_data.get("confirmation_status", "ai_assumption"),
        )
        db.add(actor)
        actor_uuid_map[a_data["logical_uuid"]] = actor
    db.flush()

    restore_rule_aggregate(db, proj_id, ws_id, state_dict)

    # Features resolve actor relationships from the restored mapping.
    feat_uuid_map: dict[str, FeatureModel] = {}
    for f_data in state_dict.get("features", []):
        feat = FeatureModel(
            project_id=proj_id,
            workspace_id=ws_id,
            logical_uuid=f_data["logical_uuid"],
            name=f_data.get("name", ""),
            description=f_data.get("description", ""),
            confirmation_status=f_data.get("confirmation_status", "ai_assumption"),
        )
        db.add(feat)
        feat_uuid_map[f_data["logical_uuid"]] = feat
    db.flush()

    # 绑定 Feature -> Actor 关联 (如果存在 actor_logical_uuids)
    for f_data in state_dict.get("features", []):
        feat = feat_uuid_map.get(f_data["logical_uuid"])
        if feat and "actor_logical_uuids" in f_data:
            bound_actors = [
                actor_uuid_map[a_uuid]
                for a_uuid in f_data["actor_logical_uuids"]
                if a_uuid in actor_uuid_map
            ]
            feat.actors = bound_actors
    db.flush()

    # Feature relations must close over restored features.
    for rel_data in state_dict.get("feature_relations", []):
        p_uuid = rel_data.get("parent_feature_logical_uuid")
        c_uuid = rel_data.get("child_feature_logical_uuid")
        p_feat = feat_uuid_map.get(p_uuid)
        c_feat = feat_uuid_map.get(c_uuid)
        if not p_feat or not c_feat:
            raise ValueError(
                f"Relational closure validation failed: FeatureRelation '{rel_data.get('logical_uuid')}' "
                f"refers to missing parent '{p_uuid}' or child '{c_uuid}'"
            )
        rel = FeatureRelationModel(
            workspace_id=ws_id,
            logical_uuid=rel_data["logical_uuid"],
            parent_feature_id=p_feat.id,
            child_feature_id=c_feat.id,
            position=rel_data.get("position", 0),
        )
        db.add(rel)
    db.flush()

    # Scenarios and criteria must close over restored features and actors.
    for sc_data in state_dict.get("scenarios", []):
        f_uuid = sc_data.get("feature_logical_uuid")
        a_uuid = sc_data.get("actor_logical_uuid")
        feat = feat_uuid_map.get(f_uuid)
        actor = actor_uuid_map.get(a_uuid)

        if not feat or not actor:
            raise ValueError(
                f"Relational closure validation failed: Scenario '{sc_data.get('logical_uuid')}' "
                f"refers to missing feature '{f_uuid}' or actor '{a_uuid}'"
            )

        scenario = ScenarioModel(
            project_id=proj_id,
            workspace_id=ws_id,
            logical_uuid=sc_data["logical_uuid"],
            feature_id=feat.id,
            actor_id=actor.id,
            name=sc_data.get("name", ""),
            content=sc_data.get("content", ""),
            confirmation_status=sc_data.get("confirmation_status", "ai_assumption"),
        )
        db.add(scenario)
        db.flush()

        for ac_data in sc_data.get("acceptance_criteria", []):
            ac = ScenarioAcceptanceCriterionModel(
                workspace_id=ws_id,
                logical_uuid=ac_data["logical_uuid"],
                scenario_id=scenario.id,
                position=ac_data.get("position", 0),
                content=ac_data.get("content", ""),
                confirmation_status=ac_data.get("confirmation_status", "ai_assumption"),
            )
            db.add(ac)
        db.flush()

    # Business objects own their restored attributes.
    bo_uuid_map: dict[str, BusinessObjectModel] = {}
    for bo_data in state_dict.get("business_objects", []):
        bo = BusinessObjectModel(
            project_id=proj_id,
            workspace_id=ws_id,
            logical_uuid=bo_data["logical_uuid"],
            name=bo_data.get("name", ""),
            description=bo_data.get("description", ""),
            confirmation_status=bo_data.get("confirmation_status", "ai_assumption"),
        )
        db.add(bo)
        db.flush()
        bo_uuid_map[bo_data["logical_uuid"]] = bo

        for attr_data in bo_data.get("attributes", []):
            attr = BusinessObjectAttributeModel(
                workspace_id=ws_id,
                logical_uuid=attr_data["logical_uuid"],
                business_object_id=bo.id,
                name=attr_data.get("name", ""),
                data_type=attr_data.get("data_type", ""),
                description=attr_data.get("description", ""),
                example=attr_data.get("example", ""),
                confirmation_status=attr_data.get("confirmation_status", "ai_assumption"),
            )
            db.add(attr)
        db.flush()

    # Flows and steps resolve their scoped entity relationships.
    flow_uuid_map: dict[str, FlowModel] = {}
    step_uuid_map: dict[str, FlowStepModel] = {}
    for fl_data in state_dict.get("flows", []):
        flow = FlowModel(
            project_id=proj_id,
            workspace_id=ws_id,
            logical_uuid=fl_data["logical_uuid"],
            name=fl_data.get("name", ""),
            description=fl_data.get("description", ""),
            confirmation_status=fl_data.get("confirmation_status", "ai_assumption"),
        )
        db.add(flow)
        db.flush()
        flow_uuid_map[fl_data["logical_uuid"]] = flow

        if "feature_logical_uuids" in fl_data:
            bound_feats = [
                feat_uuid_map[f_uuid]
                for f_uuid in fl_data["feature_logical_uuids"]
                if f_uuid in feat_uuid_map
            ]
            flow.features = bound_feats
            db.flush()

        for st_data in fl_data.get("steps", []):
            step = FlowStepModel(
                workspace_id=ws_id,
                logical_uuid=st_data["logical_uuid"],
                flow_id=flow.id,
                position=st_data.get("position", 0),
                name=st_data.get("name", ""),
                description=st_data.get("description", ""),
                step_type=st_data.get("step_type", ""),
                confirmation_status=st_data.get("confirmation_status", "ai_assumption"),
            )
            db.add(step)
            db.flush()
            step_uuid_map[st_data["logical_uuid"]] = step

            if "actor_logical_uuids" in st_data:
                step.actors = [
                    actor_uuid_map[a_uuid]
                    for a_uuid in st_data["actor_logical_uuids"]
                    if a_uuid in actor_uuid_map
                ]
            if "input_business_object_logical_uuids" in st_data:
                step.input_business_objects = [
                    bo_uuid_map[b_uuid]
                    for b_uuid in st_data["input_business_object_logical_uuids"]
                    if b_uuid in bo_uuid_map
                ]
            if "output_business_object_logical_uuids" in st_data:
                step.output_business_objects = [
                    bo_uuid_map[b_uuid]
                    for b_uuid in st_data["output_business_object_logical_uuids"]
                    if b_uuid in bo_uuid_map
                ]
            db.flush()

    # Transitions resolve only against steps in the restored flow.
    for fl_data in state_dict.get("flows", []):
        flow = flow_uuid_map.get(fl_data.get("logical_uuid"))
        if not flow:
            continue
        for tr_data in fl_data.get("transitions", []):
            source_step = step_uuid_map.get(tr_data.get("source_step_logical_uuid"))
            target_step = step_uuid_map.get(tr_data.get("target_step_logical_uuid"))
            if source_step is None or target_step is None:
                raise ValueError(
                    f"Flow transition '{tr_data.get('logical_uuid')}' refers "
                    "to a missing step endpoint."
                )
            new_trans = FlowTransitionModel(
                workspace_id=ws_id,
                project_id=proj_id,
                flow_id=flow.id,
                logical_uuid=tr_data["logical_uuid"],
                source_step_id=source_step.id,
                target_step_id=target_step.id,
                label=tr_data.get("label", ""),
                condition_text=tr_data.get("condition_text", ""),
                is_default=tr_data.get("is_default", False),
                position=tr_data.get("position", 0),
                semantic_tags=tr_data.get("semantic_tags", []),
                origin=tr_data.get("origin", "manual"),
                confirmation_status=tr_data.get(
                    "confirmation_status", "confirmed"
                ),
            )
            db.add(new_trans)
    db.flush()

    # Scope decisions close over restored features.
    for scp_data in state_dict.get("scopes", []):
        feat = feat_uuid_map.get(scp_data.get("feature_logical_uuid"))
        if feat:
            scope = ScopeModel(
                workspace_id=ws_id,
                logical_uuid=scp_data["logical_uuid"],
                feature_id=feat.id,
                status=scp_data.get("status", ""),
                positive_summary=scp_data.get("positive_summary"),
                negative_summary=scp_data.get("negative_summary"),
                reason=scp_data.get("reason", ""),
                kano_category=scp_data.get("kano_category"),
                kano_category_name=scp_data.get("kano_category_name"),
                confirmation_status=scp_data.get("confirmation_status", "ai_assumption"),
            )
            db.add(scope)
    db.flush()


def copy_workspace(
    db: Session,
    source_workspace: BranchWorkspaceModel,
    target_workspace: BranchWorkspaceModel,
) -> None:
    """
    将源 BranchWorkspace 中的建模记录完全深拷贝到目标 BranchWorkspace 中。
    保持所有实体的 logical_uuid 继承性，重新绑定所有内部引用。
    """
    proj_id = target_workspace.project_id
    src_ws_id = source_workspace.id
    tgt_ws_id = target_workspace.id

    target_workspace.user_requirements = source_workspace.user_requirements or ""
    target_workspace.kano_status = source_workspace.kano_status or "missing"
    target_workspace.unlocked_stages = source_workspace.unlocked_stages or ""

    # Actors are copied before dependent entities.
    src_actors = db.scalars(select(ActorModel).where(ActorModel.workspace_id == src_ws_id)).all()
    actor_id_map: dict[int, ActorModel] = {}
    for a in src_actors:
        new_a = ActorModel(
            project_id=proj_id,
            workspace_id=tgt_ws_id,
            logical_uuid=a.logical_uuid,
            name=a.name,
            description=a.description,
            confirmation_status=a.confirmation_status,
        )
        db.add(new_a)
        db.flush()
        actor_id_map[a.id] = new_a

    # Features retain logical identity across workspace copies.
    src_features = db.scalars(select(FeatureModel).where(FeatureModel.workspace_id == src_ws_id)).all()
    feat_id_map: dict[int, FeatureModel] = {}
    for f in src_features:
        new_f = FeatureModel(
            project_id=proj_id,
            workspace_id=tgt_ws_id,
            logical_uuid=f.logical_uuid,
            name=f.name,
            description=f.description,
            confirmation_status=f.confirmation_status,
        )
        db.add(new_f)
        db.flush()
        feat_id_map[f.id] = new_f

        if hasattr(f, "actors") and f.actors:
            new_f.actors = [actor_id_map[a.id] for a in f.actors if a.id in actor_id_map]
            db.flush()

    # Feature relations use the copied feature identifiers.
    src_rels = db.scalars(select(FeatureRelationModel).where(FeatureRelationModel.workspace_id == src_ws_id)).all()
    for rel in src_rels:
        p_feat = feat_id_map.get(rel.parent_feature_id)
        c_feat = feat_id_map.get(rel.child_feature_id)
        if p_feat and c_feat:
            new_rel = FeatureRelationModel(
                workspace_id=tgt_ws_id,
                logical_uuid=rel.logical_uuid,
                parent_feature_id=p_feat.id,
                child_feature_id=c_feat.id,
                position=rel.position,
            )
            db.add(new_rel)
    db.flush()

    # Scenarios and criteria retain their logical identities.
    src_scenarios = db.scalars(select(ScenarioModel).where(ScenarioModel.workspace_id == src_ws_id)).all()
    for sc in src_scenarios:
        p_feat = feat_id_map.get(sc.feature_id)
        p_actor = actor_id_map.get(sc.actor_id)
        if p_feat and p_actor:
            new_sc = ScenarioModel(
                project_id=proj_id,
                workspace_id=tgt_ws_id,
                logical_uuid=sc.logical_uuid,
                feature_id=p_feat.id,
                actor_id=p_actor.id,
                name=sc.name,
                content=sc.content,
                confirmation_status=sc.confirmation_status,
            )
            db.add(new_sc)
            db.flush()

            if hasattr(sc, "acceptance_criteria") and sc.acceptance_criteria:
                for ac in sc.acceptance_criteria:
                    new_ac = ScenarioAcceptanceCriterionModel(
                        workspace_id=tgt_ws_id,
                        logical_uuid=ac.logical_uuid,
                        scenario_id=new_sc.id,
                        position=ac.position,
                        content=ac.content,
                        confirmation_status=ac.confirmation_status,
                    )
                    db.add(new_ac)
                db.flush()

    # Business objects and attributes are copied as one aggregate.
    src_bos = db.scalars(select(BusinessObjectModel).where(BusinessObjectModel.workspace_id == src_ws_id)).all()
    bo_id_map: dict[int, BusinessObjectModel] = {}
    for bo in src_bos:
        new_bo = BusinessObjectModel(
            project_id=proj_id,
            workspace_id=tgt_ws_id,
            logical_uuid=bo.logical_uuid,
            name=bo.name,
            description=bo.description,
            confirmation_status=bo.confirmation_status,
        )
        db.add(new_bo)
        db.flush()
        bo_id_map[bo.id] = new_bo

        if hasattr(bo, "attributes") and bo.attributes:
            for attr in bo.attributes:
                new_attr = BusinessObjectAttributeModel(
                    workspace_id=tgt_ws_id,
                    logical_uuid=attr.logical_uuid,
                    business_object_id=new_bo.id,
                    name=attr.name,
                    data_type=attr.data_type,
                    description=attr.description,
                    example=attr.example,
                    confirmation_status=attr.confirmation_status,
                )
                db.add(new_attr)
            db.flush()

    # Flow aggregates are copied with their steps and transitions.
    src_flows = db.scalars(select(FlowModel).where(FlowModel.workspace_id == src_ws_id)).all()
    flow_id_map: dict[int, FlowModel] = {}
    step_id_map: dict[int, FlowStepModel] = {}
    for fl in src_flows:
        new_fl = FlowModel(
            project_id=proj_id,
            workspace_id=tgt_ws_id,
            logical_uuid=fl.logical_uuid,
            name=fl.name,
            description=fl.description,
            confirmation_status=fl.confirmation_status,
        )
        db.add(new_fl)
        db.flush()
        flow_id_map[fl.id] = new_fl

        if hasattr(fl, "features") and fl.features:
            new_fl.features = [feat_id_map[f.id] for f in fl.features if f.id in feat_id_map]
            db.flush()

        if hasattr(fl, "steps") and fl.steps:
            for st in fl.steps:
                new_st = FlowStepModel(
                    workspace_id=tgt_ws_id,
                    logical_uuid=st.logical_uuid,
                    flow_id=new_fl.id,
                    position=st.position,
                    name=st.name,
                    description=st.description,
                    step_type=st.step_type,
                    confirmation_status=st.confirmation_status,
                )
                db.add(new_st)
                db.flush()
                step_id_map[st.id] = new_st

                if hasattr(st, "actors") and st.actors:
                    new_st.actors = [actor_id_map[a.id] for a in st.actors if a.id in actor_id_map]
                if hasattr(st, "input_business_objects") and st.input_business_objects:
                    new_st.input_business_objects = [bo_id_map[b.id] for b in st.input_business_objects if b.id in bo_id_map]
                if hasattr(st, "output_business_objects") and st.output_business_objects:
                    new_st.output_business_objects = [bo_id_map[b.id] for b in st.output_business_objects if b.id in bo_id_map]
                db.flush()

    # 复制 FlowTransition 边
    for fl in src_flows:
        new_fl = flow_id_map.get(fl.id)
        if new_fl is None:
            raise ValueError(
                f"Flow '{fl.logical_uuid}' was not copied into the target workspace."
            )
        src_transitions = db.scalars(
            select(FlowTransitionModel).where(FlowTransitionModel.flow_id == fl.id)
        ).all()
        for tr in src_transitions:
            new_source = step_id_map.get(tr.source_step_id)
            new_target = step_id_map.get(tr.target_step_id)
            if new_source is None or new_target is None:
                raise ValueError(
                    f"Flow transition '{tr.logical_uuid}' has an endpoint "
                    "outside the source workspace flow."
                )
            new_trans = FlowTransitionModel(
                workspace_id=tgt_ws_id,
                project_id=proj_id,
                flow_id=new_fl.id,
                logical_uuid=tr.logical_uuid,
                source_step_id=new_source.id,
                target_step_id=new_target.id,
                label=tr.label,
                condition_text=tr.condition_text,
                is_default=tr.is_default,
                position=tr.position,
                semantic_tags=list(tr.semantic_tags or []),
                origin=tr.origin,
                confirmation_status=tr.confirmation_status,
            )
            db.add(new_trans)
    db.flush()

    copy_rule_aggregate(db, proj_id, src_ws_id, tgt_ws_id)

    # Scope decisions resolve the copied feature identifiers.
    src_scopes = db.scalars(select(ScopeModel).where(ScopeModel.workspace_id == src_ws_id)).all()
    for scp in src_scopes:
        p_feat = feat_id_map.get(scp.feature_id)
        if p_feat:
            new_scp = ScopeModel(
                workspace_id=tgt_ws_id,
                logical_uuid=scp.logical_uuid,
                feature_id=p_feat.id,
                status=scp.status,
                positive_summary=scp.positive_summary,
                negative_summary=scp.negative_summary,
                reason=scp.reason,
                kano_category=scp.kano_category,
                kano_category_name=scp.kano_category_name,
                confirmation_status=scp.confirmation_status,
            )
            db.add(new_scp)
    db.flush()


# 合并写回前需清理的实体表顺序：子行先行，父行随后（junction 表无 workspace_id，必须显式删）。
# 顺序依赖：junction 边引用步骤/功能/业务对象/参与者，子对象引用父对象。
_SCRUB_ENTITY_MODELS = (
    RuleLinkModel,
    FlowTransitionModel,
    FlowStepModel,
    FeatureRelationModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectAttributeModel,
    ScopeModel,
    ScenarioModel,
    FlowModel,
    DomainRuleModel,
    BusinessObjectModel,
    FeatureModel,
    ActorModel,
)


def scrub_workspace(db: Session, workspace_id: int) -> None:
    """清空目标工作区的全部需求模型行，为 restore_workspace_from_state 的全量重建腾出唯一键空间。

    说明：restore_workspace_from_state 只新增行，不清除旧行；合并写回前必须先清理。
    junction 表无 workspace_id 列，只能经关系端点 id 过滤；SQLite 测试不强制 FK，
    因此显式删除 junction 行，避免孤立边残留。ChoiceGroup/Choice 属决策工作流产物，
    不在合并状态载荷内，故合并写回时一并清除。
    """
    # Physical identifiers constrain junction-table cleanup to this workspace.
    step_ids = set(db.scalars(
        select(FlowStepModel.id).where(FlowStepModel.workspace_id == workspace_id)
    ).all())
    feature_ids = set(db.scalars(
        select(FeatureModel.id).where(FeatureModel.workspace_id == workspace_id)
    ).all())
    actor_ids = set(db.scalars(
        select(ActorModel.id).where(ActorModel.workspace_id == workspace_id)
    ).all())
    flow_ids = set(db.scalars(
        select(FlowModel.id).where(FlowModel.workspace_id == workspace_id)
    ).all())

    # Junction rows are removed before the entities they reference.
    if step_ids:
        db.execute(flow_step_actor_table.delete().where(flow_step_actor_table.c.flow_step_id.in_(step_ids)))
        db.execute(flow_step_input_business_object_table.delete().where(
            flow_step_input_business_object_table.c.flow_step_id.in_(step_ids)
        ))
        db.execute(flow_step_output_business_object_table.delete().where(
            flow_step_output_business_object_table.c.flow_step_id.in_(step_ids)
        ))
    # feature_actor / flow_feature 两端都可能属于本工作区：用任一端的 in_ 条件删除。
    db.execute(feature_actor_table.delete().where(
        feature_actor_table.c.feature_id.in_(feature_ids)
    ))
    db.execute(feature_actor_table.delete().where(
        feature_actor_table.c.actor_id.in_(actor_ids)
    ))
    db.execute(flow_feature_table.delete().where(
        flow_feature_table.c.flow_id.in_(flow_ids)
    ))
    db.execute(flow_feature_table.delete().where(
        flow_feature_table.c.feature_id.in_(feature_ids)
    ))

    # Entity rows are scoped by workspace identifier.
    for model in _SCRUB_ENTITY_MODELS:
        db.execute(model.__table__.delete().where(model.workspace_id == workspace_id))

    # Decision artifacts are transient and are not part of the restored state payload.
    choice_ids = set(db.scalars(
        select(ChoiceGroupModel.id).where(ChoiceGroupModel.workspace_id == workspace_id)
    ).all())
    if choice_ids:
        db.execute(ChoiceModel.__table__.delete().where(ChoiceModel.choice_group_id.in_(choice_ids)))
    db.execute(ChoiceGroupModel.__table__.delete().where(ChoiceGroupModel.workspace_id == workspace_id))

    db.flush()
