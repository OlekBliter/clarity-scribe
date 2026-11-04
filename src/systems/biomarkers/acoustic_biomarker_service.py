import os
import math
import parselmouth
from typing import Dict, Any, Optional
from numbers import Real

from .dsp_pitch_quality import analyze_segment_pitch_and_quality, aggregate_segment_dsp
from .dsp_tempo_pauses import analyze_speech_tempo_and_internal_pauses
from .index_calculator import compute_inferred_indices
from .windowing import analyze_windows_and_dynamics
from .exceptions import (
    AudioFileNotFoundError,
    AudioProcessingError,
    InvalidSegmentError,
)
from src.schemas.contracts import S2Out

REQUIRED_ROLES = {"DOCTOR", "PATIENT"}


class AcousticBiomarkerService:
    """
    Extract patient acoustic biomarkers using a dict -> dict contract.

    Input:
        {
            "audio_path": ...,
            "channel_map": ...,
            "segments": [
                {
                    "segment_id": ...,
                    "speaker": ...,
                    "start_time": ...,
                    "end_time": ...,
                    "text": ...,
                    "confidence": ...,
                }
            ],
        }

    Output:
        {
            "raw_dsp_features": ...,
            "inferred_indices": ...,
            "window_chunks": ...,
        }

    The source audio keeps the original recording timeline. Only PATIENT
    segments and the PATIENT channel are analyzed.
    """

    def __init__(self, default_window_sec: Optional[float] = None) -> None:
        if default_window_sec is not None and (
            not isinstance(default_window_sec, Real)
            or not math.isfinite(float(default_window_sec))
            or default_window_sec <= 0
        ):
            raise ValueError("default_window_sec must be a positive finite number.")
        self.default_window_sec = default_window_sec

    def extract_biomarkers(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public entry point invoked by orchestrator.

        Args:
            input_data: Standard Python dictionary adhering to approved input schema.

        Returns:
            Standard Python dictionary adhering to approved output schema.
        """
        if not isinstance(input_data, dict):
            raise InvalidSegmentError("S2 input must be a dictionary.")
        missing_keys = {"audio_path", "channel_map", "segments"} - input_data.keys()
        if missing_keys:
            raise InvalidSegmentError(
                f"S2 input is missing required keys: {sorted(missing_keys)}."
            )

        audio_path = input_data["audio_path"]
        channel_map = input_data["channel_map"]
        segments_data = input_data["segments"]

        if not audio_path or not os.path.exists(audio_path):
            raise AudioFileNotFoundError(f"Audio file at path '{audio_path}' was not found.")
        if not isinstance(channel_map, dict):
            raise InvalidSegmentError("channel_map must be a dictionary.")
        missing_roles = REQUIRED_ROLES - channel_map.keys()
        if missing_roles:
            raise InvalidSegmentError(
                f"channel_map must contain {sorted(missing_roles)}."
            )
        if not isinstance(segments_data, list):
            raise InvalidSegmentError("segments must be a list.")

        try:
            sound_raw = parselmouth.Sound(audio_path)
            for role in REQUIRED_ROLES:
                channel = channel_map[role]
                if (
                    not isinstance(channel, int)
                    or isinstance(channel, bool)
                    or channel < 0
                    or channel >= sound_raw.n_channels
                ):
                    raise InvalidSegmentError(
                        f"channel_map[{role!r}] must reference an existing channel."
                    )
            patient_channel = channel_map["PATIENT"]
            sound_patient = (
                sound_raw.extract_channel(patient_channel + 1)
                if sound_raw.n_channels > 1
                else sound_raw
            )
            total_duration = sound_patient.duration
        except (parselmouth.PraatError, RuntimeError, ValueError) as e:
            raise AudioProcessingError(f"Failed to load or process audio file '{audio_path}': {e}") from e

        sound_segments = []
        segment_dsp_results = []
        patient_segments = []
        last_doctor_end = None
        last_speaker = None

        for seg in segments_data:
            if not isinstance(seg, dict):
                raise InvalidSegmentError("Each segment must be a dictionary.")
            speaker = seg.get("speaker")
            if speaker not in REQUIRED_ROLES:
                raise InvalidSegmentError(f"Unknown segment speaker: {speaker!r}.")

            start_t = seg.get("start_time")
            end_t = seg.get("end_time")
            if (
                not isinstance(start_t, Real)
                or isinstance(start_t, bool)
                or not isinstance(end_t, Real)
                or isinstance(end_t, bool)
                or not math.isfinite(float(start_t))
                or not math.isfinite(float(end_t))
                or start_t < 0
                or end_t <= start_t
                or end_t > total_duration
            ):
                raise InvalidSegmentError(
                    f"Invalid segment timestamps: {start_t}-{end_t}."
                )

            if speaker == "DOCTOR":
                last_doctor_end = float(end_t)
                last_speaker = speaker
                continue

            patient_segment = dict(seg)
            if last_speaker == "DOCTOR" and last_doctor_end is not None:
                patient_segment["latent_response_time"] = max(
                    0.0, float(start_t) - last_doctor_end
                )
            last_speaker = speaker

            try:
                part = sound_patient.extract_part(
                    from_time=float(start_t),
                    to_time=float(end_t)
                )
                patient_segments.append(patient_segment)
                sound_segments.append(part)
                segment_dsp_results.append(analyze_segment_pitch_and_quality(part))
            except (parselmouth.PraatError, RuntimeError, ValueError) as e:
                raise AudioProcessingError(f"Error extracting segment ({start_t}-{end_t}): {e}") from e

        aggregated_dsp = aggregate_segment_dsp(segment_dsp_results)
        if not any(result.get("n_voiced", 0) > 0 for result in segment_dsp_results):
            raise AudioProcessingError(
                "No valid voiced material was found for biomarker extraction."
            )
        f0_sd_st = aggregated_dsp.pop("f0_sd_st", 0.0)
        f0_sd_hz_within = aggregated_dsp.pop("f0_sd_hz_within", 0.0)  

        speech_rate, pause_ratio, mean_latency = analyze_speech_tempo_and_internal_pauses(
            sound_segments, patient_segments
        )

        raw_dsp_dict = {
            **aggregated_dsp,
            "speech_rate_syllables_per_sec": speech_rate,
            "pause_ratio": pause_ratio,
            "mean_latent_response_time_sec": mean_latency
        }

        # for a correct comparison send 2 values (f0_sd_st, f0_sd_hz_within)
        inferred_dict = compute_inferred_indices(raw_dsp_dict, f0_sd_st, f0_sd_hz_within)

        window_chunks, dynamics = analyze_windows_and_dynamics(
            sound_patient, patient_segments, total_duration, window_sec=self.default_window_sec
        )

        inferred_dict["intrasession_dynamics"] = dynamics
        result = {
            "raw_dsp_features": raw_dsp_dict,
            "inferred_indices": inferred_dict,
            "window_chunks": window_chunks
        }
        return S2Out.model_validate(result).model_dump()
