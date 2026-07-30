from dataclasses import dataclass, field

from sqlalchemy import insert

from backend.database.model import (
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FlowModel,
    FlowStepModel,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_next_table,
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
    next_steps: list = field(default_factory=list)


async def create_business_objects(
    session,
    project_id: int,
    items: list[dict],
) -> dict:
    models_by_number = {}
    for item in items:
        model = BusinessObjectModel(
            project_id=project_id,
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
) -> None:
    for item in items:
        business_object = models_by_number[item["business_object_number"]]
        for attribute in item.get("business_object_attributes", []):
            example_value = attribute.get(
                "business_object_attribute_example",
                "",
            )
            session.add(
                BusinessObjectAttributeModel(
                    business_object_id=business_object.id,
                    name=attribute["business_object_attribute_name"],
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
) -> list[GeneratedFlowContext]:
    contexts = []
    for payload in payloads:
        model = FlowModel(
            project_id=project_id,
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
) -> int:
    for context in contexts:
        for position, payload in enumerate(
            context.payload.get("flow_steps", []),
            start=1,
        ):
            model = FlowStepModel(
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
) -> FlowAssociationRows:
    rows = FlowAssociationRows()
    for context in contexts:
        rows.features.extend(
            {
                "flow_id": context.model.id,
                "feature_id": feature_id,
            }
            for feature_id in context.payload.get("feature_ids", [])
        )
        _collect_step_association_rows(
            rows,
            context,
            business_objects_by_number,
        )
    return rows


def _collect_step_association_rows(
    rows: FlowAssociationRows,
    context: GeneratedFlowContext,
    business_objects_by_number: dict,
) -> None:
    for payload in context.payload.get("flow_steps", []):
        step = context.steps_by_number[payload["step_number"]]
        rows.actors.extend(
            {"flow_step_id": step.id, "actor_id": actor_id}
            for actor_id in payload.get("actor_ids", [])
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
        rows.next_steps.extend(
            {
                "source_step_id": step.id,
                "target_step_id": context.steps_by_number[number].id,
            }
            for number in payload.get("next_steps", [])
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
        (flow_step_next_table, rows.next_steps),
    ):
        if values:
            await session.execute(insert(table), values)
    await session.flush()


async def persist_flow_generation_draft(draft: dict, session) -> dict:
    project_id = draft["project_id"]
    business_object_items = draft["business_objects"]
    business_objects = await create_business_objects(
        session,
        project_id,
        business_object_items,
    )
    await create_business_object_attributes(
        session,
        business_object_items,
        business_objects,
    )
    flow_contexts = await create_flows(
        session,
        project_id,
        draft["flows"],
    )
    flow_step_count = await create_flow_steps(session, flow_contexts)
    rows = collect_flow_association_rows(
        flow_contexts,
        business_objects,
    )
    await persist_flow_association_rows(session, rows)
    return {
        "project_id": project_id,
        "business_object_count": len(business_object_items),
        "flow_count": len(flow_contexts),
        "flow_step_count": flow_step_count,
        "message": "flows_created",
    }
