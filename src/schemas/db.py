"""Моделі рядків SQLite (DB architecture v2.1, розділ 3).

JSON-колонки (transcript_meta, ner_map, data, draft, final, channel_map) приймають і рядок із БД,
і готовий об'єкт; `to_db()` повертає словник, готовий до INSERT (JSON → рядки, bool → 0/1).
"""
import json
from datetime import date
from typing import Annotated, Any, ClassVar, Mapping

from pydantic import AwareDatetime, BeforeValidator, Field, model_validator

from .common import (
    ArtifactStatus, ContractModel, Language, NonEmptyStr, PatientId, SegmentId, SessionNumber, SessionStatus,
    Speaker, UuidStr, Seconds, Confidence, parse_json_if_str, status_reached,
)
from .s1_transcription import ChannelMap, S1Metadata
from .s2_biomarkers import S2Out
from .s3_medcard import MedicalCardData, S3Out
from .s4_soap import SoapNote, SoapNoteFinal
from .s6_ner import NerMap

_J = BeforeValidator(parse_json_if_str)


class DbRow(ContractModel):
    JSON_COLUMNS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def from_row(cls, row: Mapping[str, Any]):
        """sqlite3.Row / dict → модель (з валідацією)."""
        return cls.model_validate(dict(row))

    def to_db(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        for col in self.JSON_COLUMNS:
            if data.get(col) is not None:
                data[col] = json.dumps(data[col], ensure_ascii=False)
        return {k: int(v) if isinstance(v, bool) else v for k, v in data.items()}


# ───────────── patients ─────────────
class PatientContacts(ContractModel):
    """Контакти (PII): заповнює лікар, у NER/API не йдуть. Усі поля можна заповнити пізніше."""

    preferred_name: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    preferred_channel: str | None = None
    emergency_name: str | None = None
    emergency_relation: str | None = None
    emergency_phone: str | None = None
    emergency_consent: bool | None = None


class PatientRow(PatientContacts, DbRow):
    patient_id: PatientId
    created_at: AwareDatetime


# ───────────── sessions ─────────────
class SessionRow(DbRow):
    JSON_COLUMNS = ("channel_map", "transcript_meta", "ner_map")

    session_id: UuidStr
    patient_id: PatientId
    session_number: SessionNumber
    session_date: date
    audio_path: NonEmptyStr
    patient_audio_path: str | None = None
    channel_map: Annotated[ChannelMap, _J] = Field(default_factory=ChannelMap)
    language: Language | None = None
    transcript_meta: Annotated[S1Metadata, _J] | None = None
    ner_map: Annotated[NerMap, _J] | None = None
    status: SessionStatus = SessionStatus.UPLOADED
    failed_step: str | None = None
    error: str | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _invariants(self):
        if (self.failed_step is None) != (self.error is None):
            raise ValueError("failed_step і error заповнюються й очищаються разом")
        if status_reached(self.status, SessionStatus.TRANSCRIBED):
            if self.language is None or self.transcript_meta is None or not self.patient_audio_path:
                raise ValueError("після S1 мають бути language, transcript_meta, patient_audio_path")
        if status_reached(self.status, SessionStatus.SANITIZED) and self.ner_map is None:
            raise ValueError("після sanitize має бути ner_map (можна порожній {})")
        return self


# ───────────── transcript_segments ─────────────
class TranscriptSegmentRow(DbRow):
    session_id: UuidStr
    segment_id: SegmentId
    speaker: Speaker
    start_time: Seconds
    end_time: Seconds
    text_raw: NonEmptyStr  # з PII, лише локально
    text_sanitized: str | None = None  # єдиний текст, що йде в API
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def _times(self):
        if self.end_time < self.start_time:
            raise ValueError("end_time менший за start_time")
        return self


# ───────────── biomarkers ─────────────
class BiomarkersRow(DbRow):
    JSON_COLUMNS = ("data",)

    session_id: UuidStr
    data: Annotated[S2Out, _J]


# ───────────── medical_cards ─────────────
class MedicalCardRow(DbRow):
    JSON_COLUMNS = ("draft", "data")

    patient_id: PatientId
    source_session_id: UuidStr
    status: ArtifactStatus = ArtifactStatus.GENERATED
    draft: Annotated[S3Out, _J] | None = None  # NULL, якщо S3 вимкнено
    data: Annotated[MedicalCardData, _J] | None = None
    review_started_at: AwareDatetime | None = None
    approved_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _invariants(self):
        if self.status == ArtifactStatus.GENERATED and self.draft is None:
            raise ValueError("generated: draft (сирий вихід S3) обов'язковий")
        if self.status != ArtifactStatus.GENERATED and self.data is None:
            raise ValueError("draft/approved: data (робоча копія) обов'язкова")
        _check_approval(self.status, self.review_started_at, self.approved_at)
        return self


# ───────────── soap_notes ─────────────
class SoapNoteRow(DbRow):
    JSON_COLUMNS = ("draft", "final")

    session_id: UuidStr
    status: ArtifactStatus = ArtifactStatus.GENERATED
    draft: Annotated[SoapNote, _J] | None = None
    final: Annotated[SoapNoteFinal, _J] | None = None
    review_started_at: AwareDatetime | None = None
    approved_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _invariants(self):
        if self.draft is None:
            raise ValueError("draft (вихід S4) обов'язковий")
        if self.status == ArtifactStatus.GENERATED and self.final is not None:
            raise ValueError("generated: final ще не створюється (з'являється після restore)")
        if self.status != ArtifactStatus.GENERATED and self.final is None:
            raise ValueError("draft/approved: final (робоча копія) обов'язкова")
        _check_approval(self.status, self.review_started_at, self.approved_at)
        return self


def _check_approval(status: ArtifactStatus, started, approved) -> None:
    if status == ArtifactStatus.APPROVED:
        if approved is None or started is None:
            raise ValueError("approved: потрібні review_started_at і approved_at")
        if approved < started:
            raise ValueError("approved_at раніше за review_started_at")
    elif approved is not None:
        raise ValueError("approved_at заповнюється лише при approved")
