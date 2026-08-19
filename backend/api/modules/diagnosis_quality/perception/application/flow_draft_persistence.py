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
class FlowContext:
    payload: dict
    model: FlowModel
    steps_by_number: dict = field(default_factory=dict)


@dataclass
class AssociationRows:
    features: list = field(default_factory=list)
    actors: list = field(default_factory=list)
    input_business_objects: list = field(default_factory=list)
    output_business_objects: list = field(default_factory=list)
    next_steps: list = field(default_factory=list)


async def create_missing_business_objects(
    session,
    project_id: int,
    items: list[dict],
    workspace_id: int | None = None,
) -> tuple[dict, int]:
    model_ids_by_draft_id = {}
    new_items = []
    for item in items:
        draft_id = item["business_object_id"]
        if item["is_existing"]:
            model_ids_by_draft_id[draft_id] = draft_id
            continue
        model = BusinessObjectModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=item["business_object_name"],
            description=item["business_object_description"],
            confirmation_status="ai_assumption",
        )
        session.add(model)
        new_items.append((item, model))
    await session.flush()

    for item, model in new_items:
        model_ids_by_draft_id[item["business_object_id"]] = model.id
        for attribute in item.get("business_object_attributes", []):
            session.add(
                BusinessObjectAttributeModel(
                    workspace_id=workspace_id,
                    business_object_id=model.id,
                    name=attribute["business_object_attribute_name"],
                    description=attribute[
                        "business_object_attribute_description"
                    ],
                    data_type=attribute["business_object_attribute_type"],
                    example=attribute[
                        "business_object_attribute_example"
                    ],
                )
            )
    await session.flush()
    return model_ids_by_draft_id, len(new_items)


async def create_flow_models(
    session,
    project_id: int,
    payloads: list[dict],
    workspace_id: int | None = None,
) -> list[FlowContext]:
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
        contexts.append(FlowContext(payload, model))
    await session.flush()
    return contexts


async def create_flow_step_models(
    session,
    contexts: list[FlowContext],
    workspace_id: int | None = None,
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


def collect_association_rows(
    contexts: list[FlowContext],
    business_object_ids: dict,
) -> AssociationRows:
    rows = AssociationRows()
    for context in contexts:
        rows.features.extend(
            {
                "flow_id": context.model.id,
                "feature_id": feature_id,
            }
            for feature_id in context.payload.get("feature_ids", [])
        )
        collect_step_rows(rows, context, business_object_ids)
    return rows


def collect_step_rows(
    rows: AssociationRows,
    context: FlowContext,
    business_object_ids: dict,
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
                "business_object_id": business_object_ids.get(
                    business_object_id,
                    business_object_id,
                ),
            }
            for business_object_id in payload.get(
                "input_business_object_ids",
                [],
            )
        )
        rows.output_business_objects.extend(
            {
                "flow_step_id": step.id,
                "business_object_id": business_object_ids.get(
                    business_object_id,
                    business_object_id,
                ),
            }
            for business_object_id in payload.get(
                "output_business_object_ids",
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


async def persist_association_rows(
    session,
    rows: AssociationRows,
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


async def persist_flow_draft(draft: dict, session, workspace_id: int | None = None) -> dict:
    project_id = draft["project_id"]
    business_object_ids, business_object_count = (
        await create_missing_business_objects(
            session,
            project_id,
            draft["business_objects"],
            workspace_id=workspace_id,
        )
    )
    flow_contexts = await create_flow_models(
        session,
        project_id,
        draft["flows"],
        workspace_id=workspace_id,
    )
    flow_step_count = await create_flow_step_models(
        session,
        flow_contexts,
        workspace_id=workspace_id,
    )
    rows = collect_association_rows(
        flow_contexts,
        business_object_ids,
    )
    await persist_association_rows(session, rows)
    flow_count = len(flow_contexts)
    return {
        "project_id": project_id,
        "filler_kind": "flow",
        "created_count": flow_count + business_object_count,
        "business_object_count": business_object_count,
        "flow_count": flow_count,
        "flow_step_count": flow_step_count,
        "message": "perception_slot_filled",
    }
