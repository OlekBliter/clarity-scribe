"""Real facade implementation on top of the Orchestrator.

``ClarityScribeFacadeImpl`` implements every method of ``ClarityScribeFacade``.
Responsibilities are split as follows:

* this module reads the database through repositories, calls the Orchestrator
  for every state change, and translates errors into ``FacadeError``;
* ``views.py`` builds complex responses (SOAP, medical card, sources) from
  plain dicts and never touches the database;
* ``registry.py`` holds pure formatters (dates, ``mm:ss``, badges, stage states).

This module imports the Orchestrator only for type checking, so importing it
does not load ML libraries. ``factory.create_facade`` builds the real instance.
"""
from __future__ import annotations

from functools import wraps
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from src.database.connection import Database
from src.database.repos import (
    BiomarkersRepo,
    MedicalCardsRepo,
    PatientsRepo,
    SessionsRepo,
    SoapNotesRepo,
    TranscriptRepo,
)

from .facade import ClarityScribeFacade, ProgressCallback

from src.database.exceptions import RepositoryError
from src.services.orchestrator.errors import DoctorInputError, StepFailedError
from .facade import FacadeError

if TYPE_CHECKING:
    from src.services.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

_GENERIC_ERROR = "Сталася помилка. Спробуйте ще раз"

# Any callable; lets ``_guard`` return the same type it receives.
F = TypeVar("F", bound=Callable[..., Any])


def _guard(method: F) -> F:
    """Translate backend errors raised by a facade method into ``FacadeError``.

    The UI handles only ``FacadeError``, so every public facade method is
    wrapped with this decorator. Translation rules:

    * ``FacadeError`` is re-raised unchanged;
    * ``DoctorInputError`` (including ``InvalidTransitionError``) becomes
      ``FacadeError`` with the doctor-facing message;
    * ``StepFailedError``, ``RepositoryError`` and ``OSError`` are logged with
      a traceback and become ``FacadeError`` with a generic message;
    * any other exception is a bug and propagates unchanged.

    Args:
        method: The facade method to wrap.

    Returns:
        The wrapped method with the same name, docstring and signature.
    """

    @wraps(method)
    def wrapped(*args, **kwargs):
        """Call ``method`` and translate the expected backend errors."""
        try:
            return method(*args, **kwargs)
        except FacadeError:
            raise
        except DoctorInputError as exc:
            raise FacadeError(str(exc)) from exc
        except (StepFailedError, RepositoryError, OSError) as exc:
            logger.exception(f"Facade call {method.__name__} failed")
            raise FacadeError(_GENERIC_ERROR) from exc

    return wrapped  # type: ignore[return-value]


class ClarityScribeFacadeImpl(ClarityScribeFacade):
    """Facade backed by the Orchestrator and the SQLite database.

    See ``facade.py`` for the exact response shape of every method.
    Reads go to the repositories; every change goes through the Orchestrator.
    """

    def __init__(self, orchestrator: Orchestrator, db: Database) -> None:
        """Store the backend objects and create the repositories.

        Args:
            orchestrator: Performs every state change (create, process, edit,
                approve, delete).
            db: Used for read-only queries that prepare data for the screens.
        """
        self._o = orchestrator
        self._db = db

        # Repositories are stateless; one instance of each is enough.
        self._patients = PatientsRepo()
        self._sessions = SessionsRepo()
        self._transcript = TranscriptRepo()
        self._biomarkers = BiomarkersRepo()
        self._cards = MedicalCardsRepo()
        self._soap = SoapNotesRepo()

    # ------------------------------------------------------------------ patients

    @_guard
    def list_patients(self, query: str = "") -> list[dict[str, Any]]:
        """Patient rows for the main list, filtered by name (read-only)."""
        raise NotImplementedError

    @_guard
    def create_patient(self, contacts: dict[str, Any]) -> str:
        """Create a patient via the Orchestrator and return the new id."""
        raise NotImplementedError

    @_guard
    def delete_patient(self, patient_id: str) -> None:
        """Delete a patient with all sessions via the Orchestrator."""
        raise NotImplementedError

    @_guard
    def get_patient_profile(self, patient_id: str) -> dict[str, Any]:
        """Profile screen: contacts line and the session list (read-only)."""
        raise NotImplementedError

    # ---------------------------------------------------------------- processing

    @_guard
    def next_session_number(self, patient_id: str) -> int:
        """Number the next session of this patient will get."""
        raise NotImplementedError

    @_guard
    def add_session(
        self, patient_id: str, wav_path: str, language: str, session_date: str
    ) -> str:
        """Register a new recording via the Orchestrator and return its id."""
        raise NotImplementedError

    @_guard
    def process_session(
        self, session_id: str, on_progress: ProgressCallback | None = None
    ) -> None:
        """Run the pipeline steps until the session needs the doctor."""
        raise NotImplementedError

    @_guard
    def get_processing_state(self, session_id: str) -> dict[str, Any]:
        """Stage states for the progress screen."""
        raise NotImplementedError

    @_guard
    def delete_session(self, session_id: str) -> None:
        """Delete one session via the Orchestrator."""
        raise NotImplementedError

    # ---------------------------------------------------------------------- SOAP

    @_guard
    def get_soap(self, session_id: str) -> dict[str, Any]:
        """SOAP note of a session, shaped by ``views.py`` (read-only)."""
        raise NotImplementedError

    @_guard
    def save_soap(
        self, session_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Save the doctor's SOAP edits without approving."""
        raise NotImplementedError

    @_guard
    def approve_soap(
        self, session_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Save the doctor's SOAP edits and approve the note."""
        raise NotImplementedError

    @_guard
    def get_transcript(self, session_id: str) -> list[dict[str, Any]]:
        """Transcript segments of a session (read-only)."""
        raise NotImplementedError

    @_guard
    def get_audio_info(self, session_id: str) -> dict[str, Any]:
        """Audio file path and duration for the player (read-only)."""
        raise NotImplementedError

    @_guard
    def get_waveform(self, session_id: str) -> list[float]:
        """Waveform peaks for drawing the audio track (read-only)."""
        raise NotImplementedError

    # -------------------------------------------------------------- medical card

    @_guard
    def get_card(self, patient_id: str) -> dict[str, Any]:
        """Medical card of a patient, shaped by ``views.py`` (read-only)."""
        raise NotImplementedError

    @_guard
    def save_card(
        self, patient_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Save the doctor's card edits without approving."""
        raise NotImplementedError

    @_guard
    def approve_card(
        self, patient_id: str, edits: list[dict[str, Any]], review_started_at: datetime
    ) -> None:
        """Save the doctor's card edits and approve the card."""
        raise NotImplementedError

    # ------------------------------------------------------------------ dynamics

    @_guard
    def get_dynamics(self, patient_id: str) -> dict[str, Any]:
        """Biomarker trends across approved sessions of a patient."""
        raise NotImplementedError
