from typing import List, Optional
from pydantic import BaseModel, Field


# --- S2.in ---
class PatientSegmentInput(BaseModel):
    segment_id: int
    start_time: float
    end_time: float
    latent_response_time: Optional[float] = None


class BiomarkersInput(BaseModel):
    patient_audio_path: str
    segments: List[PatientSegmentInput]


# --- S2.out ---
class RawDSPFeatures(BaseModel):
    f0_variability_sd: float
    f0_mean_hz: float
    jitter_percent: float
    shimmer_percent: float
    hnr_db: float
    speech_rate_syllables_per_sec: float
    pause_ratio: float
    mean_latent_response_time_sec: Optional[float] = None


class InferredIndices(BaseModel):
    affect_flatness_flag: bool
    vocal_jitter_percentile: float
    psychomotor_retardation_index: float


class WindowChunk(BaseModel):
    window_index: int
    time_range: str
    f0_variability_sd: float
    speech_rate_syllables_per_sec: float
    pause_ratio: float


class IntrasessionDynamics(BaseModel):
    f0_variability_change_percent: float
    speech_rate_change_percent: float
    pause_ratio_change_percent: float
    trend_summary: str


class BiomarkersOutput(BaseModel):
    raw_dsp_features: RawDSPFeatures
    inferred_indices: InferredIndices
    intrasession_dynamics: IntrasessionDynamics
    window_chunks: List[WindowChunk]