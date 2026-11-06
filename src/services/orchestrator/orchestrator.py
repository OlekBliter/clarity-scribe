from __future__ import annotations

import os
import shutil
import tempfile
import logging

from datetime import date
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from src.database.connection import Database
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

        self.patients_repo = PatientsRepo()
        self.sessions_repo = SessionsRepo()
        self.transcript_repo = TranscriptRepo()
        self.biomarkers_repo = BiomarkersRepo()
        self.cards_repo = MedicalCardsRepo()
        self.soap_repo = SoapNotesRepo()

    @staticmethod
    def _audio_relative_path(patient_id: str, session_id: str) -> str:
        """Build a portable audio path relative to the data directory."""
        return (Path("audio") / patient_id / session_id / "audio.wav").as_posix()

    def _audio_path(self, patient_id: str, session_id: str) -> Path:
        """Return the absolute path to a session's WAV file."""
        return self.data_dir / self._audio_relative_path(patient_id, session_id)

    @staticmethod
    def _backup_audio(path: Path) -> Path | None:
        """Back up an existing WAV before a session is restarted."""
        if not path.exists():
            return None
        if not path.is_file():
            raise UserInputError("Session audio path is not a file")

        backup: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=".backup-", suffix=".wav", dir=path.parent, delete=False,
            ) as tmp:
                backup = Path(tmp.name)
            shutil.copy2(path, backup)
            return backup
        except OSError as exc:
            if backup is not None:
                try:
                    backup.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    logger.warning("Cannot remove backup %s: %s", backup, cleanup_error)
            raise UserInputError("Не вдалося створити резервну копію аудіо") from exc

    @staticmethod
    def _remove_backup(backup: Path | None) -> None:
        """Remove a temporary backup, reporting filesystem errors in logs."""
        if backup is None:
            return
        try:
            backup.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to remove backup %s: %s", backup, exc)

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
                self.sessions_repo.set_failure(
                    conn, session_id, step_name, error_text,
                )
            raise StepFailedError(
                step_name=step_name,
                message=error_text,
                cause=exc,
            ) from exc


    def _step_s1(self, session_id: str) -> None:
        """Transcribe session audio and atomically save transcript and status."""

        def work() -> None:
            with self.db.read() as conn:
                session = self.sessions_repo.get(conn, session_id)

            request = build_s1_in(session, self.data_dir)
            response = self.systems["s1"].transcribe(request)
            output = S1Out.model_validate(response)

            with self.db.transaction() as conn:
                self.transcript_repo.replace_segments(
                    conn,
                    session_id,
                    [segment.model_dump(mode="json") for segment in output.segments],
                )
                self.sessions_repo.save_s1_result(
                    conn,
                    session_id,
                    output.language,
                    output.metadata.model_dump(mode="json"),
                )
                self.sessions_repo.set_status(conn, session_id, "transcribed")

        self._run_step(session_id, Step.S1.value, work)

    def _step_sanitize(self, session_id: str) -> None:
        """Sanitize raw transcript text and persist NER state atomically."""

        def work() -> None:
            with self.db.read() as conn:
                session = self.sessions_repo.get(conn, session_id)
                segments = self.transcript_repo.get_segments(conn, session_id)

            items = [
                {"key": f"seg:{segment['segment_id']}", "text": segment["text_raw"]}
                for segment in segments
            ]
            request = build_s6_in("sanitize", items, session.get("ner_map") or {})
            response = self.systems["s6"].process(request)
            output = S6SanitizeOut.model_validate(response)

            # Refuse incomplete, duplicated, or fabricated segment identifiers.
            expected_keys = {item["key"] for item in items}
            received_keys = [item.key for item in output.items]
            if len(received_keys) != len(items) or set(received_keys) != expected_keys:
                raise NerError("Sanitization returned missing or unexpected segment keys")

            sanitized = {
                int(item.key.removeprefix("seg:")): item.text
                for item in output.items
            }
            with self.db.transaction() as conn:
                self.transcript_repo.set_sanitized(conn, session_id, sanitized)
                self.sessions_repo.save_ner_map(
                    conn, session_id, {key: value.model_dump(mode="json") for key, value in output.map.items()}
                )
                self.sessions_repo.set_status(conn, session_id, "sanitized")

        self._run_step(session_id, Step.S6_SANITIZE.value, work)

    def _step_s2(self, session_id: str) -> None:
        """Compute acoustic biomarkers and atomically save analysis and status."""

        def work() -> None:
            with self.db.read() as conn:
                session = self.sessions_repo.get(conn, session_id)
                segments = self.transcript_repo.get_segments(conn, session_id)

            request = build_s2_in(session, segments, self.data_dir)
            response = self.systems["s2"].extract_biomarkers(request)
            output = S2Out.model_validate(response)

            with self.db.transaction() as conn:
                self.biomarkers_repo.upsert(conn, session_id, output.model_dump(mode="json"))
                self.sessions_repo.set_status(conn, session_id, "analyzed")

        self._run_step(session_id, Step.S2.value, work)

    @staticmethod
    def _validate_clinical_output(
        response: dict[str, Any],
        model_type: type[S3Out] | type[S4Out],
        known_segment_ids: set[int],
    ) -> S3Out | S4Out:
        """Validate generated content and its references to real transcript segments.

        The S4 contract has no check_evidence method, so the orchestrator
        checks subjective.source_segments explicitly instead.
        """
        try:
            output = model_type.model_validate(response)
            if isinstance(output, S3Out):
                output.check_evidence(known_segment_ids)
            else:
                unknown = set(output.subjective.source_segments) - known_segment_ids
                if unknown:
                    raise ValueError("SOAP source_segments reference unknown transcript segments")
            return output
        except (ValidationError, ValueError) as exc:
            raise LLMResponseError("LLM response failed schema or evidence validation") from exc

    def _generate_clinical_with_retry(
        self,
        generate: Callable[[], dict[str, Any]],
        model_type: type[S3Out] | type[S4Out],
        known_segment_ids: set[int],
        step_name: str,
    ) -> S3Out | S4Out:
        """Retry only malformed LLM responses, at most two additional times.

        The Gemini client handles its own network retries. Errors other than
        LLMResponseError propagate without an orchestrator retry.
        """
        for attempt in range(3):
            try:
                return self._validate_clinical_output(
                    generate(), model_type, known_segment_ids
                )
            except LLMResponseError:
                if attempt == 2:
                    raise
                logger.warning(
                    "Invalid %s response; retrying complete call (%s/2)",
                    step_name,
                    attempt + 1,
                )
        raise OrchestratorError("Unreachable clinical generation retry state")

    def _step_s3_generate(self, session_id: str) -> None:
        """Generate S3 for session #1, storing only a sanitized generated draft."""
        def work() -> None:
            with self.db.read() as conn:
                session = self.sessions_repo.get(conn, session_id)
                if session["session_number"] != 1 or session["status"] != "analyzed":
                    raise InvalidTransitionError("S3 is permitted only for analyzed session #1")
                card = self.cards_repo.find(conn, session["patient_id"])
                if card is not None:
                    if card["source_session_id"] != session_id:
                        raise InvalidTransitionError("Existing card belongs to a different session")
                    if card["status"] in ("generated", "draft", "approved"):
                        return
                segments = self.transcript_repo.get_segments(conn, session_id)

            # Sanitize once; never send raw text to S3.
            request = build_s3_in(segments)
            known_ids = {segment["segment_id"] for segment in segments}
            output = self._generate_clinical_with_retry(
                lambda: self.systems["s3"].generate_medical_card(request),
                S3Out, known_ids, Step.S3_GENERATE.value,
            )

            with self.db.transaction() as conn:
                self.cards_repo.save_generated(
                    conn, session["patient_id"], session_id, output.model_dump(mode="json")
                )
                # The session remains 'analyzed' until both documents are restored.
                self.sessions_repo.clear_failure(conn, session_id)

        self._run_step(session_id, Step.S3_GENERATE.value, work)

    def _step_s3_restore(self, session_id: str) -> None:
        """Restore the stored S3 result using S6 without calling the LLM."""
        def work() -> None:
            with self.db.read() as conn:
                session = self.sessions_repo.get(conn, session_id)
                if session["session_number"] != 1 or session["status"] != "analyzed":
                    raise InvalidTransitionError("S3 restore requires analyzed session #1")
                card = self.cards_repo.get(conn, session["patient_id"])
                if card["source_session_id"] != session_id:
                    raise InvalidTransitionError("Medical card belongs to another session")
                if card["status"] in ("draft", "approved"):
                    return
                if card["status"] != "generated":
                    raise InvalidTransitionError("Medical card is not generated")

            original = S3Out.model_validate(card["draft"])
            items = s3_to_items(original)
            response = self.systems["s6"].process(
                build_s6_in("restore", items, session.get("ner_map") or {})
            )
            restored = S6RestoreOut.model_validate(response)
            output = apply_items_to_s3(original, restored)

            with self.db.transaction() as conn:
                self.cards_repo.save_restored(
                    conn, session["patient_id"], output.model_dump(mode="json")
                )
                self.sessions_repo.clear_failure(conn, session_id)

        self._run_step(session_id, Step.S3_RESTORE.value, work)

    def _step_s4_generate(self, session_id: str) -> None:
        """Generate S4 using the current session's sanitized transcript and S2 output."""
        def work() -> None:
            with self.db.read() as conn:
                session = self.sessions_repo.get(conn, session_id)
                if session["status"] != "analyzed":
                    raise InvalidTransitionError("SOAP generation requires analyzed session")
                if session["session_number"] == 1:
                    card = self.cards_repo.find(conn, session["patient_id"])
                    if card is None or card["status"] not in ("draft", "approved"):
                        raise InvalidTransitionError("Session #1 medical card must be restored first")
                note = self.soap_repo.find(conn, session_id)
                if note is not None and note["status"] in ("generated", "draft", "approved"):
                    return
                segments = self.transcript_repo.get_segments(conn, session_id)
                biomarkers = self.biomarkers_repo.get(conn, session_id)

            request = build_s4_in(segments, biomarkers)
            known_ids = {segment["segment_id"] for segment in segments}
            output = self._generate_clinical_with_retry(
                lambda: self.systems["s4"].generate_soap_note(request),
                S4Out, known_ids, Step.S4_GENERATE.value,
            )

            with self.db.transaction() as conn:
                self.soap_repo.save_generated(conn, session_id, output.model_dump(mode="json"))
                self.sessions_repo.clear_failure(conn, session_id)

        self._run_step(session_id, Step.S4_GENERATE.value, work)

    def _step_s4_restore(self, session_id: str) -> None:
        """Restore generated SOAP text using S6 without another LLM call."""
        def work() -> None:
            with self.db.read() as conn:
                session = self.sessions_repo.get(conn, session_id)
                if session["status"] != "analyzed":
                    raise InvalidTransitionError("SOAP restore requires analyzed session")
                note = self.soap_repo.get(conn, session_id)
                if note["status"] in ("draft", "approved"):
                    return
                if note["status"] != "generated":
                    raise InvalidTransitionError("SOAP note is not generated")

            original = S4Out.model_validate(note["draft"])
            items = s4_to_items(original)
            response = self.systems["s6"].process(
                build_s6_in("restore", items, session.get("ner_map") or {})
            )
            restored = S6RestoreOut.model_validate(response)
            output = apply_items_to_s4(original, restored)

            with self.db.transaction() as conn:
                self.soap_repo.save_restored(conn, session_id, output.model_dump(mode="json"))
                self.sessions_repo.clear_failure(conn, session_id)

        self._run_step(session_id, Step.S4_RESTORE.value, work)

    def _step_mark_drafted(self, session_id: str) -> None:
        """Finalize the pipeline only when the required documents are restored."""
        def work() -> None:
            with self.db.transaction() as conn:
                session = self.sessions_repo.get(conn, session_id)
                if session["status"] != "analyzed":
                    raise InvalidTransitionError("Only analyzed sessions may become drafted")
                note = self.soap_repo.find(conn, session_id)
                if note is None or note["status"] not in ("draft", "approved"):
                    raise InvalidTransitionError("SOAP note must be restored before drafting")
                if session["session_number"] == 1:
                    card = self.cards_repo.find(conn, session["patient_id"])
                    if card is None or card["status"] not in ("draft", "approved"):
                        raise InvalidTransitionError("Medical card must be restored before drafting")
                self.sessions_repo.set_status(conn, session_id, "drafted")

        self._run_step(session_id, Step.MARK_DRAFTED.value, work)

    def next_session_number(self, patient_id: str) -> int:
        """Return the previous unfinished session number or the next number."""
        with self.db.read() as conn:
            self.patients_repo.get(conn, patient_id)
            sessions = self.sessions_repo.list_by_patient(conn, patient_id)

        if not sessions:
            return 1
        latest = sessions[0]  # list_by_patient orders by session_number DESC
        if latest["status"] not in ("drafted", "approved"):
            return latest["session_number"]
        return latest["session_number"] + 1

    def register_session(
        self,
        patient_id: str,
        source_wav: str | Path,
        language_hint: str,
        session_date: str,
    ) -> str:
        """Create a new session or restart the latest unfinished session.

        Database changes are committed before any backup is discarded. If the
        transaction fails, the previous WAV is restored (on restart), or a new
        session's audio directory is removed (on creation).
        """
        if language_hint != "uk":
            raise UserInputError("Unsupported language: only 'uk' is available")
        if not isinstance(session_date, str):
            raise UserInputError("Session date must use YYYY-MM-DD format")
        try:
            if date.fromisoformat(session_date).isoformat() != session_date:
                raise ValueError("noncanonical date")
        except ValueError as exc:
            raise UserInputError("Session date must use YYYY-MM-DD format") from exc

        session_id: str | None = None
        retry_path: Path | None = None
        backup_path: Path | None = None
        is_new = False
        audio_installed = False
        committed = False

        try:
            # BEGIN IMMEDIATE serializes creation of session numbers for a patient.
            with self.db.transaction() as conn:
                self.patients_repo.get(conn, patient_id)
                sessions = self.sessions_repo.list_by_patient(conn, patient_id)
                latest = sessions[0] if sessions else None
                unfinished = latest is not None and latest["status"] not in (
                    "drafted", "approved"
                )

                if unfinished:
                    session_id = latest["session_id"]
                    retry_path = self._audio_path(patient_id, session_id)
                    backup_path = self._backup_audio(retry_path)
                    import_wav(source_wav, self.data_dir, patient_id, session_id)
                    audio_installed = True
                    self.sessions_repo.update_language(conn, session_id, language_hint)
                    self.sessions_repo.reset_pipeline(conn, session_id)
                else:
                    number = self.sessions_repo.max_number(conn, patient_id)
                    number = 1 if number is None else number + 1
                    session_id = self.sessions_repo.create(
                        conn,
                        patient_id,
                        number,
                        session_date,
                        "",  # replaced by update_audio_path before commit
                        {"DOCTOR": 0, "PATIENT": 1},
                        language_hint,
                    )
                    is_new = True
                    import_wav(source_wav, self.data_dir, patient_id, session_id)
                    audio_installed = True
                    self.sessions_repo.update_audio_path(
                        conn,
                        session_id,
                        self._audio_relative_path(patient_id, session_id),
                    )
            committed = True
            if session_id is None:
                raise OrchestratorError("Session registration returned no identifier")
            return session_id
        finally:
            # This runs *after* the database context manager, including commit.
            if not committed and session_id is not None:
                if is_new:
                    delete_session_dir(self.data_dir, patient_id, session_id)
                elif audio_installed and retry_path is not None:
                    if backup_path is not None:
                        try:
                            os.replace(backup_path, retry_path)
                        except OSError as exc:
                            logger.error(
                                "Failed to restore session audio %s from %s: %s",
                                retry_path, backup_path, exc,
                            )
                            # Preserve the backup for manual recovery.
                            backup_path = None
                    else:
                        delete_session_dir(self.data_dir, patient_id, session_id)
            self._remove_backup(backup_path)

    def _get_next_step(self, session_id: str) -> Step | None:
        """Return the next executable step, refusing implicit failed-step retries."""
        with self.db.read() as conn:
            session = self.sessions_repo.get(conn, session_id)
            if session.get("failed_step") is not None:
                raise InvalidTransitionError(
                    "Обробка завершилася помилкою. Додайте запис повторно."
                )
            card = self.cards_repo.find(conn, session["patient_id"])
            note = self.soap_repo.find(conn, session_id)
        return next_step(session, card, note)

    def _execute_step(self, session_id: str, current_step: Step) -> None:
        """Dispatch one pipeline step to its corresponding handler."""
        handlers = {
            Step.S1: self._step_s1,
            Step.S6_SANITIZE: self._step_sanitize,
            Step.S2: self._step_s2,
            Step.S3_GENERATE: self._step_s3_generate,
            Step.S3_RESTORE: self._step_s3_restore,
            Step.S4_GENERATE: self._step_s4_generate,
            Step.S4_RESTORE: self._step_s4_restore,
            Step.MARK_DRAFTED: self._step_mark_drafted,
        }
        handlers[current_step](session_id)

    def run_next(self, session_id: str) -> Step | None:
        """Execute a single pending pipeline step, if one exists."""
        current_step = self._get_next_step(session_id)
        if current_step is not None:
            self._execute_step(session_id, current_step)
        return current_step

    def run_until_blocked(
        self,
        session_id: str,
        on_progress: Callable[[Step, str], None] | None = None,
    ) -> None:
        """Execute all pending steps, reporting 'running' and 'done' events."""
        for _ in range(len(Step)):
            current_step = self._get_next_step(session_id)
            if current_step is None:
                return
            if on_progress is not None:
                on_progress(current_step, "running")
            self._execute_step(session_id, current_step)
            if on_progress is not None:
                on_progress(current_step, "done")

        if self._get_next_step(session_id) is not None:
            raise OrchestratorError("Pipeline exceeded the maximum number of steps")

    def apply_doctor_command(self, command: DoctorCommand) -> None:
        """Save doctor edits or approve a SOAP note or medical card atomically."""
        with self.db.transaction() as conn:
            if command.target == "soap":
                session = self.sessions_repo.get(conn, command.id)
                document = self.soap_repo.get(conn, command.id)
                if document["status"] != "draft":
                    raise InvalidTransitionError(
                        "Підтверджені дані змінювати не можна"
                    )

                if command.edits:
                    result = apply_soap_edits(document["final"], command.edits)
                    self.soap_repo.save_edits(
                        conn, command.id, result.model_dump(mode="json")
                    )

                if command.action == "approve":
                    if session["status"] != "drafted":
                        raise InvalidTransitionError(
                            "Сесія ще не готова до підтвердження"
                        )
                    self.soap_repo.set_review_started(
                        conn, command.id, command.review_started_at.isoformat()
                    )
                    self.soap_repo.approve(conn, command.id, command.at.isoformat())
                    self._maybe_approve_session(conn, command.id)

            elif command.target == "card":
                document = self.cards_repo.get(conn, command.id)
                if document["status"] != "draft":
                    raise InvalidTransitionError(
                        "Підтверджені дані змінювати не можна"
                    )

                if command.edits:
                    result = apply_card_edits(document["data"], command.edits)
                    self.cards_repo.save_edits(
                        conn, command.id, result.model_dump(mode="json")
                    )

                if command.action == "approve":
                    session_id = document["source_session_id"]
                    session = self.sessions_repo.get(conn, session_id)
                    if session["status"] != "drafted":
                        raise InvalidTransitionError(
                            "Сесія ще не готова до підтвердження"
                        )
                    self.cards_repo.set_review_started(
                        conn, command.id, command.review_started_at.isoformat()
                    )
                    self.cards_repo.approve(conn, command.id, command.at.isoformat())
                    self._maybe_approve_session(conn, session_id)

            else:
                raise UserInputError("Unknown doctor command target")

    def _maybe_approve_session(self, conn: Any, session_id: str) -> None:
        """Approve a session once all its required documents are approved."""
        session = self.sessions_repo.get(conn, session_id)
        if session["status"] != "drafted":
            raise InvalidTransitionError("Сесія ще не готова до підтвердження")

        note = self.soap_repo.find(conn, session_id)
        if note is None or note["status"] != "approved":
            return

        if session["session_number"] == 1:
            card = self.cards_repo.find(conn, session["patient_id"])
            if card is None or card["status"] != "approved":
                return
            if card["source_session_id"] != session_id:
                raise InvalidTransitionError(
                    "Медкартка належить іншій сесії"
                )

        self.sessions_repo.set_status(conn, session_id, "approved")

    def delete_session(self, session_id: str) -> None:
        """Delete a session, then remove its audio after database commit."""
        with self.db.transaction() as conn:
            session = self.sessions_repo.get(conn, session_id)
            patient_id = session["patient_id"]
            if session["session_number"] == 1:
                sessions = self.sessions_repo.list_by_patient(conn, patient_id)
                if len(sessions) > 1:
                    raise UserInputError(
                        "Не можна видалити першу сесію, поки існують інші"
                    )
            self.sessions_repo.delete(conn, session_id)

        delete_session_dir(self.data_dir, patient_id, session_id)

    def delete_patient(self, patient_id: str) -> None:
        """Delete a patient and all records, then remove stored audio."""
        with self.db.transaction() as conn:
            self.patients_repo.delete(conn, patient_id)

        delete_patient_dir(self.data_dir, patient_id)

    def get_dynamics(self, patient_id: str) -> S5Out | None:
        """Calculate S5 results for at least two approved patient sessions."""
        with self.db.read() as conn:
            self.patients_repo.get(conn, patient_id)
            visits = self.biomarkers_repo.list_approved_for_patient(
                conn, patient_id
            )

        if len(visits) < 2:
            return None
        result = self.systems["s5"].calculate(build_s5_in(visits))
        return S5Out.model_validate(result)
