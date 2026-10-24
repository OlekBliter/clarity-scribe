import parselmouth
from parselmouth.praat import call
import numpy as np
from typing import List, Dict, Any
from .exceptions import AcousticBiomarkerError, AudioProcessingError

def analyze_segment_pitch_and_quality(sound_segment: parselmouth.Sound) -> Dict[str, Any]:
    """
    Extracts acoustic pitch and voice quality metrics for a single patient speech segment.

    Args:
        sound_segment: Parselmouth Sound object containing segment audio.

    Returns:
        Dict containing voiced frame count, F0 statistics, jitter, shimmer, and HNR.
    """
    if sound_segment.duration < 0.05:
        return {"n_voiced": 0}

    try:
        pitch = sound_segment.to_pitch(time_step=0.01)
        f0_values = pitch.selected_array['frequency']
        f0_voiced = f0_values[f0_values > 0]
        n_voiced = len(f0_voiced)

        if n_voiced < 3:
            return {"n_voiced": 0}

        f0_mean = float(np.mean(f0_voiced))
        f0_sd_hz = float(np.std(f0_voiced))

        median_f0 = np.median(f0_voiced)
        if median_f0 > 0:
            st_values = 12 * np.log2(f0_voiced / median_f0)
            f0_sd_st = float(np.std(st_values))
        else:
            f0_sd_st = 0.0

        jitter_val, shimmer_val = 0.0, 0.0
        point_process = call(sound_segment, "To PointProcess (periodic, cc)", 75, 500)
        if call(point_process, "Get number of points") > 3:
            j = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100.0
            s = call([sound_segment, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6) * 100.0
            if not np.isnan(j):
                jitter_val = float(j)
            if not np.isnan(s):
                shimmer_val = float(s)

        hnr_val = 0.0
        harmonicity = sound_segment.to_harmonicity()
        h = call(harmonicity, "Get mean", 0, 0)
        if not np.isnan(h):
            hnr_val = float(h)

        return {
            "n_voiced": n_voiced,
            "f0_mean_hz": f0_mean,
            "f0_sd_hz": f0_sd_hz,
            "f0_sd_st": f0_sd_st,
            "jitter": jitter_val,
            "shimmer": shimmer_val,
            "hnr": hnr_val
        }
    except Exception as e:
        raise AudioProcessingError(f"Failed to extract pitch and voice quality: {e}") from e


def aggregate_segment_dsp(segment_results: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Aggregates per-segment DSP metrics weighted by the number of voiced frames.

    Args:
        segment_results: List of DSP metric dicts per segment.

    Returns:
        Dict containing aggregated raw DSP features.
    """
    valid = [r for r in segment_results if r.get("n_voiced", 0) > 0]
    if not valid:
        return {
            "f0_mean_hz": 0.0,
            "f0_variability_sd": 0.0,
            "f0_sd_st": 0.0,
            "jitter_percent": 0.0,
            "shimmer_percent": 0.0,
            "hnr_db": 0.0
        }

    weights = np.array([r["n_voiced"] for r in valid], dtype=float)
    total_w = np.sum(weights)

    # 1. Mean of F0 (no changes)
    f0_mean = float(np.sum(np.array([r["f0_mean_hz"] for r in valid]) * weights) / total_w)
    # 2. Correct SD for F0 (Hz) using pooled variance
    # Σ n_i * (σ_i² + (μ_i − μ)²) / N
    variances_hz = [
        w * (r["f0_sd_hz"] ** 2 + (r["f0_mean_hz"] - f0_mean) ** 2)
        for r, w in zip(valid, weights)
    ]
    f0_sd_hz = float(np.sqrt(np.sum(variances_hz) / total_w))

    # 3. For ST mean within-segment variability SD,
    # since semitones are calculated relative to the median of each individual segment.
    f0_sd_st = float(np.sum(np.array([r["f0_sd_st"] for r in valid]) * weights) / total_w)
    jitter = float(np.sum(np.array([r["jitter"] for r in valid]) * weights) / total_w)
    shimmer = float(np.sum(np.array([r["shimmer"] for r in valid]) * weights) / total_w)
    hnr = float(np.sum(np.array([r["hnr"] for r in valid]) * weights) / total_w)

    return {
        "f0_mean_hz": round(f0_mean, 2),
        "f0_variability_sd": round(f0_sd_hz, 2),
        "f0_sd_st": round(f0_sd_st, 2),
        "jitter_percent": round(jitter, 2),
        "shimmer_percent": round(shimmer, 2),
        "hnr_db": round(hnr, 2)
    }
