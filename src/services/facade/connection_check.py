"""Minimal LLM connectivity check (Gemini, Groq) for the Settings screen.

Sends no patient data: the request only lists available models, which
validates the API key without generating text. Nothing is stored or logged.
"""
from __future__ import annotations
 
import logging
import os
import time
from typing import Any
 
from src.systems.clinical_engine.exceptions import LLMRequestError
 
logger = logging.getLogger(__name__)
 
# Request timeout in milliseconds (the UI calls this from a background thread).
_TIMEOUT_MS = 10_000
 
# Provider id -> environment variable with the saved key.
_ENV_KEYS = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}

def _result(ok: bool, message:  str, latency_ms: int | None) -> dict[str, Any]:
    """Build the response dict that the facade returns to the UI.

    Args:
        ok: Whether the provider accepted the key.
        message: Doctor-facing text in Ukrainian.
        latency_ms: Round-trip time of a successful request, else ``None``.

    Returns:
        ``{"ok": bool, "message": str, "latency_ms": int | None}``
    """
    return {"ok": ok, "message": message, "latency_ms": latency_ms}

def check_connection(provider: str, api_key: str) -> dict[str, Any]:
    """Check that the provider accepts the key and is reachable.
 
    Args:
        provider: Provider id, ``"gemini"`` or ``"groq"`` (case-insensitive).
        api_key: Key from the settings form. If empty, the saved key
            (environment variable) is used.
 
    Returns:
        ``{"ok": bool, "message": str, "latency_ms": int | None}``. Expected
        failures (bad key, no network, rate limit, timeout) are returned as
        ``ok=False`` with a Ukrainian message for the doctor.
 
    Raises:
        LLMRequestError: The provider failed in an unexpected way.
    """
    provider = (provider or "").strip().lower()
    env_name = _ENV_KEYS.get(provider)
    if env_name is None:
        return _result(False, "Невідомий провайдер LLM", None)
    key = (api_key or "").strip() or os.getenv(env_name, "").strip()
    if not key:
        return _result(False, "Введіть API-ключ", None)
    return _check_gemini(key) if provider == "gemini" else _check_groq(key)


def _check_gemini(api_key: str) -> dict[str, Any]:
    """Validate a Gemini key by requesting one page of the model list.

    Args:
        api_key: Non-empty Gemini API key.

    Returns:
        The ``_result`` dict; network problems and known API errors are
        returned as ``ok=False``.

    Raises:
        LLMRequestError: The API failed with an unexpected error code.
    """
    # Imported here so that importing this module does not load the SDK.
    import httpx
    from google import genai
    from google.genai import errors, types
 
    client = genai.Client(
        api_key=api_key, http_options=types.HttpOptions(timeout=_TIMEOUT_MS)
    )
    started = time.perf_counter()
    try:
        next(iter(client.models.list(config={"page_size": 1})), None)
    except errors.APIError as exc:
        return _from_api_error(exc)
    except httpx.TimeoutException:
        return _result(False, "Час очікування відповіді вичерпано", None)
    except httpx.TransportError:
        return _result(False, "Немає з'єднання з інтернетом", None)
    latency_ms = round((time.perf_counter() - started) * 1000)
    return _result(True, "З'єднання встановлено", latency_ms)


def _check_groq(api_key: str) -> dict[str, Any]:
    """Validate a Groq key with ``GET /models`` of its OpenAI-compatible API.

    Uses plain ``httpx``, so the ``groq`` SDK is not required.

    Args:
        api_key: Non-empty Groq API key, sent only in the request header.

    Returns:
        The ``_result`` dict; network problems and known HTTP errors
        (401/403, 429, 5xx) are returned as ``ok=False``.

    Raises:
        LLMRequestError: The API answered with an unexpected status code.
    """
    import httpx

    started = time.perf_counter()
    try:
        response = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT_MS / 1000,
        )
    except httpx.TimeoutException:
        return _result(False, "Час очікування відповіді вичерпано", None)
    except httpx.TransportError:
        return _result(False, "Немає з'єднання з інтернетом", None)
    code = response.status_code
    if code in (401, 403):
        return _result(False, "Невірний API-ключ", None)
    if code == 429:
        return _result(False, "Перевищено ліміт запитів. Спробуйте пізніше", None)
    if code >= 500:
        return _result(False, "Сервіс провайдера тимчасово недоступний", None)
    if code != 200:
        raise LLMRequestError(f"Unexpected provider error (code {code})")
    return _result(True, "З'єднання встановлено", round((time.perf_counter() - started) * 1000))
 
 
def _from_api_error(exc: Exception) -> dict[str, Any]:
    """Map a provider API error to a doctor-facing result."""
    code = getattr(exc, "code", None)
    text = str(getattr(exc, "message", "") or "").lower()
    if code in (401, 403) or "api key" in text:
        return _result(False, "Невірний API-ключ", None)
    if code == 429:
        return _result(False, "Перевищено ліміт запитів. Спробуйте пізніше", None)
    if isinstance(code, int) and code >= 500:
        return _result(False, "Сервіс провайдера тимчасово недоступний", None)
    raise LLMRequestError(f"Unexpected provider error (code {code})") from exc