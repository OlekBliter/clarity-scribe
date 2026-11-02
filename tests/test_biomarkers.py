import pytest
from unittest.mock import MagicMock

from src.systems.biomarkers import AcousticBiomarkerService
from src.systems.biomarkers import acoustic_biomarker_service as biomarker_module
from src.systems.biomarkers.exceptions import (
    AudioFileNotFoundError,
    AudioProcessingError,
    InvalidSegmentError,
)
from src.schemas.contracts import S2Out


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


def test_extract_biomarkers_returns_s2out_shape(service_instance, monkeypatch, tmp_path):
    audio_path = tmp_path / "patient.wav"
    audio_path.touch()

    sound = MagicMock(n_channels=1, duration=20.0)
    segment = MagicMock()
    monkeypatch.setattr(biomarker_module.parselmouth, "Sound", lambda _: sound)
    sound.extract_part.return_value = segment
    monkeypatch.setattr(
        biomarker_module,
        "analyze_segment_pitch_and_quality",
        lambda _: {"n_voiced": 10},
    )
    monkeypatch.setattr(
        biomarker_module,
        "aggregate_segment_dsp",
        lambda _: {
            "f0_mean_hz": 185.2,
            "f0_variability_sd": 7.2,
            "f0_sd_st": 2.0,
            "f0_sd_hz_within": 14.0,
            "jitter_percent": 1.45,
            "shimmer_percent": 4.12,
            "hnr_db": 16.8,
        },
    )
    monkeypatch.setattr(
        biomarker_module,
        "analyze_speech_tempo_and_internal_pauses",
        lambda *_: (2.6, 0.32, 1.68),
    )
    monkeypatch.setattr(
        biomarker_module,
        "compute_inferred_indices",
        lambda *_: {
            "affect_flatness_flag": False,
            "vocal_jitter_percentile": 38.0,
            "psychomotor_retardation_index": 0.42,
        },
    )
    monkeypatch.setattr(
        biomarker_module,
        "analyze_windows_and_dynamics",
        lambda *_args, **_kwargs: (
            [{
                "window_index": 0,
                "time_range": "00:00-00:15",
                "f0_variability_sd": 7.2,
                "speech_rate_syllables_per_sec": 2.6,
                "pause_ratio": 0.32,
            }],
            {
                "f0_variability_change_percent": 0.0,
                "speech_rate_change_percent": 0.0,
                "pause_ratio_change_percent": 0.0,
                "trend_summary": "insufficient_data",
            },
        ),
    )

    result = service_instance.extract_biomarkers({
        "patient_audio_path": str(audio_path),
        "segments": [{"start_time": 0.0, "end_time": 1.0}],
    })

    assert S2Out.model_validate(result).inferred_indices.intrasession_dynamics is not None
    assert "intrasession_dynamics" not in result


def test_extract_biomarkers_rejects_audio_without_voiced_material(
    service_instance, monkeypatch, tmp_path
):
    audio_path = tmp_path / "patient.wav"
    audio_path.touch()

    sound = MagicMock(n_channels=1, duration=20.0)
    monkeypatch.setattr(biomarker_module.parselmouth, "Sound", lambda _: sound)
    sound.extract_part.return_value = MagicMock()
    monkeypatch.setattr(
        biomarker_module,
        "analyze_segment_pitch_and_quality",
        lambda _: {"n_voiced": 0},
    )

    with pytest.raises(AudioProcessingError, match="No valid voiced material"):
        service_instance.extract_biomarkers({
            "patient_audio_path": str(audio_path),
            "segments": [{"start_time": 0.0, "end_time": 1.0}],
        })


def test_extract_biomarkers_rejects_invalid_segment_timestamps(
    service_instance, monkeypatch, tmp_path
):
    audio_path = tmp_path / "patient.wav"
    audio_path.touch()
    sound = MagicMock(n_channels=1, duration=20.0)
    monkeypatch.setattr(biomarker_module.parselmouth, "Sound", lambda _: sound)

    with pytest.raises(InvalidSegmentError):
        service_instance.extract_biomarkers({
            "patient_audio_path": str(audio_path),
            "segments": [{"start_time": 19.0, "end_time": 21.0}],
        })
