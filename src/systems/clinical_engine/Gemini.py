import os
import sys

from .LLM import LLM
from pydantic import BaseModel
from google import genai
from typing import Any, Optional
from pathlib import Path

from google.genai.errors import ServerError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from schemas import contracts

from dotenv import load_dotenv

load_dotenv()

class Gemini(LLM):
    def __init__(
        self,
        model_name: str = "gemini-3.1-flash-lite",
        response_schema: Optional[type[BaseModel]] = contracts.S4Out,
        api_key: Optional[str] = None,
    ):
        self.model_name = model_name
        self.response_schema = response_schema
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()

    @retry(
        retry=retry_if_exception_type((ServerError, APIError)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def query(
            self,
            prompt: str,
            schema: Optional[type[BaseModel] | Any] = None
    ) -> str:
        config: dict[str, Any] = {"response_mime_type": "application/json"}
        target_schema = schema or self.response_schema
        if target_schema:
            config["response_schema"] = target_schema

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return response.text