"""Compact text rendering of turns for the prompt."""
from __future__ import annotations

from collections.abc import Iterable

from .models import Speaker, Turn


class TurnFormatter:
    """Renders turns as ``[segment_id] <tag>: <text>``, one turn per line.

    Compared with a JSON dump this drops the repeated key names and quoting, and
    it never escapes Cyrillic (an ASCII-escaped dump would be several times
    larger). Times and confidence are intentionally absent: the orchestrator
    resolves quotes and timestamps from stored segments by ``segment_id``.
    """

    _SPEAKER_TAGS = {Speaker.DOCTOR: "Л", Speaker.PATIENT: "П"}

    def format_turn(self, turn: Turn) -> str:
        """Returns the single-line form of one turn."""
        return f"[{turn.segment_id}] {self._SPEAKER_TAGS[turn.speaker]}: {turn.text}"

    def format_turns(self, turns: Iterable[Turn]) -> str:
        """Returns all turns, newline-separated."""
        return "\n".join(self.format_turn(turn) for turn in turns)
