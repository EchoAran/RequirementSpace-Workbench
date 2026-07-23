from dataclasses import dataclass
import json
from typing import Dict

from backend.core.generators.prompts import scenarios_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.schemas import FeatureNode, ActorNode

# 为场景生成器定义专属的输入类型
@dataclass
class ScenariosGeneratorInput(GenerateInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    user_feedback: str | None = None

class ScenariosGenerator(BaseGenerator[ScenariosGeneratorInput]):
    async def generate(self, input_data: ScenariosGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements
        feedback = input_data.user_feedback or ""

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

        response = await self._llm_handler.call_llm(
            prompt=scenarios_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{actor}}",f"{actor_}").replace(
                "{{feature}}", f"{feature_}"
            ),
            query=feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        if response is None:
            raise ValueError("invalid_llm_response")
        return json.loads(response)
