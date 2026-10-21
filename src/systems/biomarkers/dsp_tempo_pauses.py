import parselmouth
import numpy as np
from typing import List, Optional, Tuple, Dict, Any


def analyze_speech_tempo_and_internal_pauses(
    sound_segments: List[parselmouth.Sound],
    segments_meta: List[Dict[str, Any]]
) -> Tuple[float, float, Optional[float]]:
    """
    Analyzes speech rate and internal pause ratios strictly within patient utterances.

    Args:
        sound_segments: Parselmouth Sound fragments for patient speech.
        segments_meta: Raw metadata dictionaries containing latent response times.

    Returns:
        Tuple of (speech_rate, pause_ratio, mean_latency).
    """
    total_segment_duration = 0.0
    total_phonation_duration = 0.0
    total_syllables = 0
    min_distance_frames = 12

    for snd in sound_segments:
        duration = snd.duration
        if duration < 0.1:
            continue

        total_segment_duration += duration

        intensity = snd.to_intensity(time_step=0.01)
        intensity_vals = intensity.values[0] if len(intensity.values) > 0 else np.array([])

        if len(intensity_vals) == 0:
            continue

        max_i = np.max(intensity_vals)
        threshold = max(max_i - 20, 30)
        voiced_frames = intensity_vals > threshold

        phonation_time = np.sum(voiced_frames) * 0.01
        total_phonation_duration += phonation_time

        last_peak_frame = -min_distance_frames
        for i in range(1, len(intensity_vals) - 1):
            if (
                intensity_vals[i] > threshold
                and intensity_vals[i] > intensity_vals[i - 1]
                and intensity_vals[i] > intensity_vals[i + 1]
                and (i - last_peak_frame) >= min_distance_frames
            ):
                total_syllables += 1
                last_peak_frame = i

    if total_segment_duration > 0:
        internal_pauses = max(0.0, total_segment_duration - total_phonation_duration)
        pause_ratio = internal_pauses / total_segment_duration
    else:
        pause_ratio = 0.0

    if total_phonation_duration > 0:
        speech_rate = total_syllables / total_phonation_duration
    elif total_segment_duration > 0:
        speech_rate = total_syllables / total_segment_duration
    else:
        speech_rate = 0.0

    latencies = [
        s.get("latent_response_time")
        for s in segments_meta
        if s.get("latent_response_time") is not None
    ]
    mean_latency = float(np.mean(latencies)) if latencies else None

    return round(speech_rate, 2), round(pause_ratio, 2), (round(mean_latency, 2) if mean_latency is not None else None)