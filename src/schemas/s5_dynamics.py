import math
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from .common import ContractModel, NonEmptyStr, SessionNumber, ensure_unique_ascending
from .s2_biomarkers import S2Out

_TOL = 0.01  # допуск на округлення у statistics


class S5Visit(ContractModel):
    session_number: SessionNumber
    biomarkers: S2Out


class S5In(ContractModel):
    visits: Annotated[list[S5Visit], Field(min_length=1)]

    @field_validator("visits")
    @classmethod
    def _sorted(cls, v: list[S5Visit]):
        ensure_unique_ascending([x.session_number for x in v], "session_number")
        return v


class S5Point(ContractModel):
    session_number: SessionNumber
    value: float
    trend_value: float | None = None


class S5Statistics(ContractModel):
    baseline_value: float
    latest_value: float
    delta_absolute: float | None = None
    delta_percent: float | None = None
    slope_per_session: float | None = None
    intercept: float | None = None
    r_squared: Annotated[float, Field(ge=0, le=1)] | None = None


class S5Trend(ContractModel):
    metric: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    points: Annotated[list[S5Point], Field(min_length=1)]
    statistics: S5Statistics

    @model_validator(mode="after")
    def _consistent(self):
        ensure_unique_ascending([p.session_number for p in self.points], "session_number")
        st, pts = self.statistics, self.points
        if not math.isclose(st.baseline_value, pts[0].value, abs_tol=_TOL):
            raise ValueError("baseline_value не збігається зі значенням першого візиту")
        if not math.isclose(st.latest_value, pts[-1].value, abs_tol=_TOL):
            raise ValueError("latest_value не збігається зі значенням останнього візиту")

        derived = (st.delta_absolute, st.delta_percent, st.slope_per_session, st.intercept, st.r_squared)
        if len(pts) == 1:
            if any(v is not None for v in derived) or pts[0].trend_value is not None:
                raise ValueError("для одного візиту всі похідні поля й trend_value мають бути null")
            return self

        if st.delta_absolute is None or st.slope_per_session is None or st.intercept is None:
            raise ValueError("для ≥2 візитів потрібні delta_absolute, slope_per_session, intercept")
        if any(p.trend_value is None for p in pts):
            raise ValueError("для ≥2 візитів кожна точка має trend_value")
        if not math.isclose(st.delta_absolute, st.latest_value - st.baseline_value, abs_tol=_TOL):
            raise ValueError("delta_absolute ≠ latest_value − baseline_value")
        if st.delta_percent is not None and st.baseline_value != 0:
            expected = st.delta_absolute / st.baseline_value * 100
            if not math.isclose(st.delta_percent, expected, abs_tol=_TOL):
                raise ValueError("delta_percent не відповідає delta_absolute / baseline_value")
        return self


class S5Out(ContractModel):
    trends: list[S5Trend]

    @field_validator("trends")
    @classmethod
    def _unique_metrics(cls, t: list[S5Trend]):
        names = [x.metric for x in t]
        if len(set(names)) != len(names):
            raise ValueError("metric мають бути унікальними")
        return t
