import uuid
from dataclasses import dataclass, field

from sqlalchemy import insert, select

from backend.database.model import (
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    DomainRuleModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
    RuleLinkPurpose,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)


@dataclass
class GeneratedFlowContext:
    payload: dict
    model: FlowModel
    steps_by_number: dict = field(default_factory=dict)


@dataclass
class FlowAssociationRows:
    features: list = field(default_factory=list)
    actors: list = field(default_factory=list)
    input_business_objects: list = field(default_factory=list)
    output_business_objects: list = field(default_factory=list)
    transitions: list[FlowTransitionModel] = field(default_factory=list)
    rule_links: list[RuleLinkModel] = field(default_factory=list)


async def create_business_objects(
    session,
    project_id: int,
    items: list[dict],
    workspace_id: int,
) -> dict:
    models_by_number = {}
    for item in items:
        obj_id = item.get("object_id") or item.get("id")
        logical_uuid = item.get("logical_uuid")
        existing_model = None

        if obj_id is not None:
            stmt = select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.id == int(obj_id),
            )
            stmt = stmt.where(BusinessObjectModel.workspace_id == workspace_id)
            res = await session.execute(stmt)
            existing_model = res.scalar_one_or_none()
            if existing_model is None:
                raise ValueError(f"business_object_not_found: id {obj_id}")
        elif logical_uuid is not None:
            stmt = select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.logical_uuid == str(logical_uuid),
            )
            stmt = stmt.where(BusinessObjectModel.workspace_id == workspace_id)
            res = await session.execute(stmt)
            existing_model = res.scalar_one_or_none()
            if existing_model is None:
                raise ValueError(
                    f"business_object_not_found: logical_uuid {logical_uuid}"
                )

        if existing_model is not None:
            # Reused existing business object (strictly NOT duplicating it)
            # NOTE: Never auto-merge by name alone without explicit ID or logical UUID!
            models_by_number[item["business_object_number"]] = existing_model
        else:
            model = BusinessObjectModel(
                project_id=project_id,
                workspace_id=workspace_id,
                name=item["business_object_name"],
                description=item["business_object_description"],
                confirmation_status="ai_assumption",
            )
            session.add(model)
            models_by_number[item["business_object_number"]] = model

    await session.flush()
    return models_by_number


async def create_business_object_attributes(
    session,
    items: list[dict],
    models_by_number: dict,
    workspace_id: int,
) -> None:
    for item in items:
        business_object = models_by_number[item["business_object_number"]]
        stmt = select(BusinessObjectAttributeModel.name).where(
            BusinessObjectAttributeModel.business_object_id == business_object.id
        )
        stmt = stmt.where(
            BusinessObjectAttributeModel.workspace_id == workspace_id
        )
        res = await session.execute(stmt)
        existing_attr_names = set(res.scalars().all())

        for attribute in item.get("business_object_attributes", []):
            attr_name = attribute["business_object_attribute_name"]
            if attr_name in existing_attr_names:
                continue
            example_value = attribute.get(
                "business_object_attribute_example",
                "",
            )
            session.add(
                BusinessObjectAttributeModel(
                    workspace_id=workspace_id,
                    business_object_id=business_object.id,
                    name=attr_name,
                    description=attribute[
                        "business_object_attribute_description"
                    ],
                    data_type=attribute["business_object_attribute_type"],
                    example=str(
                        "" if example_value is None else example_value
                    ),
                )
            )
    await session.flush()


async def create_flows(
    session,
    project_id: int,
    payloads: list[dict],
    workspace_id: int,
) -> list[GeneratedFlowContext]:
    contexts = []
    for payload in payloads:
        model = FlowModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=payload["flow_name"],
            description=payload["flow_description"],
            confirmation_status="ai_assumption",
        )
        session.add(model)
        contexts.append(GeneratedFlowContext(payload, model))
    await session.flush()
    return contexts


async def create_flow_steps(
    session,
    contexts: list[GeneratedFlowContext],
    workspace_id: int,
) -> int:
    for context in contexts:
        for position, payload in enumerate(
            context.payload.get("flow_steps", []),
            start=1,
        ):
            model = FlowStepModel(
                workspace_id=workspace_id,
                flow_id=context.model.id,
                position=position,
                name=payload["step_name"],
                description=payload["step_description"],
                step_type=payload["step_type"],
            )
            session.add(model)
            context.steps_by_number[payload["step_number"]] = model
    await session.flush()
    return sum(len(context.steps_by_number) for context in contexts)


def collect_flow_association_rows(
    contexts: list[GeneratedFlowContext],
    business_objects_by_number: dict,
    valid_actor_ids: set[int] | None = None,
    rules_by_uuid: dict[str, DomainRuleModel] | None = None,
) -> FlowAssociationRows:
    rows = FlowAssociationRows()
    def collect_rules(payload, target_kind, target_uuid, context):
        for ref in set(payload.get("rule_refs") or []):
            rule = (rules_by_uuid or {}).get(ref)
            if rule is None:
                raise ValueError(f"invalid_{target_kind}_rule_reference: {ref}")
            rows.rule_links.append(RuleLinkModel(
                project_id=context.model.project_id, workspace_id=context.model.workspace_id,
                rule_id=rule.id, target_kind=target_kind, target_logical_uuid=target_uuid,
                link_purpose=RuleLinkPurpose.APPLIES_TO.value, context_text="",
            ))

    for context in contexts:
        collect_rules(context.payload, "flow", context.model.logical_uuid, context)
        for step_payload in context.payload.get("flow_steps", []):
            step = context.steps_by_number[step_payload["step_number"]]
            collect_rules(step_payload, "flow_step", step.logical_uuid, context)
        rows.features.extend(
            {
                "flow_id": context.model.id,
                "feature_id": feature_id,
            }
            for feature_id in context.payload.get("feature_ids", [])
        )
        seen_default_sources: set[int] = set()
        for pos, t in enumerate(context.payload.get("transitions", [])):
            if isinstance(t, dict):
                src_num = t.get("source_step_number")
                tgt_num = t.get("target_step_number")
                cond = t.get("condition_text") or ""
                label = t.get("label") or ""
                is_def = t.get("is_default", False)
                tags = t.get("semantic_tags") or []
            else:
                continue
            src_step = context.steps_by_number.get(src_num)
            tgt_step = context.steps_by_number.get(tgt_num)
            if src_step and tgt_step:
                if is_def:
                    if src_step.id in seen_default_sources:
                        raise ValueError(
                            f"duplicate_default_transition: Step {src_step.id} has multiple default transitions"
                        )
                    seen_default_sources.add(src_step.id)
                transition_uuid = str(uuid.uuid4())
                transition_model = FlowTransitionModel(
                    logical_uuid=transition_uuid,
                    project_id=context.model.project_id,
                    workspace_id=context.model.workspace_id,
                    flow_id=context.model.id,
                    source_step_id=src_step.id,
                    target_step_id=tgt_step.id,
                    label=label,
                    condition_text=cond,
                    is_default=is_def,
                    position=pos,
                    semantic_tags=tags,
                    origin="ai_generated",
                    confirmation_status="confirmed",
                )
                rows.transitions.append(transition_model)

                collect_rules(t, "flow_transition", transition_model.logical_uuid, context)
        _collect_step_association_rows(
            rows,
            context,
            business_objects_by_number,
            valid_actor_ids,
        )
    return rows


def _collect_step_association_rows(
    rows: FlowAssociationRows,
    context: GeneratedFlowContext,
    business_objects_by_number: dict,
    valid_actor_ids: set[int] | None = None,
) -> None:
    for payload in context.payload.get("flow_steps", []):
        step = context.steps_by_number[payload["step_number"]]
        actor_ids = payload.get("actor_ids", [])
        if valid_actor_ids is not None:
            actor_ids = [aid for aid in actor_ids if aid in valid_actor_ids]
        rows.actors.extend(
            {"flow_step_id": step.id, "actor_id": actor_id}
            for actor_id in actor_ids
        )
        rows.input_business_objects.extend(
            {
                "flow_step_id": step.id,
                "business_object_id": business_objects_by_number[number].id,
            }
            for number in payload.get(
                "input_business_object_numbers",
                [],
            )
        )
        rows.output_business_objects.extend(
            {
                "flow_step_id": step.id,
                "business_object_id": business_objects_by_number[number].id,
            }
            for number in payload.get(
                "output_business_object_numbers",
                [],
            )
        )


async def persist_flow_association_rows(
    session,
    rows: FlowAssociationRows,
) -> None:
    for table, values in (
        (flow_feature_table, rows.features),
        (flow_step_actor_table, rows.actors),
        (
            flow_step_input_business_object_table,
            rows.input_business_objects,
        ),
        (
            flow_step_output_business_object_table,
            rows.output_business_objects,
        ),
    ):
        if values:
            await session.execute(insert(table), values)
    if rows.transitions:
        session.add_all(rows.transitions)
    if rows.rule_links:
        session.add_all(rows.rule_links)
    await session.flush()


async def persist_flow_generation_draft(
    draft: dict,
    session,
    workspace_id: int,
) -> dict:
    from backend.database.model import ActorModel
    project_id = draft["project_id"]
    business_object_items = draft["business_objects"]
    business_objects = await create_business_objects(
        session,
        project_id,
        business_object_items,
        workspace_id=workspace_id,
    )
    await create_business_object_attributes(
        session,
        business_object_items,
        business_objects,
        workspace_id=workspace_id,
    )
    flow_contexts = await create_flows(
        session,
        project_id,
        draft["flows"],
        workspace_id=workspace_id,
    )
    flow_step_count = await create_flow_steps(
        session,
        flow_contexts,
        workspace_id=workspace_id,
    )
    actor_stmt = select(ActorModel.id).where(ActorModel.project_id == project_id)
    actor_stmt = actor_stmt.where(ActorModel.workspace_id == workspace_id)
    valid_actor_ids = set((await session.execute(actor_stmt)).scalars().all())

    rule_stmt = select(DomainRuleModel).where(DomainRuleModel.project_id == project_id)
    rule_stmt = rule_stmt.where(DomainRuleModel.workspace_id == workspace_id)
    rule_models = (await session.execute(rule_stmt)).scalars().all()
    rules_by_uuid = {r.logical_uuid: r for r in rule_models}

    rows = collect_flow_association_rows(
        flow_contexts,
        business_objects,
        valid_actor_ids=valid_actor_ids,
        rules_by_uuid=rules_by_uuid,
    )
    await persist_flow_association_rows(session, rows)
    return {
        "project_id": project_id,
        "business_object_count": len(business_object_items),
        "flow_count": len(flow_contexts),
        "flow_step_count": flow_step_count,
        "message": "flows_created",
    }
