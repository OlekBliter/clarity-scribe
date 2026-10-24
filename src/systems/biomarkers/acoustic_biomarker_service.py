import os
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
            start_t = seg.get("start_time", 0.0)
            end_t = seg.get("end_time", 0.0)

            if start_t >= end_t:
                continue

            if start_t < total_duration:
                try:
                    part = sound_mono.extract_part(
                        from_time=max(0.0, start_t),
                        to_time=min(total_duration, end_t)
                    )
                    sound_segments.append(part)
                    segment_dsp_results.append(analyze_segment_pitch_and_quality(part))
                except Exception as e:
                    raise AudioProcessingError(f"Error extracting segment ({start_t}-{end_t}): {e}") from e

        aggregated_dsp = aggregate_segment_dsp(segment_dsp_results)
        f0_sd_st = aggregated_dsp.pop("f0_sd_st", 0.0)

        speech_rate, pause_ratio, mean_latency = analyze_speech_tempo_and_internal_pauses(
            sound_segments, segments_data
        )

        raw_dsp_dict = {
            **aggregated_dsp,
            "speech_rate_syllables_per_sec": speech_rate,
            "pause_ratio": pause_ratio,
            "mean_latent_response_time_sec": mean_latency
        }

        inferred_dict = compute_inferred_indices(raw_dsp_dict, f0_sd_st)

        window_chunks, dynamics = analyze_windows_and_dynamics(
            sound_mono, segments_data, total_duration, window_sec=self.default_window_sec
        )

        return {
            "raw_dsp_features": raw_dsp_dict,
            "inferred_indices": inferred_dict,
            "intrasession_dynamics": dynamics,
            "window_chunks": window_chunks
        }
