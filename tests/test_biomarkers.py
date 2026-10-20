import os
import pytest
from pydantic import BaseModel, Field
from typing import List, Optional

from src.biomarkers.acoustic_biomarker_service import AcousticBiomarkerService
from src.biomarkers.exceptions import AudioFileNotFoundError


# --- Test Contract Schemas ---
class PatientSegmentSchema(BaseModel):
    segment_id: int
    start_time: float
    end_time: float
    latent_response_time: Optional[float] = None


class InputContractSchema(BaseModel):
    patient_audio_path: str
    segments: List[PatientSegmentSchema]


class OutputContractSchema(BaseModel):
    raw_dsp_features: dict
    inferred_indices: dict
    intrasession_dynamics: dict
    window_chunks: list


# --- Tests ---
@pytest.fixture
def service_instance():
    return AcousticBiomarkerService(default_window_sec=15.0)


def test_service_execution_and_schema_validation(service_instance):
    test_audio = "mock_data/testing_audio.wav"
    if not os.path.exists(test_audio):
        pytest.skip("Audio fixture not available.")

    input_payload = InputContractSchema(
        patient_audio_path=test_audio,
        segments=[
            PatientSegmentSchema(segment_id=0, start_time=1.5, end_time=13.0, latent_response_time=1.2),
            PatientSegmentSchema(segment_id=1, start_time=16.0, end_time=28.0, latent_response_time=0.9),
            PatientSegmentSchema(segment_id=2, start_time=31.0, end_time=43.0, latent_response_time=1.1),
            PatientSegmentSchema(segment_id=3, start_time=45.5, end_time=53.5, latent_response_time=0.8),
        ]
    ).model_dump()

    # Call service class method
    output_dict = service_instance.extract_biomarkers(input_payload)

    # Validate output contract using Pydantic in tests
    validated_output = OutputContractSchema(**output_dict)
    assert validated_output.raw_dsp_features["f0_mean_hz"] > 0
    assert 0.0 <= validated_output.inferred_indices["psychomotor_retardation_index"] <= 1.0


def test_custom_exception_on_missing_file(service_instance):
    input_payload = {
        "patient_audio_path": "invalid/path/missing.wav",
        "segments": []
    }
    with pytest.raises(AudioFileNotFoundError):
        service_instance.extract_biomarkers(input_payload)