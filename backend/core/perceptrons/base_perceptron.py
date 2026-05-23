from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from backend.services.LLM_service import LLMHandler

# 定义输入参数基类
@dataclass
class PerceptronInput:
    pass

# 泛型参数，支持不同子类的输入类型
T = TypeVar('T', bound=PerceptronInput)

class BasePerceptron(ABC, Generic[T]):
    def __init__(self):
        self._llm_handler = LLMHandler()

    @abstractmethod
    async def perceive(self, input_data: T) -> Any:
        pass