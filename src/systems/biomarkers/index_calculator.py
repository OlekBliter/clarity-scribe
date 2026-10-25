from typing import Dict, Any
from .exceptions import AcousticBiomarkerError

def compute_inferred_indices(raw_dsp: Dict[str, Any], f0_sd_st: float, f0_sd_hz_within: float) -> Dict[str, Any]:
    """
    Computes clinical psychomotor indices and affect indicators from raw acoustic features.

    Args:
        raw_dsp: Dictionary containing calculated raw DSP metrics.
        f0_sd_st: Within-segment standard deviation of F0 in semitones relative to median.
        f0_sd_hz_within: Within-segment standard deviation of F0 in Hz, used as a fallback threshold.

    Returns:
        Dict containing calculated indices and flags (affect_flatness_flag, vocal_jitter_percentile, psychomotor_retardation_index).
    """
    f0_sd_hz = raw_dsp["f0_variability_sd"]
    jitter = raw_dsp["jitter_percent"]
    pause_ratio = raw_dsp["pause_ratio"]
    latency = raw_dsp["mean_latent_response_time_sec"]
    speech_rate = raw_dsp["speech_rate_syllables_per_sec"]

    # both branches use within data
    affect_flatness = bool(f0_sd_st < 1.5 if f0_sd_st > 0 else f0_sd_hz_within < 12.0)

    jitter_scale = min(max((jitter - 0.5) / (3.0 - 0.5) * 100.0, 0.0), 100.0)

    score_pauses = min(pause_ratio / 0.4, 1.0)
    score_tempo = 1.0 - min(speech_rate / 4.5, 1.0)

    if latency is not None:
        score_latency = min(latency / 3.0, 1.0)
        retardation_index = (score_pauses * 0.4) + (score_latency * 0.4) + (score_tempo * 0.2)
    else:
        retardation_index = (score_pauses * 0.65) + (score_tempo * 0.35)

    return {
        "affect_flatness_flag": affect_flatness,
        "vocal_jitter_percentile": round(jitter_scale, 1),
        "psychomotor_retardation_index": round(retardation_index, 2)
    }