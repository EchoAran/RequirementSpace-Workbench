from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.core.perceptrons.slot_fillers.flows_filler import (
    FlowsFiller,
    FlowsFillerInput,
)
from backend.schemas import (
    ActorNode,
    BusinessObjectNode,
    FeatureNode,
    PerceptionKindType,
    PerceptionSlot,
)


@pytest.mark.asyncio
async def test_flows_filler_preserves_two_stage_prompt_pipeline():
    filler = FlowsFiller()
    filler._protected_inputs = lambda input_data: ["protected"]
    filler._llm_handler = SimpleNamespace(
        call_llm=AsyncMock(
            side_effect=[
                "generated-flow",
                '{"flows":[{"flow_name":"Checkout"}]}',
            ]
        )
    )
    input_data = FlowsFillerInput(
        user_requirements="Build checkout",
        actors=[ActorNode(1, "Customer", "Buyer")],
        features=[
            FeatureNode(2, "Checkout", "Pay", actorIds=[1]),
            FeatureNode(3, "Commerce", "Module", childrenIds=[2]),
        ],
        business_objects=[
            BusinessObjectNode(4, "Order", "Purchase order"),
        ],
        flows=[],
        perception_description=PerceptionSlot(
            5,
            PerceptionKindType.FLOW,
            "Checkout has no flow",
        ),
        user_feedback="Prefer a short flow",
    )

    result = await filler.fill(input_data)

    assert result == {"flows": [{"flow_name": "Checkout"}]}
    first_call, second_call = filler._llm_handler.call_llm.await_args_list
    assert '"feature_name": "Checkout"' in first_call.kwargs["prompt"]
    assert '"feature_name": "Commerce"' not in first_call.kwargs["prompt"]
    assert "generated-flow" in second_call.kwargs["prompt"]
    assert first_call.kwargs["query"] == "Prefer a short flow"
    assert second_call.kwargs["query"] == "Prefer a short flow"
    assert first_call.kwargs["protected_inputs"] == ["protected"]
    assert second_call.kwargs["protected_inputs"] == ["protected"]
