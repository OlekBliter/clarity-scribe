"""ClarityScribe · контракти (lite, для MVP). Потрібен pydantic >= 2.6.

Strict  — внутрішні системи: зайвий ключ = помилка.
Lenient — виходи LLM (S3, S4): зайві ключі ігноруються, щоб не витрачати токени на повтори.
Вхідні контракти (S1.in … S5.in) не валідуємо: їх формує сам Оркестратор.
"""
import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


Speaker = Literal["DOCTOR", "PATIENT"]
Language = Literal["uk", "en"]
Sec = Annotated[float, Field(ge=0)]


# ───────────── S1 · Транскрибація ─────────────
class S1Metadata(Strict):  # зберігається в sessions.transcript_meta
    audio_duration_sec: Sec
    doctor_speaking_time_sec: Sec
    patient_speaking_time_sec: Sec
    silence_time_sec: Sec


class S1Segment(Strict):
    segment_id: Annotated[int, Field(ge=0)]
    speaker: Speaker
    start_time: Sec
    end_time: Sec
    text: str = Field(min_length=1)
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None

    @model_validator(mode="after")
    def _times(self):
        if self.end_time < self.start_time:
            raise ValueError("end_time < start_time")
        return self


class S1Out(Strict):
    language: Language
    metadata: S1Metadata
    segments: list[S1Segment]

    @model_validator(mode="after")
    def _ids(self):
        if [s.segment_id for s in self.segments] != list(range(len(self.segments))):
            raise ValueError("segment_id мають іти підряд з 0")
        return self


# ───────────── S6 · NER ─────────────
EntityType = Literal["PERSON", "ADDRESS", "PHONE", "EMAIL", "ORG", "BIRTH_DATE", "OTHER_ID"]
PLACEHOLDER_RE = re.compile(r"\[[^\[\]_\s]+_\d+\]")  # [ПІБ_1], [АДРЕСА_2] …


class NerEntry(Strict):
    type: EntityType
    original: str = Field(min_length=1)


NerMap = dict[str, NerEntry]  # sessions.ner_map: {"[ПІБ_1]": {"type": "PERSON", "original": "…"}}


class NerItem(Strict):
    key: str
    text: str


class S6SanitizeOut(Strict):
    items: list[NerItem]
    map: NerMap

    @model_validator(mode="after")
    def _no_leaks(self):
        for it in self.items:
            for ph in PLACEHOLDER_RE.findall(it.text):
                if ph not in self.map:
                    raise ValueError(f"{it.key}: плейсхолдера {ph} немає в map")
            for ph, e in self.map.items():
                if e.original in it.text:  # головна перевірка приватності
                    raise ValueError(f"{it.key}: у тексті лишилась сутність {ph}")
        return self


class S6RestoreOut(Strict):
    items: list[NerItem]

    @model_validator(mode="after")
    def _restored(self):
        for it in self.items:
            if PLACEHOLDER_RE.search(it.text):
                raise ValueError(f"{it.key}: лишились нерозкриті плейсхолдери")
        return self


# ───────────── S2 · Біомаркери (зберігається цілком у biomarkers.data) ─────────────
class RawDspFeatures(Strict):
    f0_variability_sd: Annotated[float, Field(ge=0)]
    f0_mean_hz: Annotated[float, Field(gt=0)]
    jitter_percent: Annotated[float, Field(ge=0)]
    shimmer_percent: Annotated[float, Field(ge=0)]
    hnr_db: float
    speech_rate_syllables_per_sec: Annotated[float, Field(ge=0)]
    pause_ratio: Annotated[float, Field(ge=0, le=1)]
    mean_latent_response_time_sec: Annotated[float, Field(ge=0)] | None  # null, якщо немає жодної латентності


class IntrasessionDynamics(Strict):
    f0_variability_change_percent: float
    speech_rate_change_percent: float
    pause_ratio_change_percent: float
    trend_summary: str  # напр. "activation"; повний перелік значень ще не затверджено


class InferredIndices(Strict):
    affect_flatness_flag: bool
    vocal_jitter_percentile: Annotated[float, Field(ge=0, le=100)]
    psychomotor_retardation_index: float
    intrasession_dynamics: IntrasessionDynamics | None  # null для надто короткого запису


class WindowChunk(Strict):
    window_index: Annotated[int, Field(ge=0)]
    time_range: str = Field(pattern=r"^\d{2,}:[0-5]\d-\d{2,}:[0-5]\d$")  # «00:00-05:00»
    f0_variability_sd: Annotated[float, Field(ge=0)]
    speech_rate_syllables_per_sec: Annotated[float, Field(ge=0)]
    pause_ratio: Annotated[float, Field(ge=0, le=1)]


class S2Out(Strict):
    raw_dsp_features: RawDspFeatures
    inferred_indices: InferredIndices
    window_chunks: list[WindowChunk]


# ───────────── S3 · Медкартка (LLM) ─────────────
BOOL_FIELDS = {"history.on_medication", "safety.suicidal_past", "safety.suicidal_now"}
MODEL_FIELDS = (  # усі поля filled_by = M
    "request.complaint", "request.onset", "request.why_now",
    "history.similar_before", "history.prior_therapy", "history.helpful_or_not",
    "history.on_medication", "history.medications_list",
    "safety.suicidal_past", "safety.suicidal_now", "safety.details",
    "context.work_study", "context.relationships_family", "context.life_changes_year", "context.social_support",
    "substance.alcohol", "substance.cannabis", "substance.other",
    "resources.coping", "resources.strengths", "goals.change", "goals.success_criteria",
)


class S3Field(Lenient):
    field_id: Literal[MODEL_FIELDS]  # type: ignore[valid-type]
    status: Literal["filled", "not_discussed", "contradictory"]
    value: str | bool | None = None
    contradiction_text: str | None = None
    attention: bool = False
    evidence: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rules(self):
        if self.status == "filled":
            if self.value is None or not self.evidence:
                raise ValueError("filled потребує value і evidence")
            if isinstance(self.value, bool) != (self.field_id in BOOL_FIELDS):
                raise ValueError("тип value не відповідає типу поля (bool / text)")
        elif self.value is not None:
            raise ValueError(f"{self.status}: value має бути null")
        if self.status == "contradictory" and not self.contradiction_text:
            raise ValueError("contradictory потребує contradiction_text")
        return self


class S3Out(Lenient):
    fields: list[S3Field]

    @model_validator(mode="after")
    def _complete(self):
        ids = [f.field_id for f in self.fields]
        if len(set(ids)) != len(ids) or set(ids) != set(MODEL_FIELDS):
            raise ValueError("у відповіді мають бути рівно всі 22 поля M, без дублів")
        return self

    def check_evidence(self, known_segment_ids: set[int]) -> None:
        """Виклик Оркестратора: evidence має посилатись на реальні репліки."""
        for f in self.fields:
            if not set(f.evidence) <= known_segment_ids:
                raise ValueError(f"{f.field_id}: evidence посилається на відсутні репліки")


class CardField(Lenient):  # medical_cards.data: поля S3 + поля лікаря
    field_id: str
    status: Literal["filled", "not_discussed", "contradictory", "doctor_input"]
    value: str | bool | None = None
    edited_by_doctor: bool = False


class MedicalCardData(Lenient):
    fields: list[CardField] = Field(default_factory=list)  # [] — якщо S3 вимкнено


# ───────────── S4 · SOAP (LLM). Одна модель і для draft, і для final ─────────────
class _Text(Lenient):
    text: str = Field(min_length=1)


class Subjective(_Text):
    source_segments: list[int] = Field(default_factory=list)


class Objective(_Text):
    biomarker_refs: list[str] = Field(default_factory=list)


class Assessment(_Text):
    basis: Literal["doctor_stated", "model_synthesis"]


class PlanItem(_Text):
    origin: Literal["doctor_stated", "recommended"]
    confirmed: bool | None = None  # лише в final: лікар підтвердив recommended


class SoapNote(Lenient):
    subjective: Subjective
    objective: Objective
    assessment: Assessment
    plan: list[PlanItem] = Field(default_factory=list)


# ───────────── S5 · Динаміка (рахується на льоту, не зберігається) ─────────────
class S5Point(Strict):
    session_number: Annotated[int, Field(ge=1)]
    value: float
    trend_value: float | None = None  # null, якщо візит один


class S5Statistics(Strict):
    baseline_value: float
    latest_value: float
    delta_absolute: float | None = None
    delta_percent: float | None = None
    slope_per_session: float | None = None
    intercept: float | None = None
    r_squared: Annotated[float, Field(ge=0, le=1)] | None = None


class S5Trend(Strict):
    metric: str
    points: Annotated[list[S5Point], Field(min_length=1)]
    statistics: S5Statistics


class S5Out(Strict):
    trends: list[S5Trend]


# ───────────── Команда лікаря (UI → Оркестратор) ─────────────
class Edit(Strict):
    path: str  # field_id для картки; шлях у S4.out для SOAP, напр. "plan[1].confirmed"
    new_value: Any


class DoctorCommand(Strict):
    target: Literal["card", "soap"]
    id: str  # patient_id для картки, session_id для SOAP
    action: Literal["edit", "approve"]
    edits: list[Edit] = Field(default_factory=list)
    review_started_at: datetime
    at: datetime

    @model_validator(mode="after")
    def _order(self):
        if self.at < self.review_started_at:
            raise ValueError("at раніше за review_started_at")
        return self
