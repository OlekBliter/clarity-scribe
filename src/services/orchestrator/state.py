"""Pure functions describing pipeline state. No database access, no UI text."""

from __future__ import annotations

from enum import Enum
from typing import Any


class Step(str, Enum):
    """Pipeline steps. Values are what is stored in ``sessions.failed_step``."""

    S1 = "s1"
    S6_SANITIZE = "s6_sanitize"
    S2 = "s2"
    S3_GENERATE = "s3_generate"
    S3_RESTORE = "s3_restore"
    S4_GENERATE = "s4_generate"
    S4_RESTORE = "s4_restore"
    MARK_DRAFTED = "mark_drafted"


STEPS: tuple[str, ...] = tuple(step.value for step in Step)

STAGE_KEYS: tuple[str, ...] = (
    "transcription",
    "anonymization",
    "biomarkers",
    "medical_card",
    "soap",
)

_STEP_TO_STAGE: dict[str, str] = {
    Step.S1.value: "transcription",
    Step.S6_SANITIZE.value: "anonymization",
    Step.S2.value: "biomarkers",
    Step.S3_GENERATE.value: "medical_card",
    Step.S3_RESTORE.value: "medical_card",
    Step.S4_GENERATE.value: "soap",
    Step.S4_RESTORE.value: "soap",
    Step.MARK_DRAFTED.value: "soap",
}

# Number of pipeline stages (transcription, anonymization, biomarkers) already
# finished for each session status.
_EARLY_PROGRESS: dict[str, int] = {
    "uploaded": 0,
    "transcribed": 1,
    "sanitized": 2,
    "analyzed": 3,
    "drafted": 3,
    "approved": 3,
}

_SIMPLE_TRANSITIONS: dict[str, Step | None] = {
    "uploaded": Step.S1,
    "transcribed": Step.S6_SANITIZE,
    "sanitized": Step.S2,
    "drafted": None,
    "approved": None,
}


def next_step(session: dict, card: dict | None, note: dict | None) -> Step | None:
    """Return the next pipeline step for a session, or None if nothing is left.

    ``card`` and ``note`` are repository records (dicts) or None. The medical
    card is considered only for session #1.
    """
    status = session["status"]
    if status in _SIMPLE_TRANSITIONS:
        return _SIMPLE_TRANSITIONS[status]
    if status != "analyzed":
        raise ValueError(f"Unknown session status: {status!r}")

    if session["session_number"] == 1:
        if card is None:
            return Step.S3_GENERATE
        if card["status"] == "generated":
            return Step.S3_RESTORE
        card_ready = card["status"] in ("draft", "approved")
    else:
        card_ready = True

    if note is None:
        return Step.S4_GENERATE if card_ready else None
    if note["status"] == "generated":
        return Step.S4_RESTORE
    if note["status"] in ("draft", "approved") and card_ready:
        return Step.MARK_DRAFTED
    return None


def session_badge(status: str, failed_step: str | None, soap_status: str | None = None) -> str | None:
    """Neutral badge kind for one session: error / processing / review / approved."""
    if failed_step:
        return "error"
    if status in ("uploaded", "transcribed", "sanitized", "analyzed"):
        return "processing"
    if status == "drafted":
        return "review"
    if status == "approved":
        return "approved"
    raise ValueError(f"Unknown session status: {status!r}")


def patient_badge(sessions: list[dict]) -> str | None:
    """Badge kind for a patient. Priority: error, processing, review, approved."""
    if not sessions:
        return None
    kinds = [session_badge(s["status"], s.get("failed_step")) for s in sessions]
    for kind in ("error", "processing", "review"):
        if kind in kinds:
            return kind
    return "approved"


def stage_states(
    status: str,
    number: int,
    failed_step: str | None,
    card_status: str | None,
    soap_status: str | None,
) -> list[dict[str, str]]:
    """State of each of the five processing stages.

    Returns rows ``{"key": <STAGE_KEYS item>, "state": ...}`` where state is one
    of ``done``, ``running``, ``pending``, ``not_needed``, ``error``.
    ``running`` marks the first unfinished stage and is never set after a failure.
    """
    if status not in _EARLY_PROGRESS:
        raise ValueError(f"Unknown session status: {status!r}")
    finished = status in ("drafted", "approved")
    early = _EARLY_PROGRESS[status]

    done = {
        "transcription": early >= 1,
        "anonymization": early >= 2,
        "biomarkers": early >= 3,
        "medical_card": finished or card_status in ("draft", "approved"),
        "soap": finished or soap_status in ("draft", "approved"),
    }
    states = {key: "done" if done[key] else "pending" for key in STAGE_KEYS}
    if number >= 2:
        states["medical_card"] = "not_needed"

    failed_stage = _STEP_TO_STAGE.get(failed_step) if failed_step else None
    if failed_stage is not None:
        index = STAGE_KEYS.index(failed_stage)
        for key in STAGE_KEYS[index:]:
            if states[key] != "not_needed":
                states[key] = "pending"
        states[failed_stage] = "error"
    elif not failed_step:
        for key in STAGE_KEYS:
            if states[key] == "pending":
                states[key] = "running"
                break
    return [{"key": key, "state": states[key]} for key in STAGE_KEYS]


def describe_stages(
    session: dict[str, Any],
    card: dict[str, Any] | None = None,
    note: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Convenience wrapper around :func:`stage_states` for repository records."""
    return stage_states(
        session["status"],
        session["session_number"],
        session.get("failed_step"),
        card["status"] if card else None,
        note["status"] if note else None,
    )
