import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from google import genai
from pydantic import BaseModel

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from schemas import contracts

class LLM(ABC):
    @abstractmethod
    def query(self, prompt: str, context_json_path: Optional[Path | str] = None) -> str:
        pass


class Gemini(LLM):
    def __init__(
        self,
        model_name: str = "gemini-3.1-flash-lite",
        response_schema: Optional[type[BaseModel]] = contracts.Objective,
        api_key: Optional[str] = None,
    ):
        self.model_name = model_name
        self.response_schema = response_schema
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()

    def query(self, prompt: str, context_json_path: Optional[Path | str] = None) -> str:
        contents: list[Any] = []
        uploaded_file = None

        try:
            if context_json_path:
                uploaded_file = self.client.files.upload(
                    file=str(context_json_path),
                    config={"mime_type": "application/json"}
                )
                contents.append(uploaded_file)

            contents.append(prompt)

            config = {"response_mime_type": "application/json"}
            if self.response_schema:
                config["response_schema"] = self.response_schema

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )
            return response.text

        finally:
            if uploaded_file:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass