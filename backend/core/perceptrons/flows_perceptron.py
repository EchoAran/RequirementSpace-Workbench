from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.prompts import flows_perceive_prompt
from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.schemas import FeatureNode, FlowNode


# 为流程感知器定义专属的输入类型
@dataclass
class FlowsPerceptronInput(PerceptronInput):
    user_requirements: str
    features: List[FeatureNode]
    flows: List[FlowNode]

class FlowsPerceptron(BasePerceptron[FlowsPerceptronInput]):
    async def perceive(self, input_data: FlowsPerceptronInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription", "actorIds")
        ).dump(node for node in input_data.features if len(node.childrenIds) == 0)      # 筛选出没有孩子的结点，即叶子结点

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2
        )

        flows_payload = FlowNode.schema(
            many=True,
            only=(
                "flowId",
                "flowName",
                "flowDescription",
                "featureIds",
                "flowSteps.stepId",
                "flowSteps.stepName",
                "flowSteps.stepDescription",
                "flowSteps.nextStepIds",
            ),
        ).dump(input_data.flows)

        flows_ = json.dumps(
            {"flows": flows_payload,},
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=flows_perceive_prompt.replace(
                "{{user_requirements}}", user_requirements_).replace(
                "{{features}}", features_).replace(
                "{{flows}}", flows_),
            print_log=True,
            protected_inputs=self._protected_inputs(input_data),
        )

        return json.loads(response)
