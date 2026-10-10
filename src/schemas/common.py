"""Спільні типи, enum-и та допоміжні валідатори для всіх контрактів ClarityScribe.

Джерело істини — ClarityScribe_contracts (v2.0, Orchestrator), розділи 4, 7.
Потрібен Python 3.10+ і pydantic >= 2.6.
"""
import json
import re
from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


class ContractModel(BaseModel):
    """База для всіх контрактів: зайві поля заборонені (контракти мінімальні, правило 4)."""

    model_config = ConfigDict(extra="forbid")


# ───────────────────────────── Enum-и (розділ 7) ─────────────────────────────
class Speaker(str, Enum):
    DOCTOR = "DOCTOR"
    PATIENT = "PATIENT"


class Language(str, Enum):
    UK = "uk"
    EN = "en"


class FieldStatus(str, Enum):
    """Статус поля картки в medical_cards.data."""

    FILLED = "filled"
    NOT_DISCUSSED = "not_discussed"
    CONTRADICTORY = "contradictory"
    DOCTOR_INPUT = "doctor_input"


class ModelFieldStatus(str, Enum):
    """Статуси, які може повернути S3 (без doctor_input)."""

    FILLED = "filled"
    NOT_DISCUSSED = "not_discussed"
    CONTRADICTORY = "contradictory"


class AssessmentBasis(str, Enum):
    DOCTOR_STATED = "doctor_stated"
    MODEL_SYNTHESIS = "model_synthesis"


class PlanOrigin(str, Enum):
    DOCTOR_STATED = "doctor_stated"
    RECOMMENDED = "recommended"


class EntityType(str, Enum):
    PERSON = "PERSON"
    ADDRESS = "ADDRESS"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    ORG = "ORG"
    BIRTH_DATE = "BIRTH_DATE"
    OTHER_ID = "OTHER_ID"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class SessionStatus(str, Enum):
    """sessions.status — останній ВИКОНАНИЙ етап (DB architecture, розділ 5.1)."""

    UPLOADED = "uploaded"
    TRANSCRIBED = "transcribed"
    SANITIZED = "sanitized"
    ANALYZED = "analyzed"
    DRAFTED = "drafted"
    APPROVED = "approved"


SESSION_STATUS_ORDER = list(SessionStatus)


def status_reached(current: SessionStatus, target: SessionStatus) -> bool:
    """True, якщо сесія вже досягла етапу target (current >= target)."""
    return SESSION_STATUS_ORDER.index(current) >= SESSION_STATUS_ORDER.index(target)


class ArtifactStatus(str, Enum):
    """medical_cards.status і soap_notes.status."""

    GENERATED = "generated"
    DRAFT = "draft"
    APPROVED = "approved"


class CommandTarget(str, Enum):
    CARD = "card"
    SOAP = "soap"


class CommandAction(str, Enum):
    EDIT = "edit"
    APPROVE = "approve"


# ───────────────────────────── Прості типи ─────────────────────────────
Seconds = Annotated[float, Field(ge=0)]  # правило 5: секунди від початку запису
SegmentId = Annotated[int, Field(ge=0)]
SessionNumber = Annotated[int, Field(ge=1)]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
Confidence = Annotated[float, Field(ge=0, le=1)]


def check_uuid(v: str) -> str:
    UUID(v)
    return v


UuidStr = Annotated[str, AfterValidator(check_uuid)]

PATIENT_ID_RE = re.compile(r"^usr-anon-[A-Za-z0-9]+$")
PatientId = Annotated[str, StringConstraints(pattern=PATIENT_ID_RE.pattern)]


def relative_media_path(*suffixes: str) -> AfterValidator:
    """Шлях відносно теки застосунку: без абсолютних шляхів і '..', з дозволеними розширеннями."""

    def _check(v: str) -> str:
        if not v.strip():
            raise ValueError("шлях порожній")
        p = PurePosixPath(v.replace("\\", "/"))
        if p.is_absolute() or re.match(r"^[A-Za-z]:", v):
            raise ValueError("шлях має бути відносним")
        if ".." in p.parts:
            raise ValueError("шлях не може містити '..'")
        if suffixes and p.suffix.lower() not in suffixes:
            raise ValueError(f"очікується розширення {', '.join(suffixes)}")
        return v

    return AfterValidator(_check)


def ensure_unique_ascending(ids: list[int], what: str) -> None:
    if any(b <= a for a, b in zip(ids, ids[1:])):
        raise ValueError(f"{what} мають бути унікальними й зростати")


def parse_json_if_str(v: Any) -> Any:
    """BeforeValidator для JSON-колонок SQLite: рядок → Python-об'єкт."""
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v


class TextSegment(ContractModel):
    """Санітизована репліка для S3.in / S4.in."""

    segment_id: SegmentId
    speaker: Speaker
    text: NonEmptyStr


def check_text_segments(segments: list[TextSegment]) -> list[TextSegment]:
    ensure_unique_ascending([s.segment_id for s in segments], "segment_id")
    return segments
