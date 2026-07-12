from dataclasses import dataclass
import json
from typing import Dict

from backend.core.generators.prompts import scenarios_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.schemas import FeatureNode, ActorNode

# 为场景生成器定义专属的输入类型
@dataclass
class ScenariosGeneratorInput(GenerateInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    user_feedback: str | None = None

class ScenariosGenerator(BaseGenerator[ScenariosGeneratorInput]):
    async def generate(self, input_data: ScenariosGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements
        feedback = input_data.user_feedback or ""

        actor_ = ActorNode.schema(
            only=("actorName", "actorDescription")
        ).dumps(
            input_data.actor,
            indent=2,
            ensure_ascii=False
        )

        feature_ = FeatureNode.schema(
            only=("featureName", "featureDescription")
        ).dumps(
            input_data.feature,
            indent=2,
            ensure_ascii=False
        )

        response = await self._llm_handler.call_llm(
            prompt=scenarios_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{actor}}",f"{actor_}").replace(
                "{{feature}}", f"{feature_}"
            ),
            query=feedback,
            print_log=False,
        )
        if response is None:
            raise ValueError("invalid_llm_response")
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    from backend.schemas import FeatureNode, ActorNode
    scenarios_generator = ScenariosGenerator()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"

    test_actor = ActorNode(
        actorId=1,
        actorName="本地音乐听众",
        actorDescription="本地音乐听众是指在需要播放和聆听电脑本地音乐文件的场景下，与音乐播放器发生交互，并可执行导入或扫描本地音乐、播放暂停、切换上一首下一首、调整播放进度、管理播放列表和选择音频格式进行播放等操作的用户角色。"
    )

    test_feature = FeatureNode(
        featureId=1,
        featureName="扫描与导入本地音乐",
        featureDescription="支持从电脑本地读取、扫描和导入音乐文件，作为播放器的媒体来源。",
        actorIds=[1],
        childrenIds=[],  # 无子功能，为叶子节点
    )

    async def main():
        await scenarios_generator.generate(
            ScenariosGeneratorInput(user_requirements, test_actor, test_feature)
        )

    asyncio.run(main())

    scenarios_generator_result = """
{
    "scenarios": [
        {
            "scenario_name": "扫描本地音乐目录",
            "scenario_content": "As a 本地音乐听众, I want to 扫描电脑中的本地音乐目录, So that 我可以一次性将所有本地音乐文件加入播放器作为播放来源"
        },
        {
            "scenario_name": "导入指定本地音乐文件",
            "scenario_content": "As a 本地音乐听众, I want to 从本地磁盘中手动选择并导入指定音乐文件或文件夹, So that 我可以精确控制哪些音乐加入播放器库"
        },
        {
            "scenario_name": "支持多种无损与常见格式导入",
            "scenario_content": "As a 本地音乐听众, I want to 在扫描与导入时支持 Flac/WAV/MP3 等格式, So that 我可以无缝播放自己本地收藏的无损与有损音乐"
        },
        {
            "scenario_name": "读取并展示本地音乐信息",
            "scenario_content": "As a 本地音乐听众, I want to 在扫描与导入时自动读取歌曲名称、专辑、歌手等标签信息, So that 我可以在播放器中清晰地识别和管理已导入的歌曲"
        },
        {
            "scenario_name": "建立纯本地音乐媒体库",
            "scenario_content": "As a 本地音乐听众, I want to 将扫描或导入的音乐文件构建成本地媒体库且不依赖网络, So that 我可以在一个纯本地、无广告、无账号登录的环境中播放音乐"
        },
        {
            "scenario_name": "更新本地音乐库",
            "scenario_content": "As a 本地音乐听众, I want to 重新扫描或增量扫描本地音乐目录, So that 我在新增或删除本地音乐文件后可以快速更新播放器中的歌曲列表"
        }
    ]
}
"""
