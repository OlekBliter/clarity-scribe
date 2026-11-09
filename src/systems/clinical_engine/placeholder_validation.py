"""Validate LLM placeholder spelling and membership without access to PII."""
import re
from collections.abc import Iterator
from typing import Any

PREFIXES = 'PER|LOC|ORG|TEL|MAIL|DOB|ID'
EXACT = re.compile(rf'\[(?:{PREFIXES})_[0-9]+\]')
# Broad candidates catch obsolete/translated prefixes and malformed tags.
# Bare known prefixes match the variants S6 would attempt to restore as well.
CANDIDATE = re.compile(
    r'\[\s*[^\W\d_]+\s*[_\-]\s*\d+\s*\]?'
    rf'|\[\s*(?:{PREFIXES})\s*\d+\s*\]?'
    rf'|(?<!\w)(?:{PREFIXES})\s*[_\-]\s*\d+\s*\]?',
    re.IGNORECASE,
)


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def allowed_placeholders(transcription: Any) -> set[str]:
    return {tag for text in _strings(transcription) for tag in EXACT.findall(text)}


def invalid_placeholders(value: Any, allowed: set[str]) -> set[str]:
    # Summaries may omit or repeat source tags; only added/altered tags fail.
    return {
        match.group() for text in _strings(value)
        for match in CANDIDATE.finditer(text)
        if match.group() not in allowed or EXACT.fullmatch(match.group()) is None
    }
