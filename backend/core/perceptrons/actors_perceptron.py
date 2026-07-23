from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.prompts import actors_perceive_prompt
from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.schemas import ActorNode

# 为参与者感知器定义专属的输入类型
@dataclass
class ActorsPerceptronInput(PerceptronInput):
    user_requirements: str
    actors: List[ActorNode]

class ActorsPerceptron(BasePerceptron[ActorsPerceptronInput]):
    async def perceive(self, input_data: ActorsPerceptronInput) -> Dict:

        user_requirements_ = input_data.user_requirements

        actors_payload = ActorNode.schema(
            many=True,
            only=("actorName", "actorDescription")
        ).dump(input_data.actors)

        actors_ = json.dumps(
            {"actors": actors_payload},
            ensure_ascii=False,
            indent=2
        )

        response = await self._llm_handler.call_llm(
            prompt=actors_perceive_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{actors}}", f"{actors_}"
            ),
            print_log=True,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
