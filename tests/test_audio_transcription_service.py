from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from pydub import AudioSegment
from systems.audio_transcription import audio_transcription_service as pap_module
from systems.audio_transcription.audio_transcription_service import PatientAudioPipeline

CHANNEL_MAP = {"DOCTOR": 0, "PATIENT": 1}

@pytest.fixture
def mock_deps(monkeypatch):
    """
    Replaces all external dependencies in patient_audio_pipeline
    so that only the logic of the PatientAudioPipeline class is tested.
    """
    # Create fake audio tracks
    fake_doctor_track = MagicMock(spec=AudioSegment)
    fake_patient_track = MagicMock(spec=AudioSegment)
    fake_stitched_track = MagicMock(spec=AudioSegment)
    
    mocks = SimpleNamespace(
        tracks={"DOCTOR": fake_doctor_track, "PATIENT": fake_patient_track},
        stitched=fake_stitched_track,
        timestamps=[{"start": 1.0, "end": 2.0}],
        model=MagicMock(),
        segments=[SimpleNamespace(segment_id=0, speaker="DOCTOR", start_time=0.0, end_time=1.0, text="Привіт", confidence=0.9)],
        metadata={"audio_duration_sec": 10.556, "silence_time_sec": 2.123},
        
        # Functions
        split=MagicMock(),
        get_voice_activity=MagicMock(),
        load_model=MagicMock(),
        recognize_words=MagicMock(),
        create_output_segments=MagicMock(),
        collect_metadata=MagicMock(),
    )

    # Configure return values
    mocks.split.return_value = mocks.tracks
    mocks.get_voice_activity.return_value = (mocks.stitched, mocks.timestamps)
    mocks.load_model.return_value = mocks.model
    mocks.create_output_segments.return_value = mocks.segments
    mocks.collect_metadata.return_value = mocks.metadata

    # Replace the imported names inside the module under test
    monkeypatch.setattr(pap_module, "split", mocks.split)
    monkeypatch.setattr(pap_module, "get_voice_activity", mocks.get_voice_activity)
    monkeypatch.setattr(pap_module, "load_model", mocks.load_model)
    monkeypatch.setattr(pap_module, "recognize_words", mocks.recognize_words)
    monkeypatch.setattr(pap_module, "create_output_segments", mocks.create_output_segments)
    monkeypatch.setattr(pap_module, "collect_metadata", mocks.collect_metadata)

    return mocks


# ------------------------------------------------------------------- _get_tracks

def test_get_tracks_caches_result_and_calls_split_once(mock_deps):
    pipeline = PatientAudioPipeline("fake.wav", CHANNEL_MAP, "uk", "")
    
    tracks1 = pipeline._get_tracks()
    tracks2 = pipeline._get_tracks()
    
    assert tracks1 is tracks2
    mock_deps.split.assert_called_once_with("fake.wav", CHANNEL_MAP)


def test_get_tracks_missing_role_raises_keyerror():
    # PATIENT role is missing
    invalid_map = {"DOCTOR": 0, "NURSE": 1}
    pipeline = PatientAudioPipeline("fake.wav", invalid_map, "uk", "")
    
    with pytest.raises(KeyError, match="PATIENT"):
        pipeline._get_tracks()


# ------------------------------------------------------------- get_patient_audio

def test_get_patient_audio_returns_stitched_track(mock_deps):
    pipeline = PatientAudioPipeline("fake.wav", CHANNEL_MAP, "uk", "")
    result = pipeline.get_patient_audio()
    
    assert result is mock_deps.stitched
    mock_deps.get_voice_activity.assert_called_once_with(mock_deps.tracks["PATIENT"])
    # export must not be called because patient_audio_out is empty
    mock_deps.stitched.export.assert_not_called()


def test_get_patient_audio_saves_file_if_path_provided(mock_deps, tmp_path):
    out_file = tmp_path / "audio" / "patient_out.wav"
    pipeline = PatientAudioPipeline("fake.wav", CHANNEL_MAP, "uk", str(out_file))
    
    pipeline.get_patient_audio()
    
    assert out_file.parent.exists()  # the output folder must have been created
    mock_deps.stitched.export.assert_called_once_with(str(out_file), format="wav")


def test_get_patient_audio_bubbles_up_vad_error(mock_deps):
    mock_deps.get_voice_activity.side_effect = ValueError("No patient speech")
    pipeline = PatientAudioPipeline("fake.wav", CHANNEL_MAP, "uk", "")
    
    with pytest.raises(ValueError, match="No patient speech"):
        pipeline.get_patient_audio()


# ------------------------------------------------------ get_transcription_result

def test_get_transcription_result_structure_and_rounding(mock_deps):
    pipeline = PatientAudioPipeline("fake.wav", CHANNEL_MAP, "uk", "")
    
    result = pipeline.get_transcription_result()
    
    # 1. Check calls to the dependencies
    mock_deps.load_model.assert_called_once()
    assert mock_deps.recognize_words.call_count == 2
    mock_deps.create_output_segments.assert_called_once()
    mock_deps.collect_metadata.assert_called_once_with(mock_deps.segments, mock_deps.tracks["DOCTOR"])

    # 2. Check the format of the returned dict
    assert result["language"] == "uk"
    
    # Metadata values must be rounded to 2 decimal places
    assert result["metadata"] == {
        "audio_duration_sec": 10.56,  # 10.556 -> 10.56
        "silence_time_sec": 2.12      # 2.123 -> 2.12
    }
    
    # Segments must be converted to plain dicts via vars()
    assert result["segments"] == [{"segment_id": 0, "speaker": "DOCTOR", "start_time": 0.0, "end_time": 1.0, "text": "Привіт", "confidence": 0.9}]