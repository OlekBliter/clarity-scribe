import pytest
from systems.biomarkers import AcousticBiomarkerService
from systems.biomarkers.exceptions import AudioFileNotFoundError


@pytest.fixture
def service_instance():
    return AcousticBiomarkerService(default_window_sec=15.0)


def test_custom_exception_on_missing_file(service_instance):
    input_payload = {
        "patient_audio_path": "invalid/path/missing.wav",
        "segments": []
    }
    with pytest.raises(AudioFileNotFoundError):
        service_instance.extract_biomarkers(input_payload)
