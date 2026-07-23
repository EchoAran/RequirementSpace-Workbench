from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.slot_fillers.prompts.features_fill_agent import features_fill_prompt
from backend.core.perceptrons.slot_fillers.base_filler import BaseFiller, FillerInput
from backend.schemas import PerceptionSlot, FeatureNode


# 为功能补充器定义专属的输入类型
@dataclass
class FeaturesFillerInput(FillerInput):
    user_requirements: str
    features: List[FeatureNode]
    perception_description: PerceptionSlot
    user_feedback: str | None = None

class FeaturesFiller(BaseFiller[FeaturesFillerInput]):
    async def fill(self, input_data: FeaturesFillerInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription", "childrenIds")
        ).dump(input_data.features)

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2
        )

        perception_description_payload = PerceptionSlot.schema(
            only=("perceptionKind", "perceptionDescription")
        ).dump(input_data.perception_description)
        perception_description_ = json.dumps(
            perception_description_payload,
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=features_fill_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{features}}", f"{features_}").replace(
                "{{perception_description}}", f"{perception_description_}"
            ),
            query=input_data.user_feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
