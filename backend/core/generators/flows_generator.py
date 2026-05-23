from dataclasses import dataclass
import json
from typing import Any, Dict, List

from backend.core.generators.prompts import (
    business_object_in_flows_prompt,
    business_objects_generate_prompt,
    flows_generate_prompt,
    flows_generate_prompt_old,
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
        use_old_prompt: bool = False,
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

        if use_old_prompt:
            response = await self._llm_handler.call_llm(
                prompt=flows_generate_prompt_old.replace(
                    "{{user_requirements}}", f"{user_requirements_}").replace(
                    "{{actors}}", f"{actors_}").replace(
                    "{{features}}", f"{features_}"
                ),
                query=feedback,
                print_log=False,
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


if __name__ == "__main__":
    import asyncio
    from backend.schemas import FeatureNode, ActorNode
    flows_generator = FlowsGenerator()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"
    test_actors = [
        ActorNode(
            actorId=1,
            actorName="本地音乐听众",
            actorDescription="本地音乐听众是指在需要播放和聆听电脑本地音乐文件的场景下，与音乐播放器发生交互，并可执行导入或扫描本地音乐、播放暂停、切换上一首下一首、调整播放进度、管理播放列表和选择音频格式进行播放等操作的用户角色。"
        ),
        ActorNode(
            actorId=2,
            actorName="歌单管理者",
            actorDescription="歌单管理者是指在需要按个人喜好整理和归类本地音乐的场景下，与歌单管理功能发生交互，并可执行新建歌单、编辑歌单、添加或移除歌曲、排序歌曲、删除歌单和自定义歌单内容等操作的用户角色。"
        ),
        ActorNode(
            actorId=3,
            actorName="音效调节者",
            actorDescription="音效调节者是指在需要根据听感优化音乐播放效果的场景下，与音效设置功能发生交互，并可执行调整均衡器、配置音效参数、切换预设音效和保存个人音效偏好等操作的用户角色。"
        ),
        ActorNode(
            actorId=4,
            actorName="歌词匹配者",
            actorDescription="歌词匹配者是指在需要查看本地歌曲对应歌词的场景下，与歌词匹配功能发生交互，并可执行本地歌词自动匹配、查看歌词显示、调整歌词同步效果和管理歌词关联结果等操作的用户角色。"
        ),
        ActorNode(
            actorId=5,
            actorName="睡眠定时设置者",
            actorDescription="睡眠定时设置者是指在需要限定音乐播放时长并在指定时间自动关闭播放器的场景下，与睡眠定时功能发生交互，并可执行设置定时关闭时间、取消定时、查看倒计时和管理播放结束行为等操作的用户角色。"
        ),
        ActorNode(
            actorId=6,
            actorName="快捷键控制者",
            actorDescription="快捷键控制者是指在需要通过全局快捷键快速控制播放的场景下，与全局快捷键功能发生交互，并可执行设置切歌快捷键、使用快捷键播放暂停、上一首下一首切换和快速调节播放控制等操作的用户角色。"
        ),
        ActorNode(
            actorId=7,
            actorName="界面偏好设置者",
            actorDescription="界面偏好设置者是指在需要让播放器保持清爽、轻量和低干扰使用体验的场景下，与界面设置功能发生交互，并可执行调整界面显示样式、切换轻量化布局、配置视觉风格和管理播放器外观偏好的用户角色。"
        ),
    ]
    test_features: List[FeatureNode] = [
        FeatureNode(
            featureId=1,
            featureName="极简纯净本地音乐播放器",
            featureDescription="系统用于在电脑本地离线播放音乐文件，支持无损与常见音频格式播放，并提供歌词匹配、音效均衡、歌单管理、睡眠定时、全局快捷键和轻量化界面等功能，旨在替代臃肿的主流音乐播放器。",
            actorIds=[1, 2, 3, 4, 5, 6, 7],
            childrenIds=[2, 6, 10, 14, 18, 22, 26]
        ),
        FeatureNode(
            featureId=2,
            featureName="本地音乐播放管理",
            featureDescription="支持读取电脑本地音乐文件并进行播放控制、进度调整和格式播放管理。",
            actorIds=[1],
            childrenIds=[3, 4, 5]
        ),
        FeatureNode(
            featureId=3,
            featureName="扫描与导入本地音乐",
            featureDescription="支持从电脑本地读取、扫描和导入音乐文件，作为播放器的媒体来源。",
            actorIds=[1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=4,
            featureName="播放控制",
            featureDescription="支持播放、暂停、上一首、下一首和播放进度调整等基础播放操作。",
            actorIds=[1, 6],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=5,
            featureName="音频格式播放",
            featureDescription="支持播放本地无损及常见音频格式文件，包括 Flac、WAV 和 MP3。",
            actorIds=[1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=6,
            featureName="歌单自定义管理",
            featureDescription="支持用户按个人喜好创建、编辑和维护本地音乐歌单。",
            actorIds=[2, 1],
            childrenIds=[7, 8, 9]
        ),
        FeatureNode(
            featureId=7,
            featureName="新建与删除歌单",
            featureDescription="支持用户创建新的歌单并删除不再需要的歌单。",
            actorIds=[2],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=8,
            featureName="添加或移除歌曲",
            featureDescription="支持用户将本地歌曲添加到歌单中或从歌单中移除。",
            actorIds=[2, 1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=9,
            featureName="歌单排序与自定义内容",
            featureDescription="支持用户调整歌单内歌曲顺序，并按个人偏好自定义歌单内容。",
            actorIds=[2],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=10,
            featureName="歌词匹配与显示",
            featureDescription="支持本地歌曲歌词自动匹配、显示与同步管理。",
            actorIds=[4],
            childrenIds=[11, 12, 13]
        ),
        FeatureNode(
            featureId=11,
            featureName="本地歌词自动匹配",
            featureDescription="支持根据本地歌曲自动匹配对应歌词文件或歌词内容。",
            actorIds=[4],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=12,
            featureName="歌词显示与同步调整",
            featureDescription="支持在播放界面显示歌词，并调整歌词同步效果以匹配播放进度。",
            actorIds=[4, 1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=13,
            featureName="歌词关联管理",
            featureDescription="支持用户管理歌词与歌曲的关联结果，便于维护匹配准确性。",
            actorIds=[4],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=14,
            featureName="音效与均衡器设置",
            featureDescription="支持用户根据听感调整音效参数与均衡器配置。",
            actorIds=[3],
            childrenIds=[15, 16, 17]
        ),
        FeatureNode(
            featureId=15,
            featureName="均衡器调节",
            featureDescription="支持用户调整均衡器各频段参数，以优化不同音乐风格的听感。",
            actorIds=[3],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=16,
            featureName="音效参数配置",
            featureDescription="支持用户配置音效相关参数，并保存个人偏好设置。",
            actorIds=[3],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=17,
            featureName="预设音效切换",
            featureDescription="支持用户切换系统提供的预设音效方案。",
            actorIds=[3],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=18,
            featureName="睡眠定时关闭",
            featureDescription="支持设置定时关闭播放器，在指定时间自动停止播放并退出或关闭程序。",
            actorIds=[5],
            childrenIds=[19, 20, 21]
        ),
        FeatureNode(
            featureId=19,
            featureName="设置定时关闭时间",
            featureDescription="支持用户设置播放器在指定时间后自动关闭。",
            actorIds=[5],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=20,
            featureName="取消定时与查看倒计时",
            featureDescription="支持用户取消已设置的定时关闭，并查看剩余倒计时。",
            actorIds=[5],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=21,
            featureName="管理播放结束行为",
            featureDescription="支持用户配置定时结束后播放器的处理方式，如停止播放或关闭程序。",
            actorIds=[5],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=22,
            featureName="全局快捷键控制",
            featureDescription="支持通过系统全局快捷键快速控制音乐播放。",
            actorIds=[6],
            childrenIds=[23, 24, 25]
        ),
        FeatureNode(
            featureId=23,
            featureName="切歌快捷键设置",
            featureDescription="支持用户设置全局切歌快捷键，以便快速控制播放。",
            actorIds=[6],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=24,
            featureName="快捷键播放控制",
            featureDescription="支持通过全局快捷键执行播放、暂停、上一首和下一首操作。",
            actorIds=[6, 1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=25,
            featureName="快速调节播放状态",
            featureDescription="支持通过快捷键快速调整当前播放状态，提升操作效率。",
            actorIds=[6],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=26,
            featureName="清爽轻量化界面设置",
            featureDescription="支持配置播放器界面风格与显示方式，保持界面简洁、轻量和低干扰。",
            actorIds=[7],
            childrenIds=[27, 28, 29]
        ),
        FeatureNode(
            featureId=27,
            featureName="界面显示样式调整",
            featureDescription="支持用户调整界面显示样式，使播放器保持清爽直观。",
            actorIds=[7],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=28,
            featureName="轻量化布局切换",
            featureDescription="支持用户切换轻量化布局，减少不必要的视觉元素与操作干扰。",
            actorIds=[7],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=29,
            featureName="视觉风格与外观偏好管理",
            featureDescription="支持用户配置播放器视觉风格，满足长期使用中的外观偏好。",
            actorIds=[7],
            childrenIds=[]
        )
    ]

    async def main():
        await flows_generator.generate(
            FlowsGeneratorInput(user_requirements, test_actors, test_features)
         )
    asyncio.run(main())

    flows_generator_result = """
{
  "business_objects": [
    {
      "business_object_number": "B-001",
      "business_object_name": "本地音乐文件",
      "business_object_description": "播放器从电脑本地扫描、识别并读取的音频文件对象，作为播放、导入、歌词匹配和歌单管理的基础数据来源。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "music_id",
          "business_object_attribute_description": "本地音乐文件唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "M-001"
        },
        {
          "business_object_attribute_name": "file_path",
          "business_object_attribute_description": "音乐文件在本地磁盘中的完整路径",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "D:\\\\Music\\\\周杰伦\\\\晴天.flac"
        },
        {
          "business_object_attribute_name": "file_name",
          "business_object_attribute_description": "音乐文件名称",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "晴天.flac"
        },
        {
          "business_object_attribute_name": "audio_format",
          "business_object_attribute_description": "音频格式类型",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "flac"
        },
        {
          "business_object_attribute_name": "duration_seconds",
          "business_object_attribute_description": "音频时长，单位为秒",
          "business_object_attribute_type": "integer",
          "business_object_attribute_example": "269"
        },
        {
          "business_object_attribute_name": "title",
          "business_object_attribute_description": "歌曲标题",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "晴天"
        },
        {
          "business_object_attribute_name": "artist",
          "business_object_attribute_description": "歌曲歌手名称",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "周杰伦"
        },
        {
          "business_object_attribute_name": "album",
          "business_object_attribute_description": "所属专辑名称",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "叶惠美"
        },
        {
          "business_object_attribute_name": "is_available",
          "business_object_attribute_description": "文件当前是否可被读取播放",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "true"
        }
      ]
    },
    {
      "business_object_number": "B-002",
      "business_object_name": "播放会话",
      "business_object_description": "播放器当前的播放上下文，用于记录正在播放的歌曲、播放状态、播放进度和切换行为。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "playback_session_id",
          "business_object_attribute_description": "播放会话唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "PS-001"
        },
        {
          "business_object_attribute_name": "current_music_id",
          "business_object_attribute_description": "当前播放的音乐文件标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "M-001"
        },
        {
          "business_object_attribute_name": "play_status",
          "business_object_attribute_description": "当前播放状态，如播放中、暂停、停止",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "playing"
        },
        {
          "business_object_attribute_name": "progress_seconds",
          "business_object_attribute_description": "当前播放进度秒数",
          "business_object_attribute_type": "integer",
          "business_object_attribute_example": "128"
        },
        {
          "business_object_attribute_name": "volume",
          "business_object_attribute_description": "当前音量值",
          "business_object_attribute_type": "integer",
          "business_object_attribute_example": "70"
        },
        {
          "business_object_attribute_name": "play_source",
          "business_object_attribute_description": "当前播放来源，如音乐库或歌单",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "playlist"
        }
      ]
    },
    {
      "business_object_number": "B-003",
      "business_object_name": "歌单",
      "business_object_description": "用户自定义维护的歌曲集合，用于按个人喜好整理、排序和播放本地音乐。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "playlist_id",
          "business_object_attribute_description": "歌单唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "PL-001"
        },
        {
          "business_object_attribute_name": "playlist_name",
          "business_object_attribute_description": "歌单名称",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "深夜循环"
        },
        {
          "business_object_attribute_name": "music_ids",
          "business_object_attribute_description": "歌单内歌曲标识列表",
          "business_object_attribute_type": "array[string]",
          "business_object_attribute_example": "[\"M-001\", \"M-003\", \"M-008\"]"
        },
        {
          "business_object_attribute_name": "song_count",
          "business_object_attribute_description": "歌单内歌曲数量",
          "business_object_attribute_type": "integer",
          "business_object_attribute_example": "3"
        },
        {
          "business_object_attribute_name": "custom_order_enabled",
          "business_object_attribute_description": "是否启用自定义排序",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "true"
        }
      ]
    },
    {
      "business_object_number": "B-004",
      "business_object_name": "歌词关联",
      "business_object_description": "歌曲与本地歌词文件之间的匹配与同步数据，用于歌词显示、偏移调整和关联维护。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "lyric_link_id",
          "business_object_attribute_description": "歌词关联唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "L-001"
        },
        {
          "business_object_attribute_name": "music_id",
          "business_object_attribute_description": "关联的歌曲标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "M-001"
        },
        {
          "business_object_attribute_name": "lyric_file_path",
          "business_object_attribute_description": "本地歌词文件路径",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "D:\\\\Lyrics\\\\晴天.lrc"
        },
        {
          "business_object_attribute_name": "match_status",
          "business_object_attribute_description": "歌词匹配状态，如已匹配、未匹配、手动关联",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "matched"
        },
        {
          "business_object_attribute_name": "sync_offset_ms",
          "business_object_attribute_description": "歌词同步偏移毫秒值",
          "business_object_attribute_type": "integer",
          "business_object_attribute_example": "250"
        },
        {
          "business_object_attribute_name": "display_enabled",
          "business_object_attribute_description": "播放界面是否启用歌词显示",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "true"
        }
      ]
    },
    {
      "business_object_number": "B-005",
      "business_object_name": "音效配置",
      "business_object_description": "用户针对播放器设置的均衡器和音效参数配置，可切换预设并保存个人偏好。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "effect_config_id",
          "business_object_attribute_description": "音效配置唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "EQ-001"
        },
        {
          "business_object_attribute_name": "preset_name",
          "business_object_attribute_description": "当前使用的预设名称",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "流行"
        },
        {
          "business_object_attribute_name": "band_settings",
          "business_object_attribute_description": "均衡器各频段参数集合",
          "business_object_attribute_type": "object",
          "business_object_attribute_example": "{\"60Hz\":\"+3\",\"230Hz\":\"+1\",\"910Hz\":\"0\",\"4kHz\":\"+2\",\"14kHz\":\"+4\"}"
        },
        {
          "business_object_attribute_name": "effect_enabled",
          "business_object_attribute_description": "是否启用音效处理",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "true"
        },
        {
          "business_object_attribute_name": "user_saved",
          "business_object_attribute_description": "当前配置是否已保存为用户偏好",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "true"
        }
      ]
    },
    {
      "business_object_number": "B-006",
      "business_object_name": "睡眠定时任务",
      "business_object_description": "用户设置的播放定时结束控制数据，用于记录倒计时、结束行为和启用状态。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "sleep_timer_id",
          "business_object_attribute_description": "睡眠定时任务唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "ST-001"
        },
        {
          "business_object_attribute_name": "remaining_seconds",
          "business_object_attribute_description": "剩余倒计时秒数",
          "business_object_attribute_type": "integer",
          "business_object_attribute_example": "1800"
        },
        {
          "business_object_attribute_name": "target_action",
          "business_object_attribute_description": "定时结束后执行的行为",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "close_app"
        },
        {
          "business_object_attribute_name": "is_active",
          "business_object_attribute_description": "定时任务是否处于启用状态",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "true"
        },
        {
          "business_object_attribute_name": "start_time",
          "business_object_attribute_description": "定时任务开始时间",
          "business_object_attribute_type": "datetime",
          "business_object_attribute_example": "2026-05-20 23:30:00"
        }
      ]
    },
    {
      "business_object_number": "B-007",
      "business_object_name": "快捷键配置",
      "business_object_description": "播放器全局快捷键的映射和启用状态配置，用于快速控制播放和切歌。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "shortcut_config_id",
          "business_object_attribute_description": "快捷键配置唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "SC-001"
        },
        {
          "business_object_attribute_name": "play_pause_key",
          "business_object_attribute_description": "播放暂停快捷键组合",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "Ctrl+Alt+Space"
        },
        {
          "business_object_attribute_name": "previous_key",
          "business_object_attribute_description": "上一首快捷键组合",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "Ctrl+Alt+Left"
        },
        {
          "business_object_attribute_name": "next_key",
          "business_object_attribute_description": "下一首快捷键组合",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "Ctrl+Alt+Right"
        },
        {
          "business_object_attribute_name": "enabled",
          "business_object_attribute_description": "全局快捷键是否启用",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "true"
        }
      ]
    },
    {
      "business_object_number": "B-008",
      "business_object_name": "界面偏好设置",
      "business_object_description": "用户针对播放器界面样式、轻量布局和视觉风格的长期偏好配置。",
      "business_object_attributes": [
        {
          "business_object_attribute_name": "ui_preference_id",
          "business_object_attribute_description": "界面偏好设置唯一标识",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "UI-001"
        },
        {
          "business_object_attribute_name": "theme_style",
          "business_object_attribute_description": "界面主题风格",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "纯净浅色"
        },
        {
          "business_object_attribute_name": "layout_mode",
          "business_object_attribute_description": "界面布局模式",
          "business_object_attribute_type": "string",
          "business_object_attribute_example": "轻量模式"
        },
        {
          "business_object_attribute_name": "show_extra_panels",
          "business_object_attribute_description": "是否显示额外信息面板",
          "business_object_attribute_type": "bool",
          "business_object_attribute_example": "false"
        },
        {
          "business_object_attribute_name": "font_scale",
          "business_object_attribute_description": "界面字体缩放比例",
          "business_object_attribute_type": "decimal",
          "business_object_attribute_example": "1.0"
        }
      ]
    }
  ],
  "flows": [
    {
      "flow_name": "本地音乐扫描与导入流程",
      "flow_description": "本地音乐听众选择本地目录，系统扫描并识别支持的音频文件格式，导入为播放器可用的本地音乐库。",
      "feature_ids": [
        3,
        5
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择扫描目录",
          "step_description": "本地音乐听众选择需要扫描的本地音乐文件夹或磁盘路径，发起导入操作。",
          "actor_ids": [
            1
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "扫描本地文件",
          "step_description": "系统遍历所选目录，读取本地音频文件并提取基础元数据。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [],
          "output_business_object_numbers": [
            "B-001"
          ],
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断音频格式是否支持",
          "step_description": "系统判断扫描到的文件是否属于 Flac、WAV 或 MP3 等受支持的可播放格式。",
          "actor_ids": [],
          "step_type": "judgment",
          "input_business_object_numbers": [
            "B-001"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "导入可用音乐文件",
          "step_description": "系统将受支持格式的本地音乐文件纳入播放器音乐库，并保留路径和标签信息。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-001"
          ],
          "output_business_object_numbers": [
            "B-001"
          ],
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "跳过不支持文件",
          "step_description": "系统忽略不受支持或损坏的文件，并继续扫描后续内容。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-001"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "完成导入并展示结果",
          "step_description": "系统生成导入结果，向用户展示可播放音乐条目，供后续浏览和播放。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-001"
          ],
          "output_business_object_numbers": [
            "B-001"
          ],
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "音乐播放控制流程",
      "flow_description": "用户从本地音乐库或歌单中选择歌曲，系统创建播放会话并支持播放、暂停、切歌和进度调整。",
      "feature_ids": [
        4,
        5,
        24,
        25
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择待播放歌曲",
          "step_description": "本地音乐听众从音乐库或歌单中选择一首本地歌曲作为当前播放目标。",
          "actor_ids": [
            1
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-001",
            "B-003"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "创建播放会话",
          "step_description": "系统加载目标音频文件，校验文件可用性并创建当前播放会话。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-001"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "执行播放或暂停操作",
          "step_description": "本地音乐听众或快捷键控制者执行播放、暂停等基础播放控制操作。",
          "actor_ids": [
            1,
            6
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-002"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "判断控制类型",
          "step_description": "系统判断当前操作是继续播放、暂停、切换上一首下一首，还是调整播放进度。",
          "actor_ids": [],
          "step_type": "judgment",
          "input_business_object_numbers": [
            "B-002",
            "B-003"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-005",
            "S-006",
            "S-007"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "更新播放状态",
          "step_description": "系统根据播放或暂停操作更新当前会话状态并刷新播放界面。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-002"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": []
        },
        {
          "step_number": "S-006",
          "step_name": "切换上下首歌曲",
          "step_description": "系统根据当前播放顺序定位上一首或下一首歌曲，并更新播放会话中的当前歌曲。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-001",
            "B-002",
            "B-003"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "调整播放进度",
          "step_description": "本地音乐听众拖动播放进度条，系统将播放位置跳转到目标时间点。",
          "actor_ids": [
            1
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-002"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": [
            "S-008"
          ]
        },
        {
          "step_number": "S-008",
          "step_name": "保存新进度状态",
          "step_description": "系统更新播放会话中的当前进度并继续播放或保持暂停状态。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-002"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "歌单管理流程",
      "flow_description": "歌单管理者创建或删除歌单，并对歌单中的歌曲进行添加、移除、排序和自定义维护。",
      "feature_ids": [
        7,
        8,
        9
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择歌单管理操作",
          "step_description": "歌单管理者进入歌单管理界面，选择新建歌单、删除歌单或编辑歌单内容。",
          "actor_ids": [
            2
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-003",
            "B-001"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "判断管理类型",
          "step_description": "系统判断当前是创建新歌单、删除现有歌单，还是维护歌单歌曲内容。",
          "actor_ids": [],
          "step_type": "judgment",
          "input_business_object_numbers": [
            "B-003"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-003",
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "新建歌单",
          "step_description": "歌单管理者输入歌单名称，创建一个新的自定义歌单。",
          "actor_ids": [
            2
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [],
          "output_business_object_numbers": [
            "B-003"
          ],
          "next_steps": [
            "S-008"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "删除歌单",
          "step_description": "歌单管理者选择不再需要的歌单并确认删除。",
          "actor_ids": [
            2
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-003"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-008"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "选择歌单编辑动作",
          "step_description": "歌单管理者选择对目标歌单执行添加歌曲、移除歌曲或调整排序。",
          "actor_ids": [
            2
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-003",
            "B-001"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "更新歌单歌曲内容",
          "step_description": "歌单管理者将歌曲加入歌单、从歌单移除，或调整歌曲顺序以形成自定义内容。",
          "actor_ids": [
            2
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-003",
            "B-001"
          ],
          "output_business_object_numbers": [
            "B-003"
          ],
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-007",
          "step_name": "保存歌单变更",
          "step_description": "系统保存歌单名称、歌曲列表和排序结果，更新歌单显示。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-003"
          ],
          "output_business_object_numbers": [
            "B-003"
          ],
          "next_steps": []
        },
        {
          "step_number": "S-008",
          "step_name": "提交歌单管理结果",
          "step_description": "系统执行歌单创建或删除操作，并刷新歌单列表。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-003"
          ],
          "output_business_object_numbers": [
            "B-003"
          ],
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "本地歌词匹配与显示流程",
      "flow_description": "歌词匹配者为本地歌曲自动匹配歌词文件，并在播放界面显示歌词、调整同步偏移和维护关联结果。",
      "feature_ids": [
        11,
        12,
        13
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择目标歌曲进行歌词处理",
          "step_description": "歌词匹配者或本地音乐听众选择需要显示歌词的本地歌曲。",
          "actor_ids": [
            4,
            1
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-001"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "自动匹配本地歌词",
          "step_description": "系统根据歌曲标题、歌手、文件名或同目录文件自动查找并匹配本地歌词文件。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-001"
          ],
          "output_business_object_numbers": [
            "B-004"
          ],
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断歌词是否匹配成功",
          "step_description": "系统判断是否已找到可用歌词关联结果。",
          "actor_ids": [],
          "step_type": "judgment",
          "input_business_object_numbers": [
            "B-004"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-004",
            "S-006"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "显示歌词内容",
          "step_description": "系统在播放界面按当前进度显示歌词内容，并建立歌曲与歌词的关联。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-002",
            "B-004"
          ],
          "output_business_object_numbers": [
            "B-004"
          ],
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "调整歌词同步偏移",
          "step_description": "歌词匹配者根据听感手动调整歌词显示的同步时间偏移。",
          "actor_ids": [
            4
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-004",
            "B-002"
          ],
          "output_business_object_numbers": [
            "B-004"
          ],
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "维护歌词关联结果",
          "step_description": "歌词匹配者在自动匹配失败或结果不准确时，手动管理歌词与歌曲的关联关系。",
          "actor_ids": [
            4
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-001",
            "B-004"
          ],
          "output_business_object_numbers": [
            "B-004"
          ],
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-007",
          "step_name": "保存歌词关联配置",
          "step_description": "系统保存歌词文件路径、匹配状态和同步偏移结果，供后续播放直接使用。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-004"
          ],
          "output_business_object_numbers": [
            "B-004"
          ],
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "音效均衡器配置流程",
      "flow_description": "音效调节者切换预设音效、调整均衡器频段和配置音效参数，并保存个人音效偏好。",
      "feature_ids": [
        15,
        16,
        17
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入音效设置",
          "step_description": "音效调节者打开播放器音效设置界面，查看当前音效配置。",
          "actor_ids": [
            3
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-005"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "选择预设或自定义调节",
          "step_description": "音效调节者选择系统预设音效方案，或进入自定义均衡器与参数设置。",
          "actor_ids": [
            3
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-005"
          ],
          "output_business_object_numbers": [
            "B-005"
          ],
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断音效调整方式",
          "step_description": "系统判断当前调整方式是直接切换预设，还是手动编辑均衡器频段与音效参数。",
          "actor_ids": [],
          "step_type": "judgment",
          "input_business_object_numbers": [
            "B-005"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "应用预设音效",
          "step_description": "系统根据用户选择应用对应的预设音效方案。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-005"
          ],
          "output_business_object_numbers": [
            "B-005"
          ],
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "调整均衡器和参数",
          "step_description": "音效调节者手动修改各频段增益和其他音效参数，以优化听感。",
          "actor_ids": [
            3
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-005"
          ],
          "output_business_object_numbers": [
            "B-005"
          ],
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "保存音效偏好",
          "step_description": "系统保存当前音效配置，供后续播放持续使用。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-005"
          ],
          "output_business_object_numbers": [
            "B-005"
          ],
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "睡眠定时关闭流程",
      "flow_description": "睡眠定时设置者设置定时关闭时长和播放结束行为，可查看倒计时并在需要时取消定时。",
      "feature_ids": [
        19,
        20,
        21
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "设置定时关闭参数",
          "step_description": "睡眠定时设置者输入定时时长，并选择到时后的处理方式，如停止播放或关闭程序。",
          "actor_ids": [
            5
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-006"
          ],
          "output_business_object_numbers": [
            "B-006"
          ],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "启动睡眠定时任务",
          "step_description": "系统创建并启动倒计时任务，记录剩余时间和目标行为。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-006"
          ],
          "output_business_object_numbers": [
            "B-006"
          ],
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "查看或取消定时",
          "step_description": "睡眠定时设置者查看剩余倒计时，并可按需取消当前定时任务。",
          "actor_ids": [
            5
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-006"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "判断定时任务状态",
          "step_description": "系统判断当前定时任务是被用户取消，还是已自然倒计时结束。",
          "actor_ids": [],
          "step_type": "judgment",
          "input_business_object_numbers": [
            "B-006",
            "B-002"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-005",
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "取消定时任务",
          "step_description": "系统停止倒计时并将睡眠定时任务标记为未启用状态。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-006"
          ],
          "output_business_object_numbers": [
            "B-006"
          ],
          "next_steps": []
        },
        {
          "step_number": "S-006",
          "step_name": "执行定时结束行为",
          "step_description": "系统在倒计时结束后按设定执行停止播放或关闭程序等处理动作。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-006",
            "B-002"
          ],
          "output_business_object_numbers": [
            "B-006",
            "B-002"
          ],
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "全局快捷键控制流程",
      "flow_description": "快捷键控制者配置全局快捷键，并通过快捷键快速执行播放、暂停和切歌等控制动作。",
      "feature_ids": [
        23,
        24,
        25
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "设置快捷键映射",
          "step_description": "快捷键控制者为播放暂停、上一首和下一首操作设置全局快捷键组合。",
          "actor_ids": [
            6
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-007"
          ],
          "output_business_object_numbers": [
            "B-007"
          ],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "注册全局快捷键",
          "step_description": "系统保存快捷键配置并向操作系统注册全局监听。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-007"
          ],
          "output_business_object_numbers": [
            "B-007"
          ],
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "触发快捷键操作",
          "step_description": "快捷键控制者在任意界面下按下已配置快捷键，发起播放控制请求。",
          "actor_ids": [
            6
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-007",
            "B-002"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "识别快捷键对应动作",
          "step_description": "系统识别触发的快捷键对应的是播放暂停、上一首还是下一首等操作。",
          "actor_ids": [],
          "step_type": "judgment",
          "input_business_object_numbers": [
            "B-007",
            "B-002"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-005",
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "更新播放状态",
          "step_description": "系统执行播放或暂停操作并更新当前播放会话状态。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-002"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": []
        },
        {
          "step_number": "S-006",
          "step_name": "执行切歌操作",
          "step_description": "系统根据快捷键请求切换上一首或下一首歌曲，并更新当前播放会话。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-002",
            "B-003",
            "B-001"
          ],
          "output_business_object_numbers": [
            "B-002"
          ],
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "界面偏好设置流程",
      "flow_description": "界面偏好设置者调整播放器的显示样式、轻量化布局和视觉风格，以保持清爽纯净的使用体验。",
      "feature_ids": [
        27,
        28,
        29
      ],
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入界面设置",
          "step_description": "界面偏好设置者打开播放器设置并进入界面外观配置区域。",
          "actor_ids": [
            7
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-008"
          ],
          "output_business_object_numbers": [],
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "调整显示样式和布局",
          "step_description": "界面偏好设置者选择界面显示样式、切换轻量化布局，并配置视觉风格偏好。",
          "actor_ids": [
            7
          ],
          "step_type": "actorAction",
          "input_business_object_numbers": [
            "B-008"
          ],
          "output_business_object_numbers": [
            "B-008"
          ],
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "应用界面偏好",
          "step_description": "系统立即应用新的界面风格与布局设置，并更新播放器展示效果。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-008"
          ],
          "output_business_object_numbers": [
            "B-008"
          ],
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "保存界面配置",
          "step_description": "系统保存界面偏好设置，供后续启动播放器时自动生效。",
          "actor_ids": [],
          "step_type": "systemAction",
          "input_business_object_numbers": [
            "B-008"
          ],
          "output_business_object_numbers": [
            "B-008"
          ],
          "next_steps": []
        }
      ]
    }
  ]
}
"""
