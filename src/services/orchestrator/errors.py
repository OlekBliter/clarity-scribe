"""Exceptions raised by the orchestrator package."""

from __future__ import annotations


class OrchestratorError(Exception):
    """Base exception for all orchestrator-level errors."""


class DoctorInputError(OrchestratorError):
    """The doctor performed an action that is not allowed.

    ``user_message`` is a ready-to-show Ukrainian text. The facade passes it
    to the UI as is; every other exception is replaced with a generic text.
    """

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class InvalidTransitionError(DoctorInputError):
    """The action is impossible in the current state (e.g. editing an approved note)."""


class StepFailedError(OrchestratorError):
    """Raised when a pipeline step fails; keeps the step name and the cause."""

    def __init__(self, step_name: str, message: str, cause: Exception | None = None) -> None:
        super().__init__(f"Step '{step_name}' failed: {message}")
        self.step_name = step_name
        self.error_message = message
        self.cause = cause
