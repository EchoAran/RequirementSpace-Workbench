"""
Workspace Model Restoration & Copying Service.
负责从 Commit 快照 state_dict 恢复工作区，或在创建分支时复制现有 BranchWorkspace，
确保物理主键重构、逻辑 UUID 继承以及所有跨实体关系在目标工作区内正确闭合。
"""
from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select

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
    ChoiceGroupModel,
    ChoiceModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
    flow_step_next_table,
)


def restore_workspace_from_state(
    db: Session,
    target_workspace: BranchWorkspaceModel,
    state_dict: Dict[str, Any],
) -> None:
    """
    根据规范化的 state_dict 快照字典，在目标 BranchWorkspace 中重建完整的需求模型图谱。
    继承 logical_uuid，生成全新物理 ID，并重构所有关联映射。
    """
    proj_id = target_workspace.project_id
    ws_id = target_workspace.id

    # 0. 更新 BranchWorkspace 级元数据
    meta = state_dict.get("project_metadata", {})
    target_workspace.user_requirements = meta.get("user_requirements", "")
    target_workspace.kano_status = meta.get("kano_status", "missing")
    target_workspace.unlocked_stages = meta.get("unlocked_stages", "")

    # 1. 恢复 Actors
    actor_uuid_map: Dict[str, ActorModel] = {}
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

    # 2. 恢复 Features
    feat_uuid_map: Dict[str, FeatureModel] = {}
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

    # 3. 恢复 FeatureRelations 并校验闭合
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

    # 4. 恢复 Scenarios & AcceptanceCriteria 并校验闭合
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

    # 5. 恢复 BusinessObjects & Attributes
    bo_uuid_map: Dict[str, BusinessObjectModel] = {}
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

    # 6. 恢复 Flows & Steps
    step_uuid_map: Dict[str, FlowStepModel] = {}
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

    # 绑定 FlowStep -> NextSteps 依赖
    for fl_data in state_dict.get("flows", []):
        for st_data in fl_data.get("steps", []):
            step = step_uuid_map.get(st_data["logical_uuid"])
            if step and "next_step_logical_uuids" in st_data:
                step.next_steps = [
                    step_uuid_map[nxt_uuid]
                    for nxt_uuid in st_data["next_step_logical_uuids"]
                    if nxt_uuid in step_uuid_map
                ]
    db.flush()

    # 7. 恢复 Scope Decisions
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

    # 1. 复制 Actors
    src_actors = db.scalars(select(ActorModel).where(ActorModel.workspace_id == src_ws_id)).all()
    actor_id_map: Dict[int, ActorModel] = {}
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

    # 2. 复制 Features
    src_features = db.scalars(select(FeatureModel).where(FeatureModel.workspace_id == src_ws_id)).all()
    feat_id_map: Dict[int, FeatureModel] = {}
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

    # 3. 复制 FeatureRelations
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

    # 4. 复制 Scenarios & AC
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

    # 5. 复制 BusinessObjects & Attributes
    src_bos = db.scalars(select(BusinessObjectModel).where(BusinessObjectModel.workspace_id == src_ws_id)).all()
    bo_id_map: Dict[int, BusinessObjectModel] = {}
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

    # 6. 复制 Flows & Steps
    src_flows = db.scalars(select(FlowModel).where(FlowModel.workspace_id == src_ws_id)).all()
    step_id_map: Dict[int, FlowStepModel] = {}
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

    # 复制 FlowStep Next 边
    for fl in src_flows:
        if hasattr(fl, "steps") and fl.steps:
            for st in fl.steps:
                new_st = step_id_map.get(st.id)
                if new_st and hasattr(st, "next_steps") and st.next_steps:
                    new_st.next_steps = [step_id_map[nxt.id] for nxt in st.next_steps if nxt.id in step_id_map]
    db.flush()

    # 7. 复制 Scope Decisions
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
    FlowStepModel,
    FeatureRelationModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectAttributeModel,
    ScopeModel,
    ScenarioModel,
    FlowModel,
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
    # 1. 读取本工作区各实体的物理主键，用于 junction 行过滤。
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

    # 2. junction 表先行（引用实体 id，需先删）。集合为空时 in_() 生成永假条件，无需特判。
    if step_ids:
        db.execute(flow_step_next_table.delete().where(
            (flow_step_next_table.c.source_step_id.in_(step_ids))
            | (flow_step_next_table.c.target_step_id.in_(step_ids))
        ))
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

    # 3. 实体行按 workspace_id 删除。
    for model in _SCRUB_ENTITY_MODELS:
        db.execute(model.__table__.delete().where(model.workspace_id == workspace_id))

    # 4. 决策工作流产物一并清空（不属于合并状态载荷，重建时由 restore 重建为空）。
    choice_ids = set(db.scalars(
        select(ChoiceGroupModel.id).where(ChoiceGroupModel.workspace_id == workspace_id)
    ).all())
    if choice_ids:
        db.execute(ChoiceModel.__table__.delete().where(ChoiceModel.choice_group_id.in_(choice_ids)))
    db.execute(ChoiceGroupModel.__table__.delete().where(ChoiceGroupModel.workspace_id == workspace_id))

    db.flush()
