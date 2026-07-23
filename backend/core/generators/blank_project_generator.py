from dataclasses import dataclass
import json
from typing import Dict

from backend.core.generators.prompts import blank_project_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput

# 为参与者生成器定义专属的输入类型
@dataclass
class BlankProjectGeneratorInput(GenerateInput):
    user_requirements: str
    knowledge_context: str | None = None

class BlankProjectGenerator(BaseGenerator[BlankProjectGeneratorInput]):
    async def generate(self, input_data: BlankProjectGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        prompt = blank_project_generate_prompt.replace(
            "{{user_requirements}}", user_requirements_
        )
        if input_data.knowledge_context:
            prompt = prompt.replace(
                "# 输出格式说明", f"{input_data.knowledge_context}\n\n# 输出格式说明"
            )

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        if not response:
            raise ValueError("LLM returned an empty response. Please check backend server logs for the detailed LLM connection or settings error.")
        return json.loads(response)
