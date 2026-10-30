import os
import math
import parselmouth
from typing import Dict, Any, Optional

from .dsp_pitch_quality import analyze_segment_pitch_and_quality, aggregate_segment_dsp
from .dsp_tempo_pauses import analyze_speech_tempo_and_internal_pauses
from .index_calculator import compute_inferred_indices
from .windowing import analyze_windows_and_dynamics
from .exceptions import (
    AcousticBiomarkerError,
    AudioFileNotFoundError,
    AudioProcessingError,
    InvalidSegmentError,
)


class AcousticBiomarkerService:
    """
    Stateless Service Class for extracting acoustic biomarkers from patient audio.
    Follows orchestrator execution contract returning pure Python dictionary payloads.
    """

    def __init__(self, default_window_sec: Optional[float] = None) -> None:
        self.default_window_sec = default_window_sec

    def extract_biomarkers(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public entry point invoked by orchestrator.

        Args:
            input_data: Standard Python dictionary adhering to approved input schema.

        Returns:
            Standard Python dictionary adhering to approved output schema.
        """
        audio_path = input_data.get("patient_audio_path")
        segments_data = input_data.get("segments", [])

        if not audio_path or not os.path.exists(audio_path):
            raise AudioFileNotFoundError(f"Audio file at path '{audio_path}' was not found.")

        try:
            sound_raw = parselmouth.Sound(audio_path)
            sound_mono = sound_raw.to_mono() if sound_raw.n_channels > 1 else sound_raw
            total_duration = sound_mono.duration
        except Exception as e:
            raise AudioProcessingError(f"Failed to load or process audio file '{audio_path}': {e}") from e

        sound_segments = []
        segment_dsp_results = []

        for seg in segments_data:
            if not isinstance(seg, dict):
                raise InvalidSegmentError("Each segment must be a dictionary.")

            start_t = seg.get("start_time")
            end_t = seg.get("end_time")
            if (
                isinstance(start_t, bool)
                or isinstance(end_t, bool)
                or not isinstance(start_t, (int, float))
                or not isinstance(end_t, (int, float))
                or not math.isfinite(start_t)
                or not math.isfinite(end_t)
                or start_t < 0
                or end_t <= start_t
                or start_t >= total_duration
                or end_t > total_duration
            ):
                raise InvalidSegmentError(
                    f"Invalid segment timestamps: start_time={start_t}, end_time={end_t}."
                )

            try:
                part = sound_mono.extract_part(from_time=start_t, to_time=end_t)
                sound_segments.append(part)
                segment_dsp_results.append(analyze_segment_pitch_and_quality(part))
            except Exception as e:
                raise AudioProcessingError(f"Error extracting segment ({start_t}-{end_t}): {e}") from e

        aggregated_dsp = aggregate_segment_dsp(segment_dsp_results)
        if not any(result.get("n_voiced", 0) > 0 for result in segment_dsp_results):
            raise AudioProcessingError(
                "No valid voiced material was found for biomarker extraction."
            )
        f0_sd_st = aggregated_dsp.pop("f0_sd_st", 0.0)
        f0_sd_hz_within = aggregated_dsp.pop("f0_sd_hz_within", 0.0)  

        speech_rate, pause_ratio, mean_latency = analyze_speech_tempo_and_internal_pauses(
            sound_segments, segments_data
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
            sound_mono, segments_data, total_duration, window_sec=self.default_window_sec
        )

        inferred_dict["intrasession_dynamics"] = dynamics
        result = {
            "raw_dsp_features": raw_dsp_dict,
            "inferred_indices": inferred_dict,
            "window_chunks": window_chunks
        }
        return result
