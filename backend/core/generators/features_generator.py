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
        )
        if not response:
            raise ValueError("LLM returned an empty response. Please check backend server logs for the detailed LLM connection or settings error.")
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    from backend.schemas import ActorNode

    features_generator = FeaturesGenerator()

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

    async def main():
         await features_generator.generate(
            FeaturesGeneratorInput(user_requirements, test_actors)
        )
    asyncio.run(main())

    features_generator_result = """
{
  "features": [
    {
      "feature_number": "F001",
      "feature_name": "极简纯净本地音乐播放器",
      "feature_description": "系统用于在电脑本地离线播放音乐文件，支持无损与常见音频格式播放，并提供歌词匹配、音效均衡、歌单管理、睡眠定时、全局快捷键和轻量化界面等功能，旨在替代臃肿的主流音乐播放器。",
      "actor_ids": [
        1,
        2,
        3,
        4,
        5,
        6,
        7
      ]
    },
    {
      "feature_number": "F001-001",
      "feature_name": "本地音乐播放管理",
      "feature_description": "支持读取电脑本地音乐文件并进行播放控制、进度调整和格式播放管理。",
      "actor_ids": [
        1
      ]
    },
    {
      "feature_number": "F001-001-001",
      "feature_name": "扫描与导入本地音乐",
      "feature_description": "支持从电脑本地读取、扫描和导入音乐文件，作为播放器的媒体来源。",
      "actor_ids": [
        1
      ]
    },
    {
      "feature_number": "F001-001-002",
      "feature_name": "播放控制",
      "feature_description": "支持播放、暂停、上一首、下一首和播放进度调整等基础播放操作。",
      "actor_ids": [
        1,
        6
      ]
    },
    {
      "feature_number": "F001-001-003",
      "feature_name": "音频格式播放",
      "feature_description": "支持播放本地无损及常见音频格式文件，包括 Flac、WAV 和 MP3。",
      "actor_ids": [
        1
      ]
    },
    {
      "feature_number": "F001-002",
      "feature_name": "歌单自定义管理",
      "feature_description": "支持用户按个人喜好创建、编辑和维护本地音乐歌单。",
      "actor_ids": [
        2,
        1
      ]
    },
    {
      "feature_number": "F001-002-001",
      "feature_name": "新建与删除歌单",
      "feature_description": "支持用户创建新的歌单并删除不再需要的歌单。",
      "actor_ids": [
        2
      ]
    },
    {
      "feature_number": "F001-002-002",
      "feature_name": "添加或移除歌曲",
      "feature_description": "支持用户将本地歌曲添加到歌单中或从歌单中移除。",
      "actor_ids": [
        2,
        1
      ]
    },
    {
      "feature_number": "F001-002-003",
      "feature_name": "歌单排序与自定义内容",
      "feature_description": "支持用户调整歌单内歌曲顺序，并按个人偏好自定义歌单内容。",
      "actor_ids": [
        2
      ]
    },
    {
      "feature_number": "F001-003",
      "feature_name": "歌词匹配与显示",
      "feature_description": "支持本地歌曲歌词自动匹配、显示与同步管理。",
      "actor_ids": [
        4
      ]
    },
    {
      "feature_number": "F001-003-001",
      "feature_name": "本地歌词自动匹配",
      "feature_description": "支持根据本地歌曲自动匹配对应歌词文件或歌词内容。",
      "actor_ids": [
        4
      ]
    },
    {
      "feature_number": "F001-003-002",
      "feature_name": "歌词显示与同步调整",
      "feature_description": "支持在播放界面显示歌词，并调整歌词同步效果以匹配播放进度。",
      "actor_ids": [
        4,
        1
      ]
    },
    {
      "feature_number": "F001-003-003",
      "feature_name": "歌词关联管理",
      "feature_description": "支持用户管理歌词与歌曲的关联结果，便于维护匹配准确性。",
      "actor_ids": [
        4
      ]
    },
    {
      "feature_number": "F001-004",
      "feature_name": "音效与均衡器设置",
      "feature_description": "支持用户根据听感调整音效参数与均衡器配置。",
      "actor_ids": [
        3
      ]
    },
    {
      "feature_number": "F001-004-001",
      "feature_name": "均衡器调节",
      "feature_description": "支持用户调整均衡器各频段参数，以优化不同音乐风格的听感。",
      "actor_ids": [
        3
      ]
    },
    {
      "feature_number": "F001-004-002",
      "feature_name": "音效参数配置",
      "feature_description": "支持用户配置音效相关参数，并保存个人偏好设置。",
      "actor_ids": [
        3
      ]
    },
    {
      "feature_number": "F001-004-003",
      "feature_name": "预设音效切换",
      "feature_description": "支持用户切换系统提供的预设音效方案。",
      "actor_ids": [
        3
      ]
    },
    {
      "feature_number": "F001-005",
      "feature_name": "睡眠定时关闭",
      "feature_description": "支持设置定时关闭播放器，在指定时间自动停止播放并退出或关闭程序。",
      "actor_ids": [
        5
      ]
    },
    {
      "feature_number": "F001-005-001",
      "feature_name": "设置定时关闭时间",
      "feature_description": "支持用户设置播放器在指定时间后自动关闭。",
      "actor_ids": [
        5
      ]
    },
    {
      "feature_number": "F001-005-002",
      "feature_name": "取消定时与查看倒计时",
      "feature_description": "支持用户取消已设置的定时关闭，并查看剩余倒计时。",
      "actor_ids": [
        5
      ]
    },
    {
      "feature_number": "F001-005-003",
      "feature_name": "管理播放结束行为",
      "feature_description": "支持用户配置定时结束后播放器的处理方式，如停止播放或关闭程序。",
      "actor_ids": [
        5
      ]
    },
    {
      "feature_number": "F001-006",
      "feature_name": "全局快捷键控制",
      "feature_description": "支持通过系统全局快捷键快速控制音乐播放。",
      "actor_ids": [
        6
      ]
    },
    {
      "feature_number": "F001-006-001",
      "feature_name": "切歌快捷键设置",
      "feature_description": "支持用户设置全局切歌快捷键，以便快速控制播放。",
      "actor_ids": [
        6
      ]
    },
    {
      "feature_number": "F001-006-002",
      "feature_name": "快捷键播放控制",
      "feature_description": "支持通过全局快捷键执行播放、暂停、上一首和下一首操作。",
      "actor_ids": [
        6,
        1
      ]
    },
    {
      "feature_number": "F001-006-003",
      "feature_name": "快速调节播放状态",
      "feature_description": "支持通过快捷键快速调整当前播放状态，提升操作效率。",
      "actor_ids": [
        6
      ]
    },
    {
      "feature_number": "F001-007",
      "feature_name": "清爽轻量化界面设置",
      "feature_description": "支持配置播放器界面风格与显示方式，保持界面简洁、轻量和低干扰。",
      "actor_ids": [
        7
      ]
    },
    {
      "feature_number": "F001-007-001",
      "feature_name": "界面显示样式调整",
      "feature_description": "支持用户调整界面显示样式，使播放器保持清爽直观。",
      "actor_ids": [
        7
      ]
    },
    {
      "feature_number": "F001-007-002",
      "feature_name": "轻量化布局切换",
      "feature_description": "支持用户切换轻量化布局，减少不必要的视觉元素与操作干扰。",
      "actor_ids": [
        7
      ]
    },
    {
      "feature_number": "F001-007-003",
      "feature_name": "视觉风格与外观偏好管理",
      "feature_description": "支持用户配置播放器视觉风格，满足长期使用中的外观偏好。",
      "actor_ids": [
        7
      ]
    }
  ]
}
"""