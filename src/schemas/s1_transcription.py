from typing import Annotated

from pydantic import Field, field_validator, model_validator

from .common import (
    Confidence, ContractModel, Language, NonEmptyStr, Seconds, SegmentId, Speaker,
    ensure_unique_ascending, relative_media_path,
)

_EPS = 0.5  # допуск (с) на округлення часових міток


class ChannelMap(ContractModel):
    DOCTOR: Annotated[int, Field(ge=0, le=1)] = 0
    PATIENT: Annotated[int, Field(ge=0, le=1)] = 1

    @model_validator(mode="after")
    def _distinct(self):
        if self.DOCTOR == self.PATIENT:
            raise ValueError("DOCTOR і PATIENT мають бути на різних каналах")
        return self


class S1In(ContractModel):
    audio_path: Annotated[str, relative_media_path(".wav", ".mp3")]
    channel_map: ChannelMap = Field(default_factory=ChannelMap)
    language_hint: Language | None = None
    patient_audio_out: Annotated[str, relative_media_path(".wav")]


class S1Metadata(ContractModel):
    audio_duration_sec: Seconds
    doctor_speaking_time_sec: Seconds
    patient_speaking_time_sec: Seconds
    silence_time_sec: Seconds

    @model_validator(mode="after")
    def _within_duration(self):
        for name in ("doctor_speaking_time_sec", "patient_speaking_time_sec", "silence_time_sec"):
            if getattr(self, name) > self.audio_duration_sec + _EPS:
                raise ValueError(f"{name} більший за audio_duration_sec")
        return self


class S1Segment(ContractModel):
    segment_id: SegmentId
    speaker: Speaker
    start_time: Seconds
    end_time: Seconds
    text: NonEmptyStr
    confidence: Confidence | None = None  # у БД колонка nullable

    @model_validator(mode="after")
    def _times(self):
        if self.end_time < self.start_time:
            raise ValueError("end_time менший за start_time")
        return self


class S1Out(ContractModel):
    language: Language
    metadata: S1Metadata
    segments: list[S1Segment]

    @field_validator("segments")
    @classmethod
    def _order(cls, segs: list[S1Segment]):
        # segment_id з 0, без пропусків, за start_time (при рівності — DOCTOR першим)
        if [s.segment_id for s in segs] != list(range(len(segs))):
            raise ValueError("segment_id мають іти підряд з 0")
        keys = [(s.start_time, 0 if s.speaker == Speaker.DOCTOR else 1) for s in segs]
        if keys != sorted(keys):
            raise ValueError("сегменти мають бути впорядковані за start_time (при рівності DOCTOR першим)")
        return segs

    @model_validator(mode="after")
    def _within_audio(self):
        for s in self.segments:
            if s.end_time > self.metadata.audio_duration_sec + _EPS:
                raise ValueError(f"сегмент {s.segment_id} закінчується після кінця запису")
        return self
