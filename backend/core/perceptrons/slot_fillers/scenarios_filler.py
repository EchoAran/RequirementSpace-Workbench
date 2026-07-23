from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.slot_fillers.prompts.scenarios_fill_agent import scenarios_fill_prompt
from backend.core.perceptrons.slot_fillers.base_filler import BaseFiller, FillerInput
from backend.schemas import ActorNode, PerceptionSlot, FeatureNode, ScenarioNode


# 为场景补充器定义专属的输入类型
@dataclass
class ScenariosFillerInput(FillerInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]
    perception_description: PerceptionSlot
    user_feedback: str | None = None

class ScenariosFiller(BaseFiller[ScenariosFillerInput]):
    async def fill(self, input_data: ScenariosFillerInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        actor_ = ActorNode.schema(
            only=("actorName", "actorDescription")
        ).dumps(
            input_data.actor,
            indent=2,
            ensure_ascii=False
        )

        feature_ = FeatureNode.schema(
            only=("featureName", "featureDescription")
        ).dumps(
            input_data.feature,
            indent=2,
            ensure_ascii=False
        )

        scenarios_payload = ScenarioNode.schema(
            many=True,
            only=("scenarioName", "scenarioContent"),
        ).dump(input_data.scenarios)

        scenarios_ = json.dumps(
            {"scenarios": scenarios_payload},
            ensure_ascii=False,
            indent=2,
        )

        perception_description_payload = PerceptionSlot.schema(
            only=("perceptionDescription",)
        ).dump(input_data.perception_description)
        perception_description_ = json.dumps(
            perception_description_payload,
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=scenarios_fill_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{actor}}", f"{actor_}").replace(
                "{{feature}}", f"{feature_}").replace(
                "{{scenarios}}", f"{scenarios_}").replace(
                "{{perception_description}}", f"{perception_description_}"
            ),
            query=input_data.user_feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
