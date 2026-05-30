from dataclasses import dataclass
import json
from typing import Dict

from backend.core.generators.prompts import blank_project_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput

# 为参与者生成器定义专属的输入类型
@dataclass
class BlankProjectGeneratorInput(GenerateInput):
    user_requirements: str

class BlankProjectGenerator(BaseGenerator[BlankProjectGeneratorInput]):
    async def generate(self, input_data: BlankProjectGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        response = await self._llm_handler.call_llm(
            prompt=blank_project_generate_prompt.replace(
                "{{user_requirements}}", user_requirements_
            ),
            print_log=False,
        )
        if not response:
            raise ValueError("LLM returned an empty response. Please check backend server logs for the detailed LLM connection or settings error.")
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    blank_project_generator = BlankProjectGenerator()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"

    async def main():
         await blank_project_generator.generate(
            BlankProjectGeneratorInput(user_requirements)
        )
    asyncio.run(main())

    blank_project_generator_result = """
{
    "project_name": "极简本地纯净音乐播放器",
    "project_description": "系统是一款完全离线、无广告无会员的本地音乐播放器，仅读取并播放用户电脑中的音乐文件，支持 Flac、WAV、MP3 等无损及常见格式。系统提供本地歌词自动匹配与显示、音效均衡器、用户自定义歌单管理、睡眠定时关闭和全局快捷键切歌等功能，并以清爽、轻量化的界面设计替代臃肿复杂的主流音乐播放器，专注于纯粹的本地听歌体验。"
}
"""