from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from src.schemas.contracts import S2Out


def _resolve_audio_path(session: Mapping[str, Any], data_dir: Path | None) -> str:
    """Resolve absolute path to session audio.wav."""
    from src.services.orchestrator.orchestrator import OrchestratorError

    if data_dir is not None:
        try:
            patient_id = session["patient_id"]
            session_id = session["session_id"]
        except KeyError as exc:
            raise OrchestratorError(f"Missing session identifier key: {exc}") from exc
        path = Path(data_dir) / "audio" / str(patient_id) / str(session_id) / "audio.wav"
        return str(path.resolve())

    if "audio_path" not in session or not session["audio_path"]:
        raise OrchestratorError("Missing 'audio_path' in session record")
    return str(Path(session["audio_path"]).resolve())


def sanitized_segments(segments: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Extract sanitized text segments for LLM consumption.

    This is the ONLY place where `text_sanitized` is read. If any segment is missing
    `text_sanitized` (None or empty), raises OrchestratorError to guarantee that
    `text_raw` never leaks into S3 or S4 LLM prompts.

    Args:
        segments: Sequence of transcript segment records from TranscriptRepo.

    Returns:
        List of dicts formatted as:
        [{"segment_id": int, "speaker": str, "text": str}, ...]

    Raises:
        OrchestratorError: If at least one segment lacks a valid `text_sanitized`.
    """
    from src.services.orchestrator.orchestrator import OrchestratorError

    result: list[dict[str, Any]] = []
    for seg in segments:
        text_sanitized = seg.get("text_sanitized")
        if text_sanitized is None or not str(text_sanitized).strip():
            raise OrchestratorError(
                f"Segment {seg.get('segment_id')} is missing 'text_sanitized'"
            )

        try:
            result.append(
                {
                    "segment_id": seg["segment_id"],
                    "speaker": seg["speaker"],
                    "text": text_sanitized,
                }
            )
        except KeyError as exc:
            raise OrchestratorError(f"Missing required segment key: {exc}") from exc

    return result


def build_s1_in(session: Mapping[str, Any], data_dir: Path) -> dict[str, Any]:
    """Build input dictionary for S1 (AudioTranscriptionService.transcribe).

    Args:
        session: Session record from SessionsRepo.
        data_dir: Base application data directory.

    Returns:
        Dict with keys:
        - "audio_path": str (resolved absolute path to audio.wav)
        - "channel_map": dict (from session)
        - "language_hint": str (from session, e.g. "uk")
    """
    from src.services.orchestrator.orchestrator import OrchestratorError

    audio_path = _resolve_audio_path(session, data_dir)
    language_hint = session.get("language")
    if "channel_map" not in session or not language_hint:
        raise OrchestratorError("Session is missing 'channel_map' or language hint")

    return {
        "audio_path": audio_path,
        "channel_map": session["channel_map"],
        "language_hint": language_hint,
    }


def build_s6_in(
    operation: str,
    items: list[dict[str, str]],
    ner_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build input dictionary for S6 (PrivacyNerService.process).

    Note: When building items for transcript sanitization in _step_sanitize,
    item keys must follow the format `f"seg:{segment_id}"`.

    Args:
        operation: Either "sanitize" or "restore".
        items: List of {"key": str, "text": str} items to process.
        ner_map: Existing entity mapping dict (empty dict `{}` on first call).

    Returns:
        Dict with keys:
        - "operation": str
        - "items": list[{"key": str, "text": str}]
        - "map": dict[str, str]
    """
    return {
        "operation": operation,
        "items": list(items),
        "map": dict(ner_map or {}),
    }


def build_s2_in(
    session: Mapping[str, Any],
    segments: Iterable[Mapping[str, Any]],
    data_dir: Path,
) -> dict[str, Any]:
    """Build input dictionary for S2 (AcousticBiomarkerService.extract_biomarkers).

    Includes ALL segments (both patient and doctor) in the exact order returned by S1.
    Do NOT compute or include `latent_response_time`.

    Args:
        session: Session record from SessionsRepo.
        segments: Ordered transcript segments from TranscriptRepo.
        data_dir: Base application data directory.

    Returns:
        Dict with keys:
        - "audio_path": str (absolute path)
        - "channel_map": dict
        - "segments": list[dict] (in S1 order, without latent_response_time)
    """
    from src.services.orchestrator.orchestrator import OrchestratorError

    audio_path = _resolve_audio_path(session, data_dir)
    if "channel_map" not in session:
        raise OrchestratorError("Session is missing 'channel_map'")

    formatted_segments: list[dict[str, Any]] = []
    for seg in segments:
        try:
            text_val = seg["text"] if "text" in seg else seg["text_raw"]
            formatted_segments.append(
                {
                    "segment_id": seg["segment_id"],
                    "speaker": seg["speaker"],
                    "start_time": seg["start_time"],
                    "end_time": seg["end_time"],
                    "text": text_val,
                }
            )
        except KeyError as exc:
            raise OrchestratorError(f"Missing required segment key for S2: {exc}") from exc

    return {
        "audio_path": audio_path,
        "channel_map": session["channel_map"],
        "segments": formatted_segments,
    }


def build_s3_in(segments: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build input dictionary for S3 (ClinicalService.generate_medical_card).

    Must exclusively use `sanitized_segments(segments)` to prevent raw PII leakage.

    Args:
        segments: Transcript segment records from TranscriptRepo.

    Returns:
        Dict formatted as:
        {"transcription": {"segments": [{"segment_id": ..., "speaker": ..., "text": ...}]}}
    """
    return {
        "transcription": {
            "segments": sanitized_segments(segments),
        }
    }


def build_s4_in(
    segments: Iterable[Mapping[str, Any]],
    biomarkers: S2Out | Mapping[str, Any],
) -> dict[str, Any]:
    """Build input dictionary for S4 (ClinicalService.generate_soap_note).

    Uses sanitized segments plus the current session's S2 biomarkers (no prior visits).

    Args:
        segments: Transcript segment records from TranscriptRepo.
        biomarkers: S2Out model or dict of the current session's biomarkers.

    Returns:
        Dict formatted as:
        {
            "transcription": {"segments": [{"segment_id": ..., "speaker": ..., "text": ...}]},
            "biomarkers": dict,
        }
    """
    biomarkers_dict = (
        biomarkers.model_dump() if isinstance(biomarkers, S2Out) else dict(biomarkers)
    )
    return {
        "transcription": {
            "segments": sanitized_segments(segments),
        },
        "biomarkers": biomarkers_dict,
    }


def build_s5_in(visits: list[dict[str, Any]]) -> dict[str, Any]:
    """Build input dictionary for S5 (DynamicsService.calculate).

    Args:
        visits: Pre-formatted list of approved visit biomarkers returned by
            `BiomarkersRepo.list_approved_for_patient`.

    Returns:
        Dict formatted as: {"visits": visits}
    """
    return {"visits": list(visits)}