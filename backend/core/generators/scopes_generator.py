from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.generators.prompts import scopes_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.schemas import FeatureNode

# 为范围生成器定义专属的输入类型
@dataclass
class ScopesGeneratorInput(GenerateInput):
    user_requirements: str
    features: List[FeatureNode]
    user_feedback: str | None = None

class ScopesGenerator(BaseGenerator[ScopesGeneratorInput]):
    async def generate(self, input_data: ScopesGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements
        feedback = input_data.user_feedback or ""

        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription")
        ).dump(node for node in input_data.features if len(node.childrenIds) == 0)      # 筛选出没有孩子的结点，即叶子结点

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2
        )

        response = await self._llm_handler.call_llm(
            prompt=scopes_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{features}}", f"{features_}"
            ),
            query=feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
