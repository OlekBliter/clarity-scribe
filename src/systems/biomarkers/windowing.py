import parselmouth
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from scipy.stats import theilslopes
from src.biomarkers.dsp_pitch_quality import analyze_segment_pitch_and_quality, aggregate_segment_dsp
from src.biomarkers.dsp_tempo_pauses import analyze_speech_tempo_and_internal_pauses


def analyze_windows_and_dynamics(
    sound_mono: parselmouth.Sound,
    segments_meta: List[Dict[str, Any]],
    total_duration_sec: float,
    window_sec: Optional[float] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Splits audio into temporal windows and evaluates intrasession trend dynamics.

    Args:
        sound_mono: Parselmouth mono Sound object.
        segments_meta: List of raw segment dictionaries.
        total_duration_sec: Total duration of audio file in seconds.
        window_sec: Optional window duration in seconds.

    Returns:
        Tuple of (window_chunks_list, dynamics_dict).
    """
    if window_sec is None:
        window_sec = 300.0 if total_duration_sec >= 1200.0 else 180.0

    chunks: List[Dict[str, Any]] = []
    num_windows = int(np.ceil(total_duration_sec / window_sec)) if total_duration_sec > 0 else 0

    for i in range(num_windows):
        w_start = i * window_sec
        w_end = min((i + 1) * window_sec, total_duration_sec)
        if w_end - w_start < 1.0:
            continue

        w_sounds = []
        w_seg_results = []
        w_meta = []

        for seg in segments_meta:
            overlap_start = max(seg["start_time"], w_start)
            overlap_end = min(seg["end_time"], w_end)

            if overlap_end - overlap_start > 0.05:
                part = sound_mono.extract_part(from_time=overlap_start, to_time=overlap_end)
                w_sounds.append(part)
                w_seg_results.append(analyze_segment_pitch_and_quality(part))
                w_meta.append(seg)

        if w_sounds:
            dsp_agg = aggregate_segment_dsp(w_seg_results)
            sp_rate, p_ratio, _ = analyze_speech_tempo_and_internal_pauses(w_sounds, w_meta)
            f0_sd = dsp_agg["f0_variability_sd"]
        else:
            f0_sd, sp_rate, p_ratio = 0.0, 0.0, 0.0

        chunks.append({
            "window_index": i,
            "time_range": f"{int(w_start//60):02d}:{int(w_start%60):02d}-{int(w_end//60):02d}:{int(w_end%60):02d}",
            "f0_variability_sd": f0_sd,
            "speech_rate_syllables_per_sec": sp_rate,
            "pause_ratio": p_ratio
        })

    valid_chunks = [c for c in chunks if c["f0_variability_sd"] > 0 or c["speech_rate_syllables_per_sec"] > 0]
    n_valid = len(valid_chunks)

    if n_valid >= 2:
        f0_series = [c["f0_variability_sd"] for c in valid_chunks]
        tempo_series = [c["speech_rate_syllables_per_sec"] for c in valid_chunks]
        pause_series = [c["pause_ratio"] for c in valid_chunks]

        x = np.arange(n_valid)
        f0_slope = float(theilslopes(f0_series, x).slope)
        sp_slope = float(theilslopes(tempo_series, x).slope)
        pause_slope = float(theilslopes(pause_series, x).slope)

        f0_change = ((f0_series[-1] - f0_series[0]) / max(f0_series[0], 1.0)) * 100.0
        sp_change = ((tempo_series[-1] - tempo_series[0]) / max(tempo_series[0], 0.5)) * 100.0
        p_change = ((pause_series[-1] - pause_series[0]) / max(pause_series[0], 0.05)) * 100.0

        if sp_slope > 0.05 or f0_slope > 0.5 or pause_slope < -0.05:
            summary = "activation"
        elif sp_slope < -0.05 or f0_slope < -0.5 or pause_slope > 0.05:
            summary = "deceleration"
        else:
            summary = "stable"
    else:
        f0_change, sp_change, p_change = 0.0, 0.0, 0.0
        summary = "insufficient_data"

    dynamics = {
        "f0_variability_change_percent": round(f0_change, 1),
        "speech_rate_change_percent": round(sp_change, 1),
        "pause_ratio_change_percent": round(p_change, 1),
        "trend_summary": summary
    }

    return chunks, dynamics