"""Facade package: the only part of ``services`` the UI may import."""
from .facade import (
    BADGE_KINDS,
    DIRECTIONS,
    FIELD_STATES,
    PROCESSING_STEPS,
    STAGE_KEYS,
    STAGE_STATES,
    ClarityScribeFacade,
    FacadeError,
    ProgressCallback,
)
from .stub import ClarityScribeFacadeStub

__all__ = [
    "BADGE_KINDS",
    "DIRECTIONS",
    "FIELD_STATES",
    "PROCESSING_STEPS",
    "STAGE_KEYS",
    "STAGE_STATES",
    "ClarityScribeFacade",
    "ClarityScribeFacadeStub",
    "FacadeError",
    "ProgressCallback",
]
