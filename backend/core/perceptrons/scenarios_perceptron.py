from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.prompts import scenarios_perceive_prompt
from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.schemas import ActorNode, FeatureNode, ScenarioNode


# 为场景感知器定义专属的输入类型
@dataclass
class ScenariosPerceptronInput(PerceptronInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]

class ScenariosPerceptron(BasePerceptron[ScenariosPerceptronInput]):
    async def perceive(self, input_data: ScenariosPerceptronInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        actor_ = ActorNode.schema(
            only=(
                "actorName",
                "actorDescription",
            ),
        ).dumps(
            input_data.actor,
            ensure_ascii=False,
            indent=2,
        )

        feature_ = FeatureNode.schema(
            only=(
                "featureName",
                "featureDescription",
            ),
        ).dumps(
            input_data.feature,
            ensure_ascii=False,
            indent=2,
        )

        scenarios_payload = ScenarioNode.schema(
            many=True,
            only=(
                "scenarioName",
                "scenarioContent",
            ),
        ).dump(input_data.scenarios)

        scenarios_ = json.dumps(
            {
                "scenarios": scenarios_payload,
            },
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=scenarios_perceive_prompt.replace(
                "{{user_requirements}}",
                user_requirements_,
            ).replace(
                "{{actor}}",
                actor_,
            ).replace(
                "{{feature}}",
                feature_,
            ).replace(
                "{{scenarios}}",
                scenarios_,
            ),
            print_log=True,
            protected_inputs=self._protected_inputs(input_data),
        )

        return json.loads(response)
