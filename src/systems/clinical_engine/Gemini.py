import asyncio
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, TypeAdapter

from src.schemas import contracts
from .LLM import LLM
from .exceptions import LLMResponseError, MissingApiKey, ProviderFailure

# google-genai may use its optional aiohttp backend for async requests.
_TRANSPORT_ERRORS = (httpx.TransportError,)
try:
    from aiohttp import ClientConnectionError, ClientPayloadError
except ImportError:
    pass
else:
    _TRANSPORT_ERRORS += (ClientConnectionError, ClientPayloadError)

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

    async def _request(self, prompt: str, config: dict[str, Any]):
        key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not key or not key.strip():
            raise MissingApiKey()
        options = types.HttpOptions(timeout=60_000)
        with genai.Client(api_key=key, http_options=options) as client:
            async with client.aio as api:
                for attempt in range(2):
                    try:
                        return await api.models.generate_content(
                            model=self.model_name, contents=prompt, config=config,
                        )
                    except APIError as exc:
                        if exc.code in (401, 403) or (
                            exc.code == 400 and "api key" in str(exc.message).lower()
                        ):
                            raise ProviderFailure("key_rejected") from exc
                        if exc.code == 429:
                            raise ProviderFailure("rate_limit") from exc
                        if exc.code not in (500, 502, 503, 504):
                            raise ProviderFailure("provider_request") from exc
                        if attempt:
                            raise ProviderFailure("provider_busy") from exc
                        await asyncio.sleep(1)

    def query(
            self,
            prompt: str,
            schema: Optional[type[BaseModel] | Any] = None,
            system_instruction: Optional[str] = None,
    ) -> str:
        config: dict[str, Any] = {"response_mime_type": "application/json"}
        target_schema = schema or self.response_schema
        if target_schema:
            # Send JSON Schema directly so Gemini receives unions and nullable fields.
            config["response_json_schema"] = (
                target_schema if isinstance(target_schema, dict)
                else TypeAdapter(target_schema).json_schema()
            )

        if system_instruction:
            config["system_instruction"] = system_instruction

        try:
            # The deadline covers both attempts together, including the retry delay.
            response = asyncio.run(asyncio.wait_for(self._request(prompt, config), timeout=90))
            text = response.text
            if not text:
                raise LLMResponseError("Gemini returned no content.")
            return text
        except (TimeoutError, httpx.TimeoutException) as error:
            raise ProviderFailure("provider_timeout") from error
        except _TRANSPORT_ERRORS as error:
            raise ProviderFailure("network_unavailable") from error