from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from src.database import Database
from src.database.exceptions import UserInputError
from src.database.repos import (
    BiomarkersRepo,
    MedicalCardsRepo,
    PatientsRepo,
    SessionsRepo,
    SoapNotesRepo,
    TranscriptRepo,
)
from src.schemas.contracts import (
    DoctorCommand,
    MedicalCardData,
    S1Out,
    S2Out,
    S3Out,
    S4Out,
    S5Out,
    S6RestoreOut,
    S6SanitizeOut,
)
from src.services.orchestrator.audio_files import (
    delete_patient_dir,
    delete_session_dir,
    duration_seconds,
    import_wav,
    waveform_peaks,
)
from src.services.orchestrator.builders import (
    build_s1_in,
    build_s2_in,
    build_s3_in,
    build_s4_in,
    build_s5_in,
    build_s6_in,
    sanitized_segments,
)
from src.services.orchestrator.edits import apply_card_edits, apply_soap_edits
from src.services.orchestrator.restore import (
    apply_items_to_s3,
    apply_items_to_s4,
    s3_to_items,
    s4_to_items,
)
from src.services.orchestrator.state import Step, next_step

# System base exceptions (after Stage 0.1 - 0.5)
from src.systems.audio_transcription.exceptions import AudioTranscriptionError
from src.systems.biomarkers import AcousticBiomarkerError
from src.systems.clinical_engine.exceptions import (
    ClinicalEngineError,
    LLMResponseError,
)
from src.systems.longitudinal import LongitudinalError
from src.systems.privacy_ner import NerError

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Base exception for all orchestrator-level errors."""


class InvalidTransitionError(OrchestratorError):
    """Raised when an operation violates session or document state rules."""


class StepFailedError(OrchestratorError):
    """Raised when a pipeline step fails due to a system or validation error."""

    def __init__(self, step_name: str, message: str, cause: Exception | None = None) -> None:
        super().__init__(f"Step '{step_name}' failed: {message}")
        self.step_name = step_name
        self.error_message = message
        self.cause = cause


SYSTEM_ERRORS: tuple[type[Exception], ...] = (
    AudioTranscriptionError,
    AcousticBiomarkerError,
    ClinicalEngineError,
    LongitudinalError,
    NerError,
    ValidationError,
)

REQUIRED_SYSTEM_KEYS: frozenset[str] = frozenset({"s1", "s2", "s3", "s4", "s5", "s6"})


class Orchestrator:
    """Coordinates session processing steps, database transactions, and edits."""

    def __init__(self, db: Database, data_dir: Path, systems: dict[str, Any]) -> None:
        """Initialize the orchestrator with database, storage directory, and systems.

        Args:
            db: Database instance managing SQLite connections and transactions.
            data_dir: Base directory path for local application data and audio files.
            systems: Dictionary mapping keys 's1'..'s6' to system service instances.
        """
        missing = REQUIRED_SYSTEM_KEYS - set(systems.keys())
        if missing:
            raise OrchestratorError(
                f"Missing required system instances: {sorted(missing)}"
            )

        self.db = db
        self.data_dir = Path(data_dir)
        self.systems = systems

        self.patients_repo = PatientsRepo
        self.sessions_repo = SessionsRepo
        self.transcript_repo = TranscriptRepo
        self.biomarkers_repo = BiomarkersRepo
        self.cards_repo = MedicalCardsRepo
        self.soap_repo = SoapNotesRepo

    def _run_step(
        self,
        session_id: str,
        step_name: str,
        work_fn: Callable[[], None],
    ) -> None:
        """Execute a single pipeline step adhering to the golden transaction rules.

        If work_fn raises any exception from SYSTEM_ERRORS, the session status remains
        unchanged, failed_step and error are recorded in a separate transaction,
        and StepFailedError is raised.
        """
        try:
            work_fn()
        except SYSTEM_ERRORS as exc:
            error_text = str(exc)
            logger.error(
                "Pipeline step '%s' failed for session '%s': %s",
                step_name,
                session_id,
                error_text,
            )
            with self.db.transaction() as conn:
                SessionsRepo.set_failure(
                    conn,
                    session_id=session_id,
                    failed_step=step_name,
                    error=error_text,
                )
            raise StepFailedError(
                step_name=step_name,
                message=error_text,
                cause=exc,
            ) from exc


    def _step_s1(self, session_id: str) -> None:
        """Run S1 audio transcription and set status to 'transcribed'."""
        raise NotImplementedError

    def _step_sanitize(self, session_id: str) -> None:
        """Run S6 privacy NER sanitization and set status to 'sanitized'."""
        raise NotImplementedError

    def _step_s2(self, session_id: str) -> None:
        """Run S2 acoustic biomarker extraction and set status to 'analyzed'."""
        raise NotImplementedError

    def _step_s3_generate(self, session_id: str) -> None:
        """Run S3 medical card generation (session #1 only) with LLM retries."""
        raise NotImplementedError

    def _step_s3_restore(self, session_id: str) -> None:
        """Restore sanitized entities in S3 medical card and save as 'draft'."""
        raise NotImplementedError

    def _step_s4_generate(self, session_id: str) -> None:
        """Run S4 SOAP note generation with LLM retries."""
        raise NotImplementedError

    def _step_s4_restore(self, session_id: str) -> None:
        """Restore sanitized entities in S4 SOAP note and save as 'draft'."""
        raise NotImplementedError

    def _step_mark_drafted(self, session_id: str) -> None:
        """Mark session status as 'drafted' once all artifacts are in 'draft'."""
        raise NotImplementedError

    def next_session_number(self, patient_id: str) -> int:
        """Determine the session number for the next or restarted session."""
        raise NotImplementedError

    def register_session(
        self,
        patient_id: str,
        source_wav: Path,
        language_hint: str,
        session_date: str,
    ) -> str:
        """Register a new session or reset an unfinished one with a new WAV file."""
        raise NotImplementedError

    def run_next(self, session_id: str) -> Step | None:
        """Determine and execute the next single pipeline step for a session."""
        raise NotImplementedError

    def run_until_blocked(
        self,
        session_id: str,
        on_progress: Callable[[Step, str], None] | None = None,
    ) -> None:
        """Run pipeline steps sequentially until reaching 'drafted' or 'approved'."""
        raise NotImplementedError

    def apply_doctor_command(self, command: DoctorCommand) -> None:
        """Apply doctor edits or approval to a draft SOAP note or medical card."""
        raise NotImplementedError

    def _maybe_approve_session(self, conn: Any, session_id: str) -> None:
        """Transition session to 'approved' if all required documents are approved."""
        raise NotImplementedError

    def delete_session(self, session_id: str) -> None:
        """Delete a session and its audio folder (blocks deleting #1 if others exist)."""
        raise NotImplementedError

    def delete_patient(self, patient_id: str) -> None:
        """Delete a patient, all associated records, and their audio directory."""
        raise NotImplementedError

    def get_dynamics(self, patient_id: str) -> S5Out | None:
        """Calculate S5 longitudinal dynamics on the fly for >= 2 approved visits."""
        raise NotImplementedError