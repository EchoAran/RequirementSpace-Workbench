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
        )
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    actors_perceptron = ActorsPerceptron()

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
        await actors_perceptron.perceive(
            ActorsPerceptronInput(user_requirements, test_actors)
        )
    asyncio.run(main())

    actors_perceptron_result = """
{
  "perception_description": "需要补充“本地音乐库维护者”参与者。原因是当前参与者主要覆盖播放、歌单、音效、歌词、定时、快捷键和界面偏好等使用层面，但没有明确覆盖“本地音乐文件库的基础维护”这一关键活动，如扫描/刷新本地目录、选择扫描路径、排除目录、去重或合并重复歌曲、修正本地文件标签信息（曲名、歌手、专辑、封面）、批量更新或清理无效条目等。对于一个只读取本地音乐文件、替代主流播放器的产品，这类操作是重要且高频的，需要单独抽象为参与者，以便后续在用例中清晰表达库维护相关的功能边界和流程。补充方式：新增参与者——“本地音乐库维护者：在需要维护和整理本地音乐文件库的场景下，与本地音乐库管理功能发生交互，并可执行选择或配置扫描目录、手动触发扫描或刷新、处理重复歌曲、修正或编辑基础标签信息、移除无效文件记录和维护音乐库结构等操作的用户角色。”"
}
"""
