"""Метадані аудіофайла для показу лікарю. Без Qt, тож перевіряється звичайним Python."""
from __future__ import annotations

import os
import wave

BYTES_IN_KB = 1024
BYTES_IN_MB = 1024 * 1024
_SECONDS_IN_MINUTE = 60
_SECONDS_IN_HOUR = 3600


def wav_duration_seconds(path: str) -> float | None:
    """Тривалість .wav у секундах; None, якщо файл не читається як wav."""
    try:
        with wave.open(path, "rb") as audio:
            rate = audio.getframerate()
            return audio.getnframes() / rate if rate else None
    except (wave.Error, EOFError, OSError):
        return None


def format_duration(seconds: float) -> str:
    """65 -> '1:05', 3725 -> '1:02:05'."""
    total = int(round(seconds))
    hours, rest = divmod(total, _SECONDS_IN_HOUR)
    minutes, secs = divmod(rest, _SECONDS_IN_MINUTE)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def file_size_bytes(path: str) -> int | None:
    try:
        return os.path.getsize(path)
    except OSError:
        return None
