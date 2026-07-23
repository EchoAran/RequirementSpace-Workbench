from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.prompts import acceptance_criteria_perceive_prompt
from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.schemas import ActorNode, FeatureNode, ScenarioNode


# 为成功标准感知器定义专属的输入类型
@dataclass
class AcceptanceCriteriaPerceptronInput(PerceptronInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]


class AcceptanceCriteriaPerceptron(
    BasePerceptron[AcceptanceCriteriaPerceptronInput]
):
    async def perceive(
        self,
        input_data: AcceptanceCriteriaPerceptronInput,
    ) -> Dict:
        user_requirements_ = input_data.user_requirements

        actor_ = ActorNode.schema(
            only=("actorName", "actorDescription"),
        ).dumps(
            input_data.actor,
            ensure_ascii=False,
            indent=2,
        )

        feature_ = FeatureNode.schema(
            only=("featureName", "featureDescription"),
        ).dumps(
            input_data.feature,
            ensure_ascii=False,
            indent=2,
        )

        scenarios_ = json.dumps(
            {
                "scenarios": self._build_scenarios_payload(
                    input_data.scenarios
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=acceptance_criteria_perceive_prompt.replace(
                "{{user_requirements}}", user_requirements_).replace(
                "{{actor}}", actor_).replace(
                "{{feature}}", feature_).replace(
                "{{scenarios}}", scenarios_
            ),
            print_log=True,
            protected_inputs=self._protected_inputs(input_data),
        )

        return json.loads(response)

    @staticmethod
    def _build_scenarios_payload(
        scenarios: List[ScenarioNode],
    ) -> list[dict]:
        return [
            {
                "scenario_id": scenario.scenarioId,
                "scenario_name": scenario.scenarioName,
                "scenario_content": scenario.scenarioContent,
                "acceptance_criteria": [
                    {
                        "criterion_id": criterion.criterionId,
                        "criterion_content": criterion.criterionContent,
                    }
                    for criterion in scenario.acceptanceCriteria
                ],
            }
            for scenario in scenarios
        ]
