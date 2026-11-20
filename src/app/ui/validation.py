"""Валідація полів форм. Без Qt, тож логіка перевіряється звичайним Python.

Кожна validate_* повертає текст помилки або None, якщо значення коректне.
"""
from __future__ import annotations

import re

from src.app.ui import metrics, strings

_PHONE_NOISE = re.compile(r"[\s\-().]")
_PHONE_RE = re.compile(r"^\+380\d{9}$")
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$"
)


def collapse_spaces(text: str) -> str:
    """Обрізає краї та замінює послідовності пробілів одним пробілом."""
    return " ".join(text.split())


def _validate_length(text: str, min_len: int, max_len: int) -> str | None:
    value = collapse_spaces(text)
    if not value:
        return strings.VALIDATION_REQUIRED
    if len(value) < min_len:
        return strings.VALIDATION_MIN_LEN.format(min=min_len)
    if len(value) > max_len:
        return strings.VALIDATION_MAX_LEN.format(max=max_len)
    return None


def validate_name(text: str) -> str | None:
    """Прізвище та ім'я: за кількістю символів (після стискання пробілів)."""
    return _validate_length(text, metrics.NAME_MIN_LEN, metrics.NAME_MAX_LEN)


def validate_other(text: str) -> str | None:
    """Власний варіант зі списку («Інше»): коротший ліміт, ніж для імені."""
    return _validate_length(text, metrics.OTHER_MIN_LEN, metrics.OTHER_MAX_LEN)


def normalize_phone(text: str) -> str | None:
    """'+380671234567' -> '+380 67 123 45 67'; None, якщо номер некоректний."""
    digits = _PHONE_NOISE.sub("", text)
    if not _PHONE_RE.match(digits):
        return None
    n = digits[4:]
    return f"+380 {n[0:2]} {n[2:5]} {n[5:7]} {n[7:9]}"


def validate_phone(text: str) -> str | None:
    if not text.strip():
        return strings.VALIDATION_REQUIRED
    return None if normalize_phone(text) else strings.VALIDATION_PHONE


def validate_email(text: str) -> str | None:
    value = text.strip()
    if not value:
        return strings.VALIDATION_REQUIRED
    return None if _EMAIL_RE.match(value) else strings.VALIDATION_EMAIL
