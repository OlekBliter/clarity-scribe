"""Application facade: the single entry point of the UI.

This module defines the *contract* between the UI (``src/app``) and the backend:

* ``FacadeError`` - the only exception the UI ever sees;
* ``ClarityScribeFacade`` - the abstract interface with the exact shape of every response.

The real implementation (on top of the Orchestrator) and ``ClarityScribeFacadeStub``
(``stub.py``) both subclass ``ClarityScribeFacade``, so they are interchangeable.

Rules:

* every method returns plain ``dict`` / ``list`` / ``str`` / ``int`` / ``bool`` / ``None``;
* nothing here depends on Qt;
* all UI texts live in the UI (``ui/strings.py``); the facade returns *kinds*
  (``"review"``, ``"done"``, ...) instead of captions, except for ready-made
  display lines such as ``"5 сесій • остання 02.10.2026"``;
* times shown to the user are strings ``"mm:ss"``, dates are ``"dd.mm.yyyy"``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable

# on_progress(step, state): step is one of PROCESSING_STEPS, state is "running" or "done".
ProgressCallback = Callable[[str, str], None]

# Orchestrator steps in execution order (S3 steps run for session #1 only).
PROCESSING_STEPS = (
    "s1",
    "s6_sanitize",
    "s2",
    "s3_generate",
    "s3_restore",
    "s4_generate",
    "s4_restore",
    "mark_drafted",
)

# The five rows of the "Обробка запису" panel, in display order.
STAGE_KEYS = ("transcription", "anonymization", "biomarkers", "medical_card", "soap")

# State of one stage row.
STAGE_STATES = ("done", "running", "pending", "not_needed", "error")

# Badge kinds (None = no badge).
BADGE_KINDS = ("review", "approved", "processing", "error")

# Field state kinds of the medical card.
FIELD_STATES = ("normal", "from_conversation", "attention", "contradictory")

# Trend direction kinds.
DIRECTIONS = ("up", "down", "stable")


class FacadeError(Exception):
    """The only exception the UI has to handle.

    Attributes:
        user_message: A ready-to-show Ukrainian message for the error banner.
    """

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class ClarityScribeFacade(ABC):
    """Abstract facade. See the docstring of each method for the response shape."""

    # ------------------------------------------------------------------ patients

    @abstractmethod
    def list_patients(self, query: str = "") -> list[dict[str, Any]]:
        """Return patient rows filtered by a case-insensitive name substring.

        Returns:
            ``[{"patient_id": str, "name": str,
                "subtitle": "5 сесій • остання 02.10.2026" | "Немає сесій",
                "badge": "review" | "approved" | "processing" | "error" | None}]``
            Badge priority: error -> processing -> review -> approved.
        """

    @abstractmethod
    def create_patient(self, contacts: dict[str, Any]) -> str:
        """Create a patient and return ``patient_id``.

        Args:
            contacts: Any subset of ``preferred_name, birth_date, phone, email,
                preferred_channel, emergency_name, emergency_relation, emergency_phone,
                emergency_consent``. All fields are optional.
        """

    @abstractmethod
    def delete_patient(self, patient_id: str) -> None:
        """Delete the patient with all sessions and audio files."""

    @abstractmethod
    def get_patient_profile(self, patient_id: str) -> dict[str, Any]:
        """Return the data of the patient profile screen.

        Returns:
            ``{"patient_id": str, "name": str,
               "contacts_line": "+380... • mail • зручний канал: Telegram",
               "has_card": bool,          # the "Медкартка" button is active
               "has_dynamics": bool,      # >= 2 approved sessions
               "sessions": [              # newest first
                   {"session_id": str, "number": int, "date": "02.10.2026",
                    "subtitle": "SOAP-нотатка" | "SOAP-нотатка • медкартка",
                    "badge": "review" | "approved" | "processing" | "error" | None,
                    "is_ready": bool}]}``  # True -> open SOAP, False -> open progress screen
        """

    # ------------------------------------------------------------ session upload

    @abstractmethod
    def next_session_number(self, patient_id: str) -> int:
        """Return the number to show in the read-only "Номер сесії" field.

        It is the number of the last session if that session has not reached
        ``drafted`` yet (it will be restarted), otherwise ``max + 1``; 1 for a new patient.
        """

    @abstractmethod
    def add_session(
        self, patient_id: str, wav_path: str, language: str, session_date: str
    ) -> str:
        """Register a session (step 0 only) and return ``session_id``.

        Args:
            patient_id: Owner of the session.
            wav_path: Path to a two-channel ``.wav`` file.
            language: Language code, currently only ``"uk"``.
            session_date: ``"YYYY-MM-DD"``.

        Raises:
            FacadeError: Not a two-channel ``.wav``, unreadable file, unknown patient.
        """

    @abstractmethod
    def process_session(
        self, session_id: str, on_progress: ProgressCallback | None = None
    ) -> None:
        """Run the pipeline synchronously until the session is ``drafted``.

        Raises:
            FacadeError: A step failed ("Сталася помилка. Спробуйте ще раз").
        """

    @abstractmethod
    def get_processing_state(self, session_id: str) -> dict[str, Any]:
        """Return the state of the "Обробка запису" panel.

        Returns:
            ``{"stages": [{"key": one of STAGE_KEYS,
                           "state": "done" | "running" | "pending" | "not_needed" | "error"}],
               "error": str | None,   # user message when a stage failed
               "finished": bool}``    # True when the session is drafted or approved
        """

    # --------------------------------------------------------------------- SOAP

    @abstractmethod
    def get_soap(self, session_id: str) -> dict[str, Any]:
        """Return the SOAP screen data.

        Returns:
            ``{"session_id": str, "patient_id": str, "patient_name": str,
               "number": int, "date": "02.10.2026",
               "status": "draft" | "approved", "badge": "review" | "approved",
               "editable": bool,
               "subjective": {"text": str,
                              "sources": [{"segment_id": int, "time": "07:45", "quote": str}]},
               "objective": {"text": str,
                             "chips": [{"metric": str, "value": float, "baseline": float | None,
                                        "arrow": "up" | "down" | None}]},
               "assessment": {"text": str, "basis": "doctor_stated" | "model_synthesis"},
               "plan": [{"text": str, "origin": "doctor_stated" | "recommended"}]}``
        """

    @abstractmethod
    def save_soap(
        self, session_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Save doctor edits (status stays ``draft``).

        Args:
            edits: ``[{"path": "subjective.text" | "objective.text" | "assessment.text"
                       | "plan[<i>].text", "new_value": str}]``
            review_started_at: When the doctor opened the screen.

        Raises:
            FacadeError: The note is already approved or a path is unknown.
        """

    @abstractmethod
    def approve_soap(
        self, session_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Apply edits (if any) and approve the note. Same arguments as ``save_soap``."""

    @abstractmethod
    def get_transcript(self, session_id: str) -> list[dict[str, Any]]:
        """Return transcript lines (raw text: the screen is local).

        Returns:
            ``[{"segment_id": int, "speaker": "DOCTOR" | "PATIENT",
                "start": float, "end": float, "time": "07:45", "text": str}]``
        """

    @abstractmethod
    def get_audio_info(self, session_id: str) -> dict[str, Any]:
        """Return ``{"path": str | None, "duration": float}`` (seconds)."""

    @abstractmethod
    def get_waveform(self, session_id: str) -> list[float]:
        """Return waveform peaks in ``0..1`` (about 900 bins; ``[]`` if unavailable)."""

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete a session.

        Raises:
            FacadeError: Session #1 cannot be deleted while other sessions exist.
        """

    # ------------------------------------------------------------- medical card

    @abstractmethod
    def get_card(self, patient_id: str) -> dict[str, Any]:
        """Return the medical card screen data.

        Returns:
            ``{"patient_id": str, "patient_name": str, "date": "04.09.2026",
               "status": "draft" | "approved", "badge": "review" | "approved",
               "editable": bool,
               "contacts": {"preferred_name": str | None, "birth_date": str | None,
                            "age": int | None, "phone": str | None, "email": str | None,
                            "preferred_channel": str | None,
                            "emergency_name": str | None, "emergency_relation": str | None,
                            "emergency_phone": str | None, "emergency_consent": bool | None},
               "fields": [{"field_id": str,
                           "state": "normal" | "from_conversation" | "attention" | "contradictory",
                           "value": str | bool | None,
                           "contradiction_text": str | None,
                           "sources": [{"segment_id": int, "time": "14:02", "quote": str}],
                           "edited_by_doctor": bool}]}``
            ``fields`` holds the 22 model fields plus the doctor fields
            (``scales.*``, ``hypotheses.*``, ``agreements.*``).

        Raises:
            FacadeError: The patient has no card yet.
        """

    @abstractmethod
    def save_card(
        self, patient_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Save doctor edits of the card. ``edits`` = ``[{"path": field_id, "new_value": ...}]``."""

    @abstractmethod
    def approve_card(
        self, patient_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Apply edits (if any) and approve the card."""

    # ----------------------------------------------------------------- dynamics

    @abstractmethod
    def get_dynamics(self, patient_id: str) -> dict[str, Any]:
        """Return the dynamics screen data.

        Returns:
            ``{"available": bool,           # False when < 2 approved sessions
               "sessions_label": "1–5",
               "trends": [{"metric": str,
                           "values": [{"session_number": int, "value": float}],
                           "slope": float | None,       # per session
                           "direction": "up" | "down" | "stable"}],
               "summary_text": str}``
        """
