import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, ValidationError

from src.schemas.contracts import MedicalCardData, S1Segment, S3Out
from src.schemas.db_json import dump_column, load_column

from .exceptions import RecordNotFoundError, RepositoryError, UserInputError


_PATIENT_CONTACT_FIELDS = (
    "preferred_name",
    "birth_date",
    "phone",
    "email",
    "preferred_channel",
    "emergency_name",
    "emergency_relation",
    "emergency_phone",
    "emergency_consent",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else dict(row)


def _require_row(row: sqlite3.Row | None, entity: str, record_id: str) -> dict[str, Any]:
    result = _row_dict(row)
    if result is None:
        raise RecordNotFoundError(f"{entity} '{record_id}' was not found.")
    return result


def _dump_json(table: str, column: str, value: Any) -> str:
    try:
        return dump_column(table, column, value)
    except (TypeError, ValueError, ValidationError) as error:
        raise RepositoryError(f"Invalid JSON payload for {table}.{column}.") from error


def _load_json(table: str, column: str, value: str | None) -> Any:
    try:
        return load_column(table, column, value)
    except (TypeError, ValueError, ValidationError) as error:
        raise RepositoryError(f"Invalid JSON stored in {table}.{column}.") from error


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _decode_session(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["channel_map"] = _plain(
        _load_json("sessions", "channel_map", result["channel_map"])
    )
    result["transcript_meta"] = _plain(
        _load_json("sessions", "transcript_meta", result["transcript_meta"])
    )
    result["ner_map"] = _plain(_load_json("sessions", "ner_map", result["ner_map"]))
    return result


class PatientsRepo:
    def create(self, conn: sqlite3.Connection, contacts: dict[str, Any]) -> str:
        if not isinstance(contacts, dict):
            raise UserInputError("Patient contacts must be a dictionary.")
        unknown = set(contacts) - set(_PATIENT_CONTACT_FIELDS)
        if unknown:
            raise UserInputError(f"Unknown patient contact fields: {sorted(unknown)}")

        patient_id = f"usr-anon-{secrets.token_hex(4)}"
        values = {field: contacts.get(field) for field in _PATIENT_CONTACT_FIELDS}
        if values["emergency_consent"] is not None:
            consent = values["emergency_consent"]
            if not isinstance(consent, (bool, int)) or consent not in (0, 1):
                raise UserInputError("emergency_consent must be a boolean, 0, or 1.")
            values["emergency_consent"] = int(consent)

        try:
            conn.execute(
                """
                INSERT INTO patients (
                    patient_id, preferred_name, birth_date, phone, email,
                    preferred_channel, emergency_name, emergency_relation,
                    emergency_phone, emergency_consent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (patient_id, *(values[field] for field in _PATIENT_CONTACT_FIELDS), _now()),
            )
        except sqlite3.Error as error:
            raise RepositoryError("Failed to create patient.") from error
        return patient_id

    def get(self, conn: sqlite3.Connection, patient_id: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        return _require_row(row, "Patient", patient_id)

    def update_contacts(
        self, conn: sqlite3.Connection, patient_id: str, contacts: dict[str, Any]
    ) -> None:
        if not isinstance(contacts, dict):
            raise UserInputError("Patient contacts must be a dictionary.")
        unknown = set(contacts) - set(_PATIENT_CONTACT_FIELDS)
        if unknown:
            raise UserInputError(f"Unknown patient contact fields: {sorted(unknown)}")
        if not contacts:
            return

        values = dict(contacts)
        if "emergency_consent" in values and values["emergency_consent"] is not None:
            consent = values["emergency_consent"]
            if not isinstance(consent, (bool, int)) or consent not in (0, 1):
                raise UserInputError("emergency_consent must be a boolean, 0, or 1.")
            values["emergency_consent"] = int(consent)
        assignments = ", ".join(f"{field} = ?" for field in values)
        try:
            cursor = conn.execute(
                f"UPDATE patients SET {assignments} WHERE patient_id = ?",
                (*values.values(), patient_id),
            )
        except sqlite3.Error as error:
            raise RepositoryError("Failed to update patient contacts.") from error
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Patient '{patient_id}' was not found.")

    def delete(self, conn: sqlite3.Connection, patient_id: str) -> None:
        patient = self.get(conn, patient_id)
        sessions = conn.execute(
            "SELECT session_id FROM sessions WHERE patient_id = ?", (patient["patient_id"],)
        ).fetchall()
        session_ids = [row["session_id"] for row in sessions]

        for session_id in session_ids:
            SoapNotesRepo().delete(conn, session_id)
            BiomarkersRepo().delete(conn, session_id)
            TranscriptRepo().delete(conn, session_id)
        conn.execute("DELETE FROM medical_cards WHERE patient_id = ?", (patient_id,))
        conn.execute("DELETE FROM sessions WHERE patient_id = ?", (patient_id,))
        conn.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))

    def list_with_sessions(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        patients = conn.execute("SELECT * FROM patients ORDER BY created_at").fetchall()
        result = []
        for patient in patients:
            sessions = conn.execute(
                """
                SELECT status, failed_step, session_date
                FROM sessions
                WHERE patient_id = ?
                ORDER BY session_number
                """,
                (patient["patient_id"],),
            ).fetchall()
            item = dict(patient)
            item["sessions_count"] = len(sessions)
            item["last_session_date"] = max(
                (row["session_date"] for row in sessions), default=None
            )
            item["sessions"] = [
                {"status": row["status"], "failed_step": row["failed_step"]}
                for row in sessions
            ]
            result.append(item)
        return result


class SessionsRepo:
    def create(
        self,
        conn: sqlite3.Connection,
        patient_id: str,
        number: int,
        date: str,
        audio_path: str,
        channel_map: dict[str, int],
        language: str,
    ) -> str:
        session_id = str(uuid.uuid4())
        try:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, patient_id, session_number, session_date,
                    audio_path, channel_map, language, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    patient_id,
                    number,
                    date,
                    audio_path,
                    _dump_json("sessions", "channel_map", channel_map),
                    language,
                    _now(),
                ),
            )
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error).upper():
                raise UserInputError("A session with this number already exists.") from error
            raise RepositoryError("Failed to create session.") from error
        except (sqlite3.Error, RepositoryError) as error:
            raise RepositoryError("Failed to create session.") from error
        return session_id

    def get(self, conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        _require_row(row, "Session", session_id)
        return _decode_session(row)

    def get_by_number(
        self, conn: sqlite3.Connection, patient_id: str, number: int
    ) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT * FROM sessions
            WHERE patient_id = ? AND session_number = ?
            """,
            (patient_id, number),
        ).fetchone()
        _require_row(row, "Session", f"{patient_id}/{number}")
        return _decode_session(row)

    def list_by_patient(
        self, conn: sqlite3.Connection, patient_id: str
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE patient_id = ?
            ORDER BY session_number DESC
            """,
            (patient_id,),
        ).fetchall()
        return [_decode_session(row) for row in rows]

    def max_number(self, conn: sqlite3.Connection, patient_id: str) -> int | None:
        row = conn.execute(
            "SELECT MAX(session_number) AS max_number FROM sessions WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
        return row["max_number"]

    def list_approved_before(
        self, conn: sqlite3.Connection, patient_id: str, number: int, limit: int = 3
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE patient_id = ? AND session_number < ? AND status = 'approved'
            ORDER BY session_number DESC
            LIMIT ?
            """,
            (patient_id, number, limit),
        ).fetchall()
        return [_decode_session(row) for row in rows]

    def set_status(self, conn: sqlite3.Connection, session_id: str, status: str) -> None:
        try:
            cursor = conn.execute(
                "UPDATE sessions SET status = ?, failed_step = NULL, error = NULL WHERE session_id = ?",
                (status, session_id),
            )
        except sqlite3.Error as error:
            raise RepositoryError("Failed to update session status.") from error
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Session '{session_id}' was not found.")

    def set_failure(
        self, conn: sqlite3.Connection, session_id: str, step: str, error: str
    ) -> None:
        cursor = conn.execute(
            "UPDATE sessions SET failed_step = ?, error = ? WHERE session_id = ?",
            (step, error, session_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Session '{session_id}' was not found.")

    def clear_failure(self, conn: sqlite3.Connection, session_id: str) -> None:
        cursor = conn.execute(
            "UPDATE sessions SET failed_step = NULL, error = NULL WHERE session_id = ?",
            (session_id,),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Session '{session_id}' was not found.")

    def save_s1_result(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        language: str,
        transcript_meta: dict[str, Any],
        patient_audio_path: str | None,
    ) -> None:
        meta = _dump_json("sessions", "transcript_meta", transcript_meta)
        cursor = conn.execute(
            """
            UPDATE sessions
            SET language = ?, transcript_meta = ?, patient_audio_path = ?
            WHERE session_id = ?
            """,
            (language, meta, patient_audio_path, session_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Session '{session_id}' was not found.")

    def save_ner_map(
        self, conn: sqlite3.Connection, session_id: str, ner_map: dict[str, Any]
    ) -> None:
        value = _dump_json("sessions", "ner_map", ner_map)
        cursor = conn.execute(
            "UPDATE sessions SET ner_map = ? WHERE session_id = ?",
            (value, session_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Session '{session_id}' was not found.")

    def reset_pipeline(self, conn: sqlite3.Connection, session_id: str) -> None:
        session = self.get(conn, session_id)
        SoapNotesRepo().delete(conn, session_id)
        BiomarkersRepo().delete(conn, session_id)
        TranscriptRepo().delete(conn, session_id)
        conn.execute(
            """
            DELETE FROM medical_cards
            WHERE source_session_id = ? AND status != 'approved'
            """,
            (session_id,),
        )
        conn.execute(
            """
            UPDATE sessions
            SET patient_audio_path = NULL, transcript_meta = NULL, ner_map = NULL,
                failed_step = NULL, error = NULL, status = 'uploaded'
            WHERE session_id = ?
            """,
            (session["session_id"],),
        )

    def update_audio_path(
        self, conn: sqlite3.Connection, session_id: str, path: str
    ) -> None:
        cursor = conn.execute(
            "UPDATE sessions SET audio_path = ? WHERE session_id = ?",
            (path, session_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Session '{session_id}' was not found.")

    def delete(self, conn: sqlite3.Connection, session_id: str) -> None:
        self.get(conn, session_id)
        SoapNotesRepo().delete(conn, session_id)
        BiomarkersRepo().delete(conn, session_id)
        TranscriptRepo().delete(conn, session_id)
        conn.execute("DELETE FROM medical_cards WHERE source_session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


class TranscriptRepo:
    def replace_segments(
        self, conn: sqlite3.Connection, session_id: str, segments: Iterable[dict[str, Any]]
    ) -> None:
        validated = [S1Segment.model_validate(segment) for segment in segments]
        conn.execute("DELETE FROM transcript_segments WHERE session_id = ?", (session_id,))
        try:
            conn.executemany(
                """
                INSERT INTO transcript_segments (
                    session_id, segment_id, speaker, start_time, end_time,
                    text_raw, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        segment.segment_id,
                        segment.speaker,
                        segment.start_time,
                        segment.end_time,
                        segment.text,
                        segment.confidence,
                    )
                    for segment in validated
                ],
            )
        except sqlite3.Error as error:
            raise RepositoryError("Failed to replace transcript segments.") from error

    def get_segments(self, conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT segment_id, speaker, start_time, end_time, text_raw,
                   text_sanitized, confidence
            FROM transcript_segments
            WHERE session_id = ?
            ORDER BY segment_id
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def set_sanitized(
        self, conn: sqlite3.Connection, session_id: str, sanitized: dict[int, str]
    ) -> None:
        try:
            cursor = conn.executemany(
                """
                UPDATE transcript_segments
                SET text_sanitized = ?
                WHERE session_id = ? AND segment_id = ?
                """,
                [(text, session_id, segment_id) for segment_id, text in sanitized.items()],
            )
        except sqlite3.Error as error:
            raise RepositoryError("Failed to save sanitized transcript.") from error
        if cursor.rowcount != len(sanitized):
            raise RecordNotFoundError(
                f"One or more transcript segments for session '{session_id}' were not found."
            )

    def delete(self, conn: sqlite3.Connection, session_id: str) -> None:
        conn.execute("DELETE FROM transcript_segments WHERE session_id = ?", (session_id,))


class BiomarkersRepo:
    def upsert(self, conn: sqlite3.Connection, session_id: str, data: dict[str, Any]) -> None:
        value = _dump_json("biomarkers", "data", data)
        try:
            conn.execute(
                """
                INSERT INTO biomarkers (session_id, data) VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET data = excluded.data
                """,
                (session_id, value),
            )
        except sqlite3.Error as error:
            raise RepositoryError("Failed to save biomarkers.") from error

    def get(self, conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT data FROM biomarkers WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Biomarkers for session '{session_id}' were not found.")
        return _plain(_load_json("biomarkers", "data", row["data"]))

    def list_approved_for_patient(
        self, conn: sqlite3.Connection, patient_id: str
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT s.session_number, b.data
            FROM sessions AS s
            JOIN biomarkers AS b ON b.session_id = s.session_id
            WHERE s.patient_id = ? AND s.status = 'approved'
            ORDER BY s.session_number
            """,
            (patient_id,),
        ).fetchall()
        return [
            {
                "session_number": row["session_number"],
                "data": _plain(_load_json("biomarkers", "data", row["data"])),
            }
            for row in rows
        ]

    def delete(self, conn: sqlite3.Connection, session_id: str) -> None:
        conn.execute("DELETE FROM biomarkers WHERE session_id = ?", (session_id,))


class MedicalCardsRepo:
    def get(self, conn: sqlite3.Connection, patient_id: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM medical_cards WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        result = _require_row(row, "Medical card", patient_id)
        result["draft"] = _plain(_load_json("medical_cards", "draft", result["draft"]))
        result["data"] = _plain(_load_json("medical_cards", "data", result["data"]))
        return result

    def save_generated(
        self,
        conn: sqlite3.Connection,
        patient_id: str,
        source_session_id: str,
        raw: dict[str, Any],
    ) -> None:
        value = _dump_json("medical_cards", "draft", raw)
        conn.execute(
            """
            INSERT INTO medical_cards (patient_id, source_session_id, status, draft, data)
            VALUES (?, ?, 'generated', ?, NULL)
            ON CONFLICT(patient_id) DO UPDATE SET
                source_session_id = excluded.source_session_id,
                status = 'generated',
                draft = excluded.draft,
                data = NULL,
                review_started_at = NULL,
                approved_at = NULL
            """,
            (patient_id, source_session_id, value),
        )

    def save_restored(
        self, conn: sqlite3.Connection, patient_id: str, restored: dict[str, Any]
    ) -> None:
        restored_model = S3Out.model_validate(restored)
        draft = _dump_json("medical_cards", "draft", restored_model)
        data = _dump_json(
            "medical_cards",
            "data",
            MedicalCardData(
                fields=[
                    {
                        "field_id": field.field_id,
                        "status": field.status,
                        "value": field.value,
                        "edited_by_doctor": False,
                    }
                    for field in restored_model.fields
                ]
            ),
        )
        cursor = conn.execute(
            """
            UPDATE medical_cards
            SET draft = ?, data = ?, status = 'draft'
            WHERE patient_id = ?
            """,
            (draft, data, patient_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Medical card for patient '{patient_id}' was not found.")

    def save_edits(
        self, conn: sqlite3.Connection, patient_id: str, data: dict[str, Any]
    ) -> None:
        value = _dump_json("medical_cards", "data", data)
        cursor = conn.execute(
            "UPDATE medical_cards SET data = ?, status = 'draft' WHERE patient_id = ?",
            (value, patient_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Medical card for patient '{patient_id}' was not found.")

    def set_review_started(
        self, conn: sqlite3.Connection, patient_id: str, at: str
    ) -> None:
        cursor = conn.execute(
            """
            UPDATE medical_cards
            SET review_started_at = COALESCE(review_started_at, ?)
            WHERE patient_id = ?
            """,
            (at, patient_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Medical card for patient '{patient_id}' was not found.")

    def approve(self, conn: sqlite3.Connection, patient_id: str, at: str) -> None:
        cursor = conn.execute(
            """
            UPDATE medical_cards
            SET status = 'approved', approved_at = ?
            WHERE patient_id = ? AND status = 'draft'
            """,
            (at, patient_id),
        )
        if cursor.rowcount == 0:
            self.get(conn, patient_id)
            raise UserInputError("Medical card must be in draft status before approval.")

    def delete(self, conn: sqlite3.Connection, patient_id: str) -> None:
        conn.execute("DELETE FROM medical_cards WHERE patient_id = ?", (patient_id,))


class SoapNotesRepo:
    def get(self, conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM soap_notes WHERE session_id = ?", (session_id,)
        ).fetchone()
        result = _require_row(row, "SOAP note", session_id)
        result["draft"] = _plain(_load_json("soap_notes", "draft", result["draft"]))
        result["final"] = _plain(_load_json("soap_notes", "final", result["final"]))
        return result

    def save_generated(
        self, conn: sqlite3.Connection, session_id: str, raw: dict[str, Any]
    ) -> None:
        value = _dump_json("soap_notes", "draft", raw)
        conn.execute(
            """
            INSERT INTO soap_notes (session_id, status, draft, final)
            VALUES (?, 'generated', ?, NULL)
            ON CONFLICT(session_id) DO UPDATE SET
                status = 'generated',
                draft = excluded.draft,
                final = NULL,
                review_started_at = NULL,
                approved_at = NULL
            """,
            (session_id, value),
        )

    def save_restored(
        self, conn: sqlite3.Connection, session_id: str, restored: dict[str, Any]
    ) -> None:
        value = _dump_json("soap_notes", "final", restored)
        cursor = conn.execute(
            """
            UPDATE soap_notes
            SET draft = ?, final = ?, status = 'draft'
            WHERE session_id = ?
            """,
            (value, value, session_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"SOAP note for session '{session_id}' was not found.")

    def save_edits(
        self, conn: sqlite3.Connection, session_id: str, final: dict[str, Any]
    ) -> None:
        value = _dump_json("soap_notes", "final", final)
        cursor = conn.execute(
            "UPDATE soap_notes SET final = ?, status = 'draft' WHERE session_id = ?",
            (value, session_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"SOAP note for session '{session_id}' was not found.")

    def set_review_started(
        self, conn: sqlite3.Connection, session_id: str, at: str
    ) -> None:
        cursor = conn.execute(
            """
            UPDATE soap_notes
            SET review_started_at = COALESCE(review_started_at, ?)
            WHERE session_id = ?
            """,
            (at, session_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"SOAP note for session '{session_id}' was not found.")

    def approve(self, conn: sqlite3.Connection, session_id: str, at: str) -> None:
        cursor = conn.execute(
            """
            UPDATE soap_notes
            SET status = 'approved', approved_at = ?
            WHERE session_id = ? AND status = 'draft'
            """,
            (at, session_id),
        )
        if cursor.rowcount == 0:
            self.get(conn, session_id)
            raise UserInputError("SOAP note must be in draft status before approval.")

    def delete(self, conn: sqlite3.Connection, session_id: str) -> None:
        conn.execute("DELETE FROM soap_notes WHERE session_id = ?", (session_id,))