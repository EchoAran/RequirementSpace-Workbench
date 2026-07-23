from dataclasses import dataclass
import json
from typing import Any, Dict, List

from backend.core.generators.prompts import (
    business_object_in_flows_prompt,
    business_objects_generate_prompt,
    flows_generate_prompt,
    flows_generate_combined_prompt,
)
from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.schemas import FeatureNode, ActorNode

# 为流程生成器定义专属的输入类型
@dataclass
class FlowsGeneratorInput(GenerateInput):
    user_requirements: str
    actors: List[ActorNode]
    features: List[FeatureNode]
    user_feedback: str | None = None

class FlowsGenerator(BaseGenerator[FlowsGeneratorInput]):
    async def generate(
        self,
        input_data: FlowsGeneratorInput,
        use_combined_prompt: bool = False,
    ) -> Dict:
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

        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription", "actorIds")
        ).dump(node for node in input_data.features if len(node.childrenIds) == 0)      # 筛选出没有孩子的结点，即叶子结点

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2
        )

        if use_combined_prompt:
            response = await self._llm_handler.call_llm(
                prompt=flows_generate_combined_prompt.replace(
                    "{{user_requirements}}", f"{user_requirements_}").replace(
                    "{{actors}}", f"{actors_}").replace(
                    "{{features}}", f"{features_}"
                ),
                query=feedback,
                print_log=False,
                protected_inputs=self._protected_inputs(input_data),
            )
            result = self._loads_llm_json(response)
            if not isinstance(result, dict):
                raise ValueError("invalid_llm_response")
            return result

        flows_response = await self._llm_handler.call_llm(
            prompt=flows_generate_prompt.replace(
                "{{user_requirements}}",f"{user_requirements_}").replace(
                "{{actors}}", f"{actors_}").replace(
                "{{features}}", f"{features_}"
            ),
            query=feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        flows_result = self._loads_llm_json(flows_response)
        if not isinstance(flows_result, dict):
            raise ValueError("invalid_llm_response")

        flows_ = self._dumps_prompt_payload({"flows": flows_result.get("flows", [])})

        business_objects_response = await self._llm_handler.call_llm(
            prompt=business_objects_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{flows}}", flows_
            ),
            query=feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        business_objects_result = self._loads_llm_json(business_objects_response)
        if not isinstance(business_objects_result, dict):
            raise ValueError("invalid_llm_response")

        business_objects_ = self._dumps_prompt_payload(
            {
                "business_objects": business_objects_result.get(
                    "business_objects",
                    [],
                )
            }
        )

        relations_response = await self._llm_handler.call_llm(
            prompt=business_object_in_flows_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{flows}}", flows_).replace(
                "{{business_objects}}", business_objects_
            ),
            query=feedback,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        relations_result = self._loads_llm_json(relations_response)

        return self._merge_generation_results(
            flows_result=flows_result,
            business_objects_result=business_objects_result,
            relations_result=relations_result,
        )

    @staticmethod
    def _loads_llm_json(response: str | None) -> Any:
        if response is None:
            raise ValueError("empty_llm_response")

        return json.loads(response)

    @staticmethod
    def _dumps_prompt_payload(payload: dict) -> str:
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _merge_generation_results(
        flows_result: dict,
        business_objects_result: dict,
        relations_result: Any,
    ) -> dict:
        flows = flows_result.get("flows", [])
        if not isinstance(flows, list):
            flows = []

        business_objects = business_objects_result.get("business_objects", [])
        if not isinstance(business_objects, list):
            business_objects = []

        if isinstance(relations_result, dict):
            relations = relations_result.get("business_object_in_flows")
            if relations is None:
                relations = relations_result.get("flows")
        else:
            relations = relations_result

        if not isinstance(relations, list):
            relations = []

        relation_by_flow_name = {
            relation.get("flow_name"): relation
            for relation in relations
            if isinstance(relation, dict) and relation.get("flow_name")
        }

        for flow_index, flow in enumerate(flows):
            if not isinstance(flow, dict):
                continue

            relation = relation_by_flow_name.get(flow.get("flow_name"))
            if relation is None and flow_index < len(relations):
                relation = relations[flow_index]

            step_relation_by_number = {}
            if isinstance(relation, dict):
                step_relation_by_number = {
                    step_relation.get("step_number"): step_relation
                    for step_relation in relation.get("flow_steps", [])
                    if (
                        isinstance(step_relation, dict)
                        and step_relation.get("step_number")
                    )
                }

            for step in flow.get("flow_steps", []):
                if not isinstance(step, dict):
                    continue

                step_relation = step_relation_by_number.get(
                    step.get("step_number"),
                    {},
                )
                step["input_business_object_numbers"] = step_relation.get(
                    "input_business_object_numbers",
                    [],
                )
                step["output_business_object_numbers"] = step_relation.get(
                    "output_business_object_numbers",
                    [],
                )

        return {
            "business_objects": business_objects,
            "flows": flows,
        }
