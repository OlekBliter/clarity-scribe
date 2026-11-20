"""Короткий опис аудіофайла для картки файла: «розмір · тривалість · мова»."""
from __future__ import annotations

from src.app.ui import audio_meta, strings


def file_meta(path: str, language: str) -> str:
    """'1.2 МБ · 12:05 · Українська'. Невідомі частини (напр. тривалість не-wav) пропускаються."""
    parts: list[str] = []
    size = audio_meta.file_size_bytes(path)
    if size is not None:
        if size >= audio_meta.BYTES_IN_MB:
            parts.append(strings.FILEINFO_SIZE_MB.format(value=size / audio_meta.BYTES_IN_MB))
        else:
            parts.append(strings.FILEINFO_SIZE_KB.format(value=size / audio_meta.BYTES_IN_KB))
    seconds = audio_meta.wav_duration_seconds(path)
    if seconds is not None:
        parts.append(audio_meta.format_duration(seconds))
    if language:
        parts.append(language)
    return strings.FILEINFO_SEPARATOR.join(parts)
