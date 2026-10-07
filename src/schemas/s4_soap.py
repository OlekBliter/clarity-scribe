from typing import Annotated

from pydantic import Field, field_validator, model_validator

from .common import (
    AssessmentBasis, ContractModel, NonEmptyStr, PlanOrigin, SegmentId, SessionNumber, TextSegment,
    check_text_segments,
)
from .s2_biomarkers import BIOMARKER_KEYS, S2Out


# ───────────── S4.in (санітизований) ─────────────
class S4In(ContractModel):
    session_number: SessionNumber  # довідково; на вміст нотатки не впливає
    segments: Annotated[list[TextSegment], Field(min_length=1)]
    biomarkers: S2Out  # весь S2.out поточної сесії

    @field_validator("segments")
    @classmethod
    def _ids(cls, v):
        return check_text_segments(v)


# ───────────── S4.out ─────────────
class Subjective(ContractModel):
    text: NonEmptyStr
    source_segments: list[SegmentId] = Field(default_factory=list)


class Objective(ContractModel):
    text: NonEmptyStr
    biomarker_refs: list[str] = Field(default_factory=list)

    @field_validator("biomarker_refs")
    @classmethod
    def _known_keys(cls, refs: list[str]):
        unknown = [r for r in refs if r not in BIOMARKER_KEYS]
        if unknown:
            raise ValueError(f"невідомі біомаркери: {unknown}")
        return refs


class Assessment(ContractModel):
    text: NonEmptyStr
    basis: AssessmentBasis


class PlanItem(ContractModel):
    text: NonEmptyStr
    origin: PlanOrigin


class SoapNote(ContractModel):
    subjective: Subjective
    objective: Objective
    assessment: Assessment
    plan: list[PlanItem] = Field(default_factory=list)

    def check_against_input(self, inp: S4In) -> None:
        known = {s.segment_id for s in inp.segments}
        bad = [i for i in self.subjective.source_segments if i not in known]
        if bad:
            raise ValueError(f"source_segments посилаються на відсутні segment_id {bad}")


class PlanItemFinal(PlanItem):
    confirmed: bool | None = None

    @model_validator(mode="after")
    def _only_recommended(self):
        if self.confirmed is not None and self.origin != PlanOrigin.RECOMMENDED:
            raise ValueError("confirmed стосується лише пунктів recommended")
        return self


class SoapNoteFinal(SoapNote):
    plan: list[PlanItemFinal] = Field(default_factory=list)

    @property
    def pending_recommendations(self) -> list[PlanItemFinal]:
        return [p for p in self.plan if p.origin == PlanOrigin.RECOMMENDED and p.confirmed is None]
