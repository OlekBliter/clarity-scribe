"""Build service inputs from repository records without exposing raw text to LLMs."""

from pathlib import Path
from typing import Any

from src.services.orchestrator.errors import OrchestratorError


def _audio_path(session: dict[str, Any], data_dir: str | Path) -> str:
    """Resolve the recorded audio path against the application data directory."""
    path = Path(session["audio_path"])
    return str((path if path.is_absolute() else Path(data_dir) / path).resolve())


def build_s1_in(session: dict[str, Any], data_dir: str | Path) -> dict[str, Any]:
    """Build the S1 transcription input."""
    return {
        "audio_path": _audio_path(session, data_dir),
        "channel_map": session["channel_map"],
        "language_hint": session["language"],
    }


def build_s6_in(
    operation: str,
    items: list[dict[str, str]],
    ner_map: dict[str, Any],
) -> dict[str, Any]:
    """Build an S6 sanitize or restore request."""
    return {"operation": operation, "items": items, "map": ner_map}


def build_s2_in(
    session: dict[str, Any], segments: list[dict[str, Any]], data_dir: str | Path,
) -> dict[str, Any]:
    """Build S2 input with all speaker segments, ordered as stored by S1."""
    return {
        "audio_path": _audio_path(session, data_dir),
        "channel_map": session["channel_map"],
        "segments": [
            {
                "segment_id": row["segment_id"],
                "speaker": row["speaker"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "text": row["text_raw"],
                "confidence": row["confidence"],
            }
            for row in segments
        ],
    }


def sanitized_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prepare sanitized-only transcript text for the external LLM."""
    result = []
    for row in segments:
        sanitized = row.get("text_sanitized")
        if sanitized is None:
            raise OrchestratorError(
                f"Segment {row['segment_id']} has not been sanitized"
            )
        result.append({
            "segment_id": row["segment_id"],
            "speaker": row["speaker"],
            "text": sanitized,
        })
    return result


def build_s3_in(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Build S3 input from sanitized text only."""
    return {"transcription": {"segments": sanitized_segments(segments)}}


def build_s4_in(
    segments: list[dict[str, Any]], biomarkers: dict[str, Any],
) -> dict[str, Any]:
    """Build S4 input from sanitized text and current-session biomarkers."""
    return {
        "transcription": {"segments": sanitized_segments(segments)},
        "biomarkers": biomarkers,
    }


def build_s5_in(visits: list[dict[str, Any]]) -> dict[str, Any]:
    """Build S5 input from approved visits."""
    return {"visits": visits}
