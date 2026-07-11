from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from backend.services.llm_handler_service import LLMHandler

# 定义输入参数基类
@dataclass
class GenerateInput:
    pass

# 泛型参数，支持不同子类的输入类型
T = TypeVar('T', bound=GenerateInput)

class BaseGenerator(ABC, Generic[T]):
    def __init__(self):
        self._llm_handler = LLMHandler()

    @abstractmethod
    async def generate(self, input_data: T) -> Any:
        pass
