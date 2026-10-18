from pathlib import Path
from typing import Any

class PromptManager:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir

    def get_prompt(self, prompt_name: str, **kwargs: Any) -> str:
        prompt_path = self.prompts_dir / f"{prompt_name}.txt"
        template = prompt_path.read_text(encoding="utf-8")
        return template.format(**kwargs) if kwargs else template