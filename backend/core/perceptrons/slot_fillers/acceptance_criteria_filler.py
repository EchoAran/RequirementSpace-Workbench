from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.slot_fillers.prompts.acceptance_criteria_fill_agent import acceptance_criteria_fill_prompt
from backend.core.perceptrons.slot_fillers.base_filler import BaseFiller, FillerInput
from backend.schemas import ActorNode, FeatureNode, PerceptionSlot, ScenarioNode


# 为成功标准补充器定义专属的输入类型
@dataclass
class AcceptanceCriteriaFillerInput(FillerInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]
    perception_description: PerceptionSlot
    user_feedback: str | None = None


class AcceptanceCriteriaFiller(BaseFiller[AcceptanceCriteriaFillerInput]):
    async def fill(
        self,
        input_data: AcceptanceCriteriaFillerInput,
    ) -> Dict:
        user_requirements_ = input_data.user_requirements

        actor_ = ActorNode.schema(
            only=("actorName", "actorDescription"),
        ).dumps(
            input_data.actor,
            indent=2,
            ensure_ascii=False,
        )

        feature_ = FeatureNode.schema(
            only=("featureName", "featureDescription"),
        ).dumps(
            input_data.feature,
            indent=2,
            ensure_ascii=False,
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

        perception_description_payload = PerceptionSlot.schema(
            only=("perceptionDescription",)
        ).dump(input_data.perception_description)

        perception_description_ = json.dumps(
            perception_description_payload,
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=acceptance_criteria_fill_prompt.replace(
                "{{user_requirements}}", user_requirements_,).replace(
                "{{actor}}", actor_,).replace(
                "{{feature}}", feature_,).replace(
                "{{scenarios}}", scenarios_,).replace(
                "{{perception_description}}", perception_description_,
            ),
            query=input_data.user_feedback,
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
