import json
from dataclasses import dataclass

from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.core.perceptrons.prompts import features_perceive_prompt
from backend.schemas import FeatureNode


# 为系统功能感知器定义专属的输入类型
@dataclass
class FeaturesPerceptronInput(PerceptronInput):
    user_requirements: str
    features: list[FeatureNode]

class FeaturesPerceptron(BasePerceptron[FeaturesPerceptronInput]):
    async def perceive(self, input_data: FeaturesPerceptronInput) -> dict:
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

        response = await self._llm_handler.call_llm(
            prompt=features_perceive_prompt.replace(
                "{{user_requirements}}",f"{user_requirements_}").replace(
                "{{features}}", f"{features_}"
            ),
            print_log=True,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
