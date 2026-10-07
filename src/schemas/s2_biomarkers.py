import re
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator, model_validator

from .common import ContractModel, NonEmptyStr, Seconds, SegmentId, ensure_unique_ascending, relative_media_path


# ───────────── S2.in ─────────────
class S2SegmentIn(ContractModel):
    segment_id: SegmentId
    start_time: Seconds
    end_time: Seconds

    latent_response_time: Seconds | None = None

    @model_validator(mode="after")
    def _times(self):
        if self.end_time < self.start_time:
            raise ValueError("end_time менший за start_time")
        return self


class S2In(ContractModel):
    patient_audio_path: Annotated[str, relative_media_path(".wav")]
    segments: Annotated[list[S2SegmentIn], Field(min_length=1)]

    @field_validator("segments")
    @classmethod
    def _ids(cls, segs: list[S2SegmentIn]):
        ensure_unique_ascending([s.segment_id for s in segs], "segment_id")
        return segs


# ───────────── S2.out ─────────────
class RawDspFeatures(ContractModel):
    f0_variability_sd: Annotated[float, Field(ge=0)]
    f0_mean_hz: Annotated[float, Field(gt=0)]
    jitter_percent: Annotated[float, Field(ge=0)]
    shimmer_percent: Annotated[float, Field(ge=0)]
    hnr_db: float
    speech_rate_syllables_per_sec: Annotated[float, Field(ge=0)]
    pause_ratio: Annotated[float, Field(ge=0, le=1)]

    mean_latent_response_time_sec: Annotated[float, Field(ge=0)] | None


# значення поки що не зафіксовані контрактом (відомо лише "activation"), тому перевіряємо лише формат
TrendSummary = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z_]*$")]


class IntrasessionDynamics(ContractModel):
    f0_variability_change_percent: float
    speech_rate_change_percent: float
    pause_ratio_change_percent: float
    trend_summary: TrendSummary


class InferredIndices(ContractModel):
    affect_flatness_flag: bool
    vocal_jitter_percentile: Annotated[float, Field(ge=0, le=100)]
    psychomotor_retardation_index: float
    # null, якщо запис закороткий для порівняння вікон (припущення; у контракті приклад завжди заповнений)
    intrasession_dynamics: IntrasessionDynamics | None


_TIME_RANGE = re.compile(r"^(\d{2,}):([0-5]\d)-(\d{2,}):([0-5]\d)$")


class WindowChunk(ContractModel):
    window_index: Annotated[int, Field(ge=0)]
    time_range: NonEmptyStr  # «мм:сс-мм:сс» від початку запису (для відображення)
    f0_variability_sd: Annotated[float, Field(ge=0)]
    speech_rate_syllables_per_sec: Annotated[float, Field(ge=0)]
    pause_ratio: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def _range(self):
        m = _TIME_RANGE.match(self.time_range)
        if not m:
            raise ValueError("time_range має формат «мм:сс-мм:сс»")
        if self.end_sec <= self.start_sec:
            raise ValueError("кінець вікна має бути пізніше за початок")
        return self

    @property
    def start_sec(self) -> int:
        m = _TIME_RANGE.match(self.time_range)
        return int(m.group(1)) * 60 + int(m.group(2))

    @property
    def end_sec(self) -> int:
        m = _TIME_RANGE.match(self.time_range)
        return int(m.group(3)) * 60 + int(m.group(4))


RAW_METRIC_NAMES: tuple[str, ...] = tuple(RawDspFeatures.model_fields)
INDEX_METRIC_NAMES: tuple[str, ...] = ("vocal_jitter_percentile", "psychomotor_retardation_index")
SCALAR_METRIC_NAMES: frozenset[str] = frozenset(RAW_METRIC_NAMES + INDEX_METRIC_NAMES)
# усі ключі, на які може посилатись S4.out.objective.biomarker_refs
BIOMARKER_KEYS: frozenset[str] = frozenset(RawDspFeatures.model_fields) | frozenset(InferredIndices.model_fields)


class S2Out(ContractModel):
    raw_dsp_features: RawDspFeatures
    inferred_indices: InferredIndices
    window_chunks: list[WindowChunk]

    @field_validator("window_chunks")
    @classmethod
    def _windows(cls, w: list[WindowChunk]):
        ensure_unique_ascending([c.window_index for c in w], "window_index")
        return w

    def scalar_metrics(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for name in RAW_METRIC_NAMES:
            v = getattr(self.raw_dsp_features, name)
            if v is not None:
                out[name] = float(v)
        for name in INDEX_METRIC_NAMES:
            out[name] = float(getattr(self.inferred_indices, name))
        return out
