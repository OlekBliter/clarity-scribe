"""ClarityScribe · contracts (lite, for MVP). Requires pydantic >= 2.6.

Strict  — internal systems: extra key = error.
Lenient — LLM outputs (S3, S4): extra keys are ignored to avoid wasting tokens on retries.
Input contracts (S1.in … S5.in) are not validated: they are constructed by the Orchestrator itself.
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


# ───────────── S1 · Transcription ─────────────
class S1Metadata(Strict):  # stored in sessions.transcript_meta
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
            raise ValueError("segment_id must be sequential starting from 0")
        return self


# ───────────── S6 · NER ─────────────
EntityType = Literal["PERSON", "ADDRESS", "PHONE", "EMAIL", "ORG", "BIRTH_DATE", "OTHER_ID"]
PLACEHOLDER_RE = re.compile(r"\[[^\[\]_\s]+_\d+\]")  # [NAME_1], [ADDRESS_2] …


class NerEntry(Strict):
    type: EntityType
    original: str = Field(min_length=1)


NerMap = dict[str, NerEntry]  # sessions.ner_map: {"[NAME_1]": {"type": "PERSON", "original": "…"}}


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
                    raise ValueError(f"{it.key}: placeholder {ph} is missing from map")
            for ph, e in self.map.items():
                if e.original in it.text:  # primary privacy check
                    raise ValueError(f"{it.key}: unmasked entity {ph} remains in text")
        return self


class S6RestoreOut(Strict):
    items: list[NerItem]

    @model_validator(mode="after")
    def _restored(self):
        for it in self.items:
            if PLACEHOLDER_RE.search(it.text):
                raise ValueError(f"{it.key}: unresolved placeholders remain")
        return self


# ───────────── S2 · Biomarkers (stored entirely in biomarkers.data) ─────────────
class RawDspFeatures(Strict):
    f0_variability_sd: Annotated[float, Field(ge=0)]
    f0_mean_hz: Annotated[float, Field(gt=0)]
    jitter_percent: Annotated[float, Field(ge=0)]
    shimmer_percent: Annotated[float, Field(ge=0)]
    hnr_db: float
    speech_rate_syllables_per_sec: Annotated[float, Field(ge=0)]
    pause_ratio: Annotated[float, Field(ge=0, le=1)]
    mean_latent_response_time_sec: Annotated[float, Field(ge=0)] | None  # null if there is no latency at all


class IntrasessionDynamics(Strict):
    f0_variability_change_percent: float
    speech_rate_change_percent: float
    pause_ratio_change_percent: float
    trend_summary: str  # e.g., "activation"; full list of values not yet finalized


class InferredIndices(Strict):
    affect_flatness_flag: bool
    vocal_jitter_percentile: Annotated[float, Field(ge=0, le=100)]
    psychomotor_retardation_index: float
    intrasession_dynamics: IntrasessionDynamics | None  # null for recordings that are too short


class WindowChunk(Strict):
    window_index: Annotated[int, Field(ge=0)]
    time_range: str = Field(pattern=r"^\d{2,}:[0-5]\d-\d{2,}:[0-5]\d$")  # "00:00-05:00"
    f0_variability_sd: Annotated[float, Field(ge=0)]
    speech_rate_syllables_per_sec: Annotated[float, Field(ge=0)]
    pause_ratio: Annotated[float, Field(ge=0, le=1)]


class S2Out(Strict):
    raw_dsp_features: RawDspFeatures
    inferred_indices: InferredIndices
    window_chunks: list[WindowChunk]


# ───────────── S3 · Medical Card (LLM) ─────────────
BOOL_FIELDS = {"history.on_medication", "safety.suicidal_past", "safety.suicidal_now"}
MODEL_FIELDS = (  # all fields with filled_by = M
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
                raise ValueError("filled requires value and evidence")
            if isinstance(self.value, bool) != (self.field_id in BOOL_FIELDS):
                raise ValueError("value type does not match the field type (bool / text)")
        elif self.value is not None:
            raise ValueError(f"{self.status}: value must be null")
        if self.status == "contradictory" and not self.contradiction_text:
            raise ValueError("contradictory requires contradiction_text")
        return self


class S3Out(Lenient):
    fields: list[S3Field]

    @model_validator(mode="after")
    def _complete(self):
        ids = [f.field_id for f in self.fields]
        if len(set(ids)) != len(ids) or set(ids) != set(MODEL_FIELDS):
            raise ValueError("the response must contain exactly all 22 M fields, without duplicates")
        return self

    def check_evidence(self, known_segment_ids: set[int]) -> None:
        """Called by Orchestrator: evidence must reference existing segments."""
        for f in self.fields:
            if not set(f.evidence) <= known_segment_ids:
                raise ValueError(f"{f.field_id}: evidence references non-existent segments")


class CardField(Lenient):  # medical_cards.data: S3 fields + doctor-entered fields
    field_id: str
    status: Literal["filled", "not_discussed", "contradictory", "doctor_input"]
    value: str | bool | None = None
    edited_by_doctor: bool = False


class MedicalCardData(Lenient):
    fields: list[CardField] = Field(default_factory=list)  # [] — if S3 is disabled


# ───────────── S4 · SOAP (LLM). Single model for both draft and final ─────────────
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
    confirmed: bool | None = None  # final only: doctor confirmed the recommended item


class S4Out(Lenient):
    subjective: Subjective
    objective: Objective
    assessment: Assessment
    plan: list[PlanItem] = Field(default_factory=list)


# ───────────── S5 · Dynamics (computed on the fly, not stored) ─────────────
class S5Point(Strict):
    session_number: Annotated[int, Field(ge=1)]
    value: float
    trend_value: float | None = None  # null if there is only one session


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


# ───────────── Doctor Command (UI → Orchestrator) ─────────────
class Edit(Strict):
    path: str  # field_id for card; path in S4.out for SOAP, e.g., "plan[1].confirmed"
    new_value: Any


class DoctorCommand(Strict):
    target: Literal["card", "soap"]
    id: str  # patient_id for card, session_id for SOAP
    action: Literal["edit", "approve"]
    edits: list[Edit] = Field(default_factory=list)
    review_started_at: datetime
    at: datetime

    @model_validator(mode="after")
    def _order(self):
        if self.at < self.review_started_at:
            raise ValueError("at is earlier than review_started_at")
        return self