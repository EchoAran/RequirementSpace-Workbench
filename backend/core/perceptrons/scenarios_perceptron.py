from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.prompts import scenarios_perceive_prompt
from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.schemas import ActorNode, FeatureNode, ScenarioNode


# 为场景感知器定义专属的输入类型
@dataclass
class ScenariosPerceptronInput(PerceptronInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]

class ScenariosPerceptron(BasePerceptron[ScenariosPerceptronInput]):
    async def perceive(self, input_data: ScenariosPerceptronInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        actor_ = ActorNode.schema(
            only=(
                "actorName",
                "actorDescription",
            ),
        ).dumps(
            input_data.actor,
            ensure_ascii=False,
            indent=2,
        )

        feature_ = FeatureNode.schema(
            only=(
                "featureName",
                "featureDescription",
            ),
        ).dumps(
            input_data.feature,
            ensure_ascii=False,
            indent=2,
        )

        scenarios_payload = ScenarioNode.schema(
            many=True,
            only=(
                "scenarioName",
                "scenarioContent",
            ),
        ).dump(input_data.scenarios)

        scenarios_ = json.dumps(
            {
                "scenarios": scenarios_payload,
            },
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=scenarios_perceive_prompt.replace(
                "{{user_requirements}}",
                user_requirements_,
            ).replace(
                "{{actor}}",
                actor_,
            ).replace(
                "{{feature}}",
                feature_,
            ).replace(
                "{{scenarios}}",
                scenarios_,
            ),
            print_log=False,
        )

        return json.loads(response)


if __name__ == "__main__":
    import asyncio
    scenarios_perceptron = ScenariosPerceptron()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"

    test_actor = ActorNode(
        actorId=1,
        actorName="普通用户",
        actorDescription="使用系统进行日常操作的注册用户，拥有基本的浏览、查询和操作权限"
    )

    test_feature = FeatureNode(
        featureId=1,
        featureName="本地文件读取",
        featureDescription="仅从电脑本地读取音乐文件，不依赖网络资源或在线音乐服务",
        actorIds=[1],
        childrenIds=[],  # 无子功能，为叶子节点
    )

    test_scenarios = [
        ScenarioNode(
            scenarioId=1,
            scenarioName="从本地文件夹导入音乐文件",
            scenarioContent="As a 普通用户, I want to 直接从电脑本地文件夹读取音乐文件, So that 我可以在不联网的情况下快速导入自己的歌曲并开始播放",
            featureId=1,
            actorId=1,
        ),
        ScenarioNode(
            scenarioId=2,
            scenarioName="扫描本地音乐库中的无损和常见音频格式",
            scenarioContent="As a 普通用户, I want to 从本地读取 Flac、WAV 和 MP3 等音乐文件, So that 我可以统一管理并播放电脑中保存的不同格式音乐",
            featureId=1,
            actorId=1,
        ),
        ScenarioNode(
            scenarioId=3,
            scenarioName="仅使用本地音乐资源构建播放器曲库",
            scenarioContent="As a 普通用户, I want to 让播放器只读取电脑本地音乐文件而不依赖在线资源, So that 我可以在离线环境下稳定使用播放器并避免网络内容干扰",
            featureId=1,
            actorId=1,
        ),
        ScenarioNode(
            scenarioId=4,
            scenarioName="离线浏览本地音乐列表并选择播放",
            scenarioContent="As a 普通用户, I want to 浏览本地读取到的音乐列表并直接选择歌曲播放, So that 我可以快速找到想听的音乐而无需登录或搜索在线曲库",
            featureId=1,
            actorId=1,
        ),
    ]

    async def main():
        await scenarios_perceptron.perceive(
            ScenariosPerceptronInput(user_requirements, test_actor, test_feature, test_scenarios)
        )
    asyncio.run(main())

    scenarios_perceptron_result = """
{
  "perception_description": "需要。当前用户故事覆盖了“能从本地获取并播放音乐”的主路径，但对本地文件读取这一能力在真实使用中的几个关键补充场景尚未体现：\n1）需要补充“从不同来源位置读取本地音乐”的用户故事，例如从外接硬盘/U 盘、移动设备挂载盘或自定义路径导入音乐库。原因是普通用户的音乐文件通常不会只集中在一个固定文件夹中，支持多路径与可配置路径是本地读取能力的核心要求。可增加类似场景：As a 普通用户, I want to 从多个本地路径（含外接设备）选择并导入音乐文件, So that 我可以统一管理分散在不同磁盘和设备中的本地音乐。\n2）需要补充“处理本地文件变化（新增、删除、移动）”的用户故事，例如自动/手动刷新扫描结果，处理失效文件路径。原因是本地文件夹结构会发生变化，若播放器曲库不随之更新，将导致大量“灰色歌曲”或点击播放失败。可增加场景：As a 普通用户, I want to 在本地文件变化时通过自动或手动刷新更新曲库, So that 我可以保证播放器中的本地音乐列表与电脑实际文件保持一致。\n3）需要补充“导入和扫描过程的可控性与反馈”的用户故事，例如展示扫描进度、允许取消扫描、跳过错误文件并给出提示。原因是本地音乐库可能很大，若没有过程反馈与异常处理，会影响使用体验。可增加场景：As a 普通用户, I want to 在本地扫描音乐时看到进度并获得错误提示, So that 我可以知道扫描大概需要多久并了解哪些文件未被成功导入。\n4）需要补充“本地文件筛选与基础管理”的用户故事，例如按文件夹、文件名、时长、格式等对已读取的本地文件进行简单管理（重建索引、不重复导入等）。原因是本地读取不仅是一次性导入，还涉及后续的组织与维持。可增加场景：As a 普通用户, I want to 对已读取的本地音乐列表进行基础整理（去重、按文件夹查看）, So that 我可以更高效地管理已经导入播放器的本地音乐。通过补充上述用户故事，可以让‘本地文件读取’从单纯的“能读”扩展为“能灵活选择来源、能应对文件变化、能对过程有感知、能维持可用的本地曲库”，从而更完整地支撑该 feature 的设计与实现。"
}
"""
