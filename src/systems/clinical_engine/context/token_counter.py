"""Token estimation behind a small interface."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod


class TokenCounter(ABC):
    """Estimates how many tokens a text costs in the LLM context window."""

    @abstractmethod
    def count(self, text: str) -> int:
        """Returns an estimated token count for the text."""


class HeuristicTokenCounter(TokenCounter):
    """Offline estimator based on the average characters per token.

    It makes no network calls and is deliberately pessimistic (safety factor),
    because under-counting would let an oversized prompt through. Ukrainian
    tokenizes less efficiently than English, so calibrate ``chars_per_token``
    once against the provider's own ``count_tokens``. A counter backed by the
    provider API can replace this class without touching its users.
    """

    def __init__(self, chars_per_token: float = 2.5, safety_factor: float = 1.2) -> None:
        if chars_per_token <= 0 or safety_factor <= 0:
            raise ValueError("chars_per_token and safety_factor must be positive")
        self._chars_per_token = chars_per_token
        self._safety_factor = safety_factor

    def count(self, text: str) -> int:
        if not text:
            return 0
        return math.ceil(len(text) / self._chars_per_token * self._safety_factor)
