"""S3 · Заповнення медкартки (Optional, лише сесія №1) (контракти, розділ 4 і 6)."""
from typing import Annotated

from pydantic import Field, StrictBool, StrictStr, field_validator, model_validator

from .catalog import CARD_DATA_FIELDS, DOCTOR_CARD_FIELDS, MODEL_FIELDS, FieldType
from .common import (
    ContractModel, FieldStatus, ModelFieldStatus, NonEmptyStr, RiskLevel, Seconds, SegmentId, Speaker,
    TextSegment, check_text_segments, ensure_unique_ascending,
)


# ───────────── S3.in ─────────────
class S3In(ContractModel):
    segments: Annotated[list[TextSegment], Field(min_length=1)]

    @field_validator("segments")
    @classmethod
    def _ids(cls, v):
        return check_text_segments(v)


# ───────────── S3.out ─────────────
class S3Field(ContractModel):
    field_id: str
    status: ModelFieldStatus
    value: StrictStr | StrictBool | None = None  # str для text, bool для bool; null при not_discussed / contradictory
    contradiction_text: str | None = None  # лише при contradictory: «Спочатку пацієнт сказав: … Потім: …»
    attention: bool = False  # true лише для safety.*
    evidence: list[SegmentId] = Field(default_factory=list)  # segment_id у хронологічному порядку

    @field_validator("field_id")
    @classmethod
    def _known(cls, v: str):
        if v not in MODEL_FIELDS:
            raise ValueError(f"{v!r} — не поле filled_by=M з каталогу")
        return v

    @model_validator(mode="after")
    def _by_status(self):
        ensure_unique_ascending(self.evidence, "evidence")
        if self.attention and not self.field_id.startswith("safety."):
            raise ValueError("attention=true дозволено лише для safety.*")

        if self.status == ModelFieldStatus.FILLED:
            _check_value_type(self.field_id, self.value, required=True)
            if self.contradiction_text is not None:
                raise ValueError("contradiction_text лише при contradictory")
            if not self.evidence:
                raise ValueError("filled без evidence")
        elif self.status == ModelFieldStatus.NOT_DISCUSSED:
            if self.value is not None or self.contradiction_text is not None or self.evidence:
                raise ValueError("not_discussed: value, contradiction_text і evidence мають бути порожні")
        else:  # contradictory
            if self.value is not None:
                raise ValueError("contradictory: value має бути null")
            if not self.contradiction_text or not self.contradiction_text.strip():
                raise ValueError("contradictory: потрібен contradiction_text")
            if len(self.evidence) < 2:
                raise ValueError("contradictory: потрібні щонайменше дві репліки-джерела")
        return self


def _check_value_type(field_id: str, value, *, required: bool) -> None:
    ftype = CARD_DATA_FIELDS[field_id]
    if value is None:
        if required:
            raise ValueError("value не може бути null")
        return
    if ftype == FieldType.BOOL:
        if not isinstance(value, bool):
            raise ValueError(f"{field_id}: очікується bool")
    elif ftype == FieldType.ENUM:
        if value not in {r.value for r in RiskLevel}:
            raise ValueError(f"{field_id}: очікується {', '.join(r.value for r in RiskLevel)}")
    else:  # text
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_id}: очікується непорожній рядок")


class S3Out(ContractModel):
    """Також зберігається в medical_cards.draft (сирий вихід, потім — відновлений)."""

    fields: list[S3Field]

    @model_validator(mode="after")
    def _all_model_fields(self):
        ids = [f.field_id for f in self.fields]
        if len(set(ids)) != len(ids):
            raise ValueError("field_id дублюються")
        missing = set(MODEL_FIELDS) - set(ids)
        if missing:
            raise ValueError(f"відсутні поля M: {sorted(missing)}")
        return self

    def check_against_input(self, inp: S3In) -> None:
        """evidence має посилатись на репліки зі вхідного транскрипту."""
        known = {s.segment_id for s in inp.segments}
        for f in self.fields:
            bad = [i for i in f.evidence if i not in known]
            if bad:
                raise ValueError(f"{f.field_id}: evidence посилається на відсутні segment_id {bad}")


# ───────────── medical_cards.data ─────────────
class EvidenceRef(ContractModel):
    """Джерело, яке Оркестратор додає з transcript_segments (правило 8). Форма — припущення."""

    segment_id: SegmentId
    speaker: Speaker
    start_time: Seconds
    quote: NonEmptyStr


class CardField(ContractModel):
    """Поле робочої картки: формат S3.out + поля лікаря + прапорець правки."""

    field_id: str
    status: FieldStatus
    value: StrictStr | StrictBool | None = None
    contradiction_text: str | None = None
    attention: bool = False
    evidence: list[SegmentId] = Field(default_factory=list)
    sources: list[EvidenceRef] = Field(default_factory=list)
    edited_by_doctor: bool = False

    @model_validator(mode="after")
    def _check(self):
        if self.field_id not in CARD_DATA_FIELDS:
            raise ValueError(f"{self.field_id!r} не зберігається в medical_cards.data")
        if self.field_id in DOCTOR_CARD_FIELDS and self.status != FieldStatus.DOCTOR_INPUT:
            raise ValueError("поля лікаря мають статус doctor_input")
        if self.attention and not self.field_id.startswith("safety."):
            raise ValueError("attention=true дозволено лише для safety.*")
        if self.value is not None:
            _check_value_type(self.field_id, self.value, required=True)
        if self.status == FieldStatus.FILLED and self.value is None:
            raise ValueError("filled без value")
        if not self.edited_by_doctor and self.status in (FieldStatus.NOT_DISCUSSED, FieldStatus.CONTRADICTORY):
            if self.value is not None:
                raise ValueError(f"{self.status.value}: value має бути null")
        return self


class MedicalCardData(ContractModel):
    """medical_cards.data. Порожня картка (S3 вимкнено): fields = []."""

    fields: list[CardField] = Field(default_factory=list)

    @field_validator("fields")
    @classmethod
    def _unique(cls, f: list[CardField]):
        ids = [x.field_id for x in f]
        if len(set(ids)) != len(ids):
            raise ValueError("field_id дублюються")
        return f
