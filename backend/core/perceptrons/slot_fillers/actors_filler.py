from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.slot_fillers.prompts.actors_fill_agent import actors_fill_prompt
from backend.core.perceptrons.slot_fillers.base_filler import BaseFiller, FillerInput
from backend.schemas import ActorNode, PerceptionSlot

# 为参与者补充器定义专属的输入类型
@dataclass
class ActorsFillerInput(FillerInput):
    user_requirements: str
    actors: List[ActorNode]
    perception_description: PerceptionSlot
    user_feedback: str | None = None

class ActorsFiller(BaseFiller[ActorsFillerInput]):
    async def fill(self, input_data: ActorsFillerInput) -> Dict:
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

        perception_description_payload = PerceptionSlot.schema(
            only=("perceptionDescription",)
        ).dump(input_data.perception_description)
        perception_description_ = json.dumps(
            perception_description_payload,
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=actors_fill_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{actors}}", f"{actors_}").replace(
                "{{perception_description}}", f"{perception_description_}"
            ),
            query=input_data.user_feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
