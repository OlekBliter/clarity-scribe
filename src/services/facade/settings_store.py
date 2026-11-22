"""Local persistence for application settings and the LLM API key."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, set_key


DEFAULTS: dict[str, Any] = {
    "channels_swapped": False,
    "language": "uk",
    "llm_provider": "gemini",
}

PROVIDER_ENV_KEYS = {"gemini": "GEMINI_API_KEY"}


def load(data_dir: Path) -> dict[str, Any]:
    """Load settings, falling back to defaults for missing or invalid data."""
    settings_path = Path(data_dir) / "settings.json"
    try:
        values = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return dict(DEFAULTS)

    if not isinstance(values, dict):
        return dict(DEFAULTS)

    result = dict(DEFAULTS)
    result.update(values)
    return result


def save(data_dir: Path, values: dict[str, Any]) -> None:
    """Atomically save application settings without API-key fields."""
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)

    settings_path = directory / "settings.json"
    secret_names = {"api_key", "gemini_api_key", "llm_api_key"}
    saved_values = {
        key: value
        for key, value in values.items()
        if key not in PROVIDER_ENV_KEYS.values()
        and key.lower() not in secret_names
        and not key.upper().endswith("_API_KEY")
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=".settings.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(saved_values, temporary, ensure_ascii=False)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)

        os.replace(temporary_path, settings_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def save_api_key(data_dir: Path, provider: str, key: str) -> None:
    """Save a provider key in the local .env file and current environment."""
    provider = (provider or "").strip().lower()
    env_name = PROVIDER_ENV_KEYS.get(provider)
    if env_name is None:
        raise ValueError("Unknown LLM provider")

    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    set_key(str(directory / ".env"), env_name, key)
    os.environ[env_name] = key


def has_api_key(data_dir: Path, provider: str) -> bool:
    """Return whether a provider has a non-empty key in environment or .env."""
    provider = (provider or "").strip().lower()
    env_name = PROVIDER_ENV_KEYS.get(provider)
    if env_name is None:
        return False

    environment_key = os.getenv(env_name)
    if environment_key and environment_key.strip():
        return True

    file_values = dotenv_values(str(Path(data_dir) / ".env"))
    file_key = file_values.get(env_name)
    return isinstance(file_key, str) and bool(file_key.strip())
