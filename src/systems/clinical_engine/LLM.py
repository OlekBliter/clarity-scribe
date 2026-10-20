from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class LLM(ABC):
    @abstractmethod
    def query(self, prompt: str, context_json_path: Optional[Path | str] = None) -> str:
        pass