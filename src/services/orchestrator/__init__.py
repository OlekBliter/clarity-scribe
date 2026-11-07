"""Orchestrator package initialization and public exports."""

from src.services.orchestrator.errors import (
    DoctorInputError,
    InvalidTransitionError,
    OrchestratorError,
    StepFailedError,
)
from src.services.orchestrator.orchestrator import (
    SYSTEM_ERRORS,
    Orchestrator,
    build_default_systems,
)
from src.services.orchestrator.state import (
    STAGE_KEYS,
    STEPS,
    Step,
    describe_stages,
    next_step,
    patient_badge,
    session_badge,
    stage_states,
)

__all__ = [
    "Orchestrator",
    "build_default_systems",
    "OrchestratorError",
    "DoctorInputError",
    "InvalidTransitionError",
    "StepFailedError",
    "SYSTEM_ERRORS",
    "Step",
    "STEPS",
    "STAGE_KEYS",
    "next_step",
    "session_badge",
    "patient_badge",
    "stage_states",
    "describe_stages",
]
