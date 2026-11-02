from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

class LLM(ABC):
    @abstractmethod
    def query(
        self,
        prompt: str,
        schema: type[BaseModel] | Any | None = None,
    ) -> str:
        ...