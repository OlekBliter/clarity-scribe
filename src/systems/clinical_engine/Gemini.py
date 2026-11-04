from .LLM import LLM
from pydantic import BaseModel
from google import genai
from typing import Any, Optional

from google.genai.errors import ServerError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .exceptions import ConfigurationError, LLMRequestError

from src.schemas import contracts

from dotenv import load_dotenv
import os

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
        self.api_key = api_key
        self.client = None

    def _get_client(self) -> genai.Client:
        if self.client is None:
            api_key = self.api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ConfigurationError(
                    "GEMINI_API_KEY is not configured. Set it before making an LLM request."
                )
            self.client = genai.Client(api_key=api_key)
        return self.client

    @retry(
        retry=retry_if_exception_type((ServerError, APIError)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _generate_content(
        self,
        prompt: str,
        config: dict[str, Any],
    ) -> Any:
        return self._get_client().models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
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

        try:
            response = self._generate_content(prompt, config)
            return response.text
        except APIError as error:
            raise LLMRequestError(
                "Gemini request failed after the configured retries."
            ) from error