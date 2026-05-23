from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.slot_fillers.prompts.flows_fill_agent import flows_fill_prompt, business_objects_actors_label_prompt
from backend.core.perceptrons.slot_fillers.base_filler import BaseFiller, FillerInput
from backend.schemas import ActorNode, BusinessObjectNode, PerceptionSlot, FeatureNode, FlowNode


# 为流程补充器定义专属的输入类型
@dataclass
class FlowsFillerInput(FillerInput):
    user_requirements: str
    actors: List[ActorNode]
    features: List[FeatureNode]
    business_objects: List[BusinessObjectNode]
    flows: List[FlowNode]
    perception_description: PerceptionSlot
    user_feedback: str | None = None

class FlowsFiller(BaseFiller[FlowsFillerInput]):
    async def fill(self, input_data: FlowsFillerInput) -> Dict:
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

        perception_description_payload = PerceptionSlot.schema(
            only=("perceptionDescription",)
        ).dump(input_data.perception_description)
        perception_description_ = json.dumps(
            perception_description_payload,
            ensure_ascii=False,
            indent=2,
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

        # 第一步，生成补充的流程
        flows_response = await self._llm_handler.call_llm(
            prompt=flows_fill_prompt.replace(
                "{{user_requirements}}",f"{user_requirements_}").replace(
                "{{features}}", f"{features_}").replace(
                "{{flows}}", f"{flows_}").replace(
                "{{perception_description}}", f"{perception_description_}"
            ),
            query=input_data.user_feedback,
            print_log=False,
        )

        actors_payload = ActorNode.schema(
            many=True,
            only=("actorName", "actorDescription")
        ).dump(input_data.actors)

        actors_ = json.dumps(
            {"actors": actors_payload},
            ensure_ascii=False,
            indent=2
        )

        business_objects_payload = BusinessObjectNode.schema(
            many=True,
            only=(
                "businessObjectId",
                "businessObjectName",
                "businessObjectDescription",
                "businessObjectAttributes",
            ),
        ).dump(input_data.business_objects)

        business_objects_ = json.dumps(
            {"business_objects": business_objects_payload},
            ensure_ascii=False,
            indent=2,
        )

        # 第二步 生成或标记流程相关属性
        response = await self._llm_handler.call_llm(
            prompt=business_objects_actors_label_prompt.replace(
                "{{actors}}", f"{actors_}").replace(
                "{{business_objects}}", f"{business_objects_}").replace(
                "{{flow}}", f"{flows_response}"
            ),
            query=input_data.user_feedback,
            print_log=False,
        )
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    from backend.schemas import ActorNode, PerceptionSlot, PerceptionKindType, BusinessObjectAttributeNode, FlowStepNode, FlowStepType

    flows_filler = FlowsFiller()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"

    # 测试数据因编码问题已省略，详细测试用例请参考其他 filler 文件
    pass
