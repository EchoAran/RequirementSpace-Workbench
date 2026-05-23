from dataclasses import dataclass
import json
from typing import Dict

from backend.core.generators.prompts import actors_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput

# 为参与者生成器定义专属的输入类型
@dataclass
class ActorsGeneratorInput(GenerateInput):
    user_requirements: str
    user_feedback: str | None = None

class ActorsGenerator(BaseGenerator[ActorsGeneratorInput]):
    async def generate(self, input_data: ActorsGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements
        feedback = input_data.user_feedback or ""

        response = await self._llm_handler.call_llm(
            prompt=actors_generate_prompt.replace(
                "{{user_requirements}}", user_requirements_
            ),
            query=feedback,
            print_log=False,
        )
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    actors_generator = ActorsGenerator()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"

    async def main():
         await actors_generator.generate(
            ActorsGeneratorInput(user_requirements)
        )
    asyncio.run(main())

    actors_generator_result = """
{
  "actors": [
    {
      "actor_name": "本地音乐听众",
      "actor_description": "本地音乐听众是指在需要播放和聆听电脑本地音乐文件的场景下，与音乐播放器发生交互，并可执行导入或扫描本地音乐、播放暂停、切换上一首下一首、调整播放进度、管理播放列表和选择音频格式进行播放等操作的用户角色。"
    },
    {
      "actor_name": "歌单管理者",
      "actor_description": "歌单管理者是指在需要按个人喜好整理和归类本地音乐的场景下，与歌单管理功能发生交互，并可执行新建歌单、编辑歌单、添加或移除歌曲、排序歌曲、删除歌单和自定义歌单内容等操作的用户角色。"
    },
    {
      "actor_name": "音效调节者",
      "actor_description": "音效调节者是指在需要根据听感优化音乐播放效果的场景下，与音效设置功能发生交互，并可执行调整均衡器、配置音效参数、切换预设音效和保存个人音效偏好等操作的用户角色。"
    },
    {
      "actor_name": "歌词匹配者",
      "actor_description": "歌词匹配者是指在需要查看本地歌曲对应歌词的场景下，与歌词匹配功能发生交互，并可执行本地歌词自动匹配、查看歌词显示、调整歌词同步效果和管理歌词关联结果等操作的用户角色。"
    },
    {
      "actor_name": "睡眠定时设置者",
      "actor_description": "睡眠定时设置者是指在需要限定音乐播放时长并在指定时间自动关闭播放器的场景下，与睡眠定时功能发生交互，并可执行设置定时关闭时间、取消定时、查看倒计时和管理播放结束行为等操作的用户角色。"
    },
    {
      "actor_name": "快捷键控制者",
      "actor_description": "快捷键控制者是指在需要通过全局快捷键快速控制播放的场景下，与全局快捷键功能发生交互，并可执行设置切歌快捷键、使用快捷键播放暂停、上一首下一首切换和快速调节播放控制等操作的用户角色。"
    },
    {
      "actor_name": "界面偏好设置者",
      "actor_description": "界面偏好设置者是指在需要让播放器保持清爽、轻量和低干扰使用体验的场景下，与界面设置功能发生交互，并可执行调整界面显示样式、切换轻量化布局、配置视觉风格和管理播放器外观偏好的用户角色。"
    }
  ]
}
"""