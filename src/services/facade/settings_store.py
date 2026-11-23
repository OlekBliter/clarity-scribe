"""Local persistence for application settings and the LLM API key."""
from __future__ import annotations

import json
import os
import tempfile
from threading import Lock
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, set_key


DEFAULTS: dict[str, Any] = {
    "channels_swapped": False,
    "language": "uk",
    "llm_provider": "gemini",
}

_write_lock = Lock()

PROVIDER_ENV_KEYS = {"gemini": "GEMINI_API_KEY"}


def load(data_dir: Path) -> dict[str, Any]:
    """Load settings, falling back to defaults for missing or invalid data."""
    packed = dotenv_values(data_dir / ".env", interpolate=False).get("CLARITYSCRIBE_SETTINGS")
    if packed:
        try:
            values = json.loads(packed)
            if isinstance(values, dict):
                return {**DEFAULTS, **values}
        except ValueError:
            pass
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


def save(data_dir: Path, values: dict[str, Any], api_key: str | None = None) -> None:
    """Commit preferences and a replacement key together, preserving unrelated dotenv entries."""
    with _write_lock:
        _commit(data_dir, values, api_key)


def _commit(data_dir: Path, values: dict[str, Any], api_key: str | None) -> None:
    target = data_dir / ".env"
    options = {key: values[key] for key in DEFAULTS}
    env_name = PROVIDER_ENV_KEYS[options["llm_provider"]]
    if api_key and any(ch in api_key for ch in ("\x00", "\r", "\n")):
        raise ValueError("Некоректний API-ключ")
    with tempfile.NamedTemporaryFile(dir=data_dir, delete=False) as handle:
        stage = Path(handle.name)
    try:
        if target.exists():
            stage.write_bytes(target.read_bytes())
        set_key(str(stage), "CLARITYSCRIBE_SETTINGS", json.dumps(options))
        if api_key:
            set_key(str(stage), env_name, api_key)
        os.chmod(stage, 0o600)
        os.replace(stage, target)
        if api_key:
            os.environ[env_name] = api_key
    finally:
        stage.unlink(missing_ok=True)


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
