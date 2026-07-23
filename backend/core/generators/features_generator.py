from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.generators.prompts import features_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.schemas import ActorNode

# 为特征树生成器定义专属的输入类型
@dataclass
class FeaturesGeneratorInput(GenerateInput):
    user_requirements: str
    actors: List[ActorNode]
    user_feedback: str | None = None
    knowledge_context: str | None = None

class FeaturesGenerator(BaseGenerator[FeaturesGeneratorInput]):
    async def generate(self, input_data: FeaturesGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements
        feedback = input_data.user_feedback or ""

        actors_payload = ActorNode.schema(
            many=True,
            only=("actorId", "actorName", "actorDescription")
        ).dump(input_data.actors)

        actors_ = json.dumps(
            {"actors": actors_payload},
            ensure_ascii=False,
            indent=2
        )

        prompt = features_generate_prompt.replace(
            "{{user_requirements}}", f"{user_requirements_}"
        ).replace(
            "{{actors}}", f"{actors_}"
        )
        if input_data.knowledge_context:
            prompt = prompt.replace(
                "# 输出格式说明", f"{input_data.knowledge_context}\n\n# 输出格式说明"
            )

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        if not response:
            raise ValueError("LLM returned an empty response. Please check backend server logs for the detailed LLM connection or settings error.")
        return json.loads(response)
