from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar

from backend.services.llm_handler_service import LLMHandler


# 定义输入参数基类
@dataclass
class FillerInput:
    pass

# 泛型参数，支持不同子类的输入类型
T = TypeVar('T', bound=FillerInput)

class BaseFiller[T: FillerInput](ABC):
    def __init__(self):
        self._llm_handler = LLMHandler()

    @abstractmethod
    async def fill(self, input_data: T) -> Any:
        pass
