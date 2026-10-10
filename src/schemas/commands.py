"""Команда лікаря: UI → Оркестратор (контракти, розділ 5)."""
import re
from typing import Annotated, Any

from pydantic import AwareDatetime, Field, model_validator

from .catalog import CARD_DATA_FIELDS
from .common import (
    PATIENT_ID_RE, AssessmentBasis, CommandAction, CommandTarget, ContractModel, FieldStatus,
    NonEmptyStr, check_uuid,
)
from .s3_medcard import _check_value_type

# шляхи у структурі S4.out, які лікар може правити
_SOAP_TEXT_PATH = re.compile(r"^(?:(?:subjective|objective|assessment)\.text|plan\[\d+\]\.text)$")
_SOAP_BASIS_PATH = re.compile(r"^assessment\.basis$")
_SOAP_CONFIRMED_PATH = re.compile(r"^plan\[\d+\]\.confirmed$")


class Edit(ContractModel):
    path: NonEmptyStr  # field_id для картки; шлях у структурі S4.out для SOAP
    new_value: Any


class DoctorCommand(ContractModel):
    target: CommandTarget
    id: NonEmptyStr  # patient_id для картки, session_id (UUID) для SOAP
    action: CommandAction
    edits: list[Edit] = Field(default_factory=list)
    review_started_at: AwareDatetime
    at: AwareDatetime

    @model_validator(mode="after")
    def _check(self):
        if self.at < self.review_started_at:
            raise ValueError("at раніше за review_started_at")
        if self.action == CommandAction.EDIT and not self.edits:
            raise ValueError("action=edit без edits")

        if self.target == CommandTarget.SOAP:
            check_uuid(self.id)  # session_id — UUID
            for e in self.edits:
                self._check_soap_edit(e)
        else:
            if not PATIENT_ID_RE.match(self.id):
                raise ValueError("id картки має бути patient_id виду usr-anon-…")
            seen = set()
            for e in self.edits:
                if e.path not in CARD_DATA_FIELDS:
                    raise ValueError(f"{e.path!r}: поле не зберігається в medical_cards.data")
                if e.path in seen:
                    raise ValueError(f"{e.path!r} правиться двічі")
                seen.add(e.path)
                _check_value_type(e.path, e.new_value, required=False)
        return self

    @staticmethod
    def _check_soap_edit(e: Edit) -> None:
        if _SOAP_TEXT_PATH.match(e.path):
            if not isinstance(e.new_value, str) or not e.new_value.strip():
                raise ValueError(f"{e.path}: очікується непорожній рядок")
        elif _SOAP_CONFIRMED_PATH.match(e.path):
            if not isinstance(e.new_value, bool):
                raise ValueError(f"{e.path}: очікується bool")
        elif _SOAP_BASIS_PATH.match(e.path):
            if e.new_value not in {b.value for b in AssessmentBasis}:
                raise ValueError(f"{e.path}: очікується doctor_stated | model_synthesis")
        else:
            raise ValueError(f"недопустимий шлях правки SOAP: {e.path!r}")
