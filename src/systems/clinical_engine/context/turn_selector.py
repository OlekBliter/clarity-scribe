"""Strategies that decide which turns are worth sending to the model."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence

from .models import Speaker, Turn

# Words that carry no information when a DOCTOR says them alone.
_DOCTOR_BACKCHANNELS = frozenset({
    "угу", "ага", "мм", "ммм", "м-м", "е", "ее", "ну", "так", "добре",
    "зрозуміло", "ясно", "окей", "ок", "гаразд", "розумію", "чую",
})
_NON_WORD_CHARS = re.compile(r"[^\w\s'’-]")


class TurnSelector(ABC):
    """Picks the turns relevant for one note section (Strategy pattern).

    Each section can have its own selector, so a section that needs different
    context (for example the doctor's closing remarks) does not touch this one.
    """

    @abstractmethod
    def select(self, turns: Sequence[Turn]) -> list[Turn]:
        """Returns the chosen turns in their original order."""


class PatientFocusedSelector(TurnSelector):
    """Keeps everything the patient said and only the doctor lines that give it meaning.

    Rules:
      * every PATIENT turn is kept in full, because recall matters more than
        savings, especially for safety-related statements;
      * a DOCTOR turn is kept only if it is a question, or if it directly precedes
        a very short patient answer ("так", "іноді") that is meaningless alone;
      * pure DOCTOR backchannels ("угу", "добре") are dropped;
      * kept DOCTOR turns that are too long are cut, preserving the final question,
        because the actual question usually sits at the end of a long remark.
    """

    def __init__(self, doctor_context_max_words: int = 40, short_answer_max_words: int = 6) -> None:
        self._max_words = doctor_context_max_words
        self._short_answer_max_words = short_answer_max_words

    def select(self, turns: Sequence[Turn]) -> list[Turn]:
        selected: list[Turn] = []
        for index, turn in enumerate(turns):
            if turn.speaker is Speaker.PATIENT:
                selected.append(turn)
            elif self._doctor_turn_is_useful(turns, index):
                selected.append(self._trim(turn))
        return selected

    def _doctor_turn_is_useful(self, turns: Sequence[Turn], index: int) -> bool:
        text = turns[index].text
        if self._is_backchannel(text):
            return False
        return "?" in text or self._precedes_short_patient_answer(turns, index)

    def _precedes_short_patient_answer(self, turns: Sequence[Turn], index: int) -> bool:
        if index + 1 >= len(turns):
            return False
        following = turns[index + 1]
        return (
            following.speaker is Speaker.PATIENT
            and len(following.text.split()) <= self._short_answer_max_words
        )

    @staticmethod
    def _is_backchannel(text: str) -> bool:
        # "Так?" is a real confirmation question, not a filler.
        if "?" in text:
            return False
        words = _NON_WORD_CHARS.sub("", text.lower()).split()
        return bool(words) and all(word in _DOCTOR_BACKCHANNELS for word in words)

    def _trim(self, turn: Turn) -> Turn:
        """Cuts a long doctor turn to ``max_words``, keeping its last question."""
        text = turn.text
        last_question = text.rfind("?")
        if last_question != -1:
            text = text[: last_question + 1]
        words = text.split()
        if len(words) <= self._max_words:
            return Turn(turn.segment_id, turn.speaker, " ".join(words))
        return Turn(turn.segment_id, turn.speaker, "… " + " ".join(words[-self._max_words:]))
