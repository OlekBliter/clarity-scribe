from pathlib import Path
from pydub import AudioSegment
from .channel_splitter import split
from .speech_filter import get_voice_activity 
from .vosk_transcription import load_model, recognize_words, create_output_segments, collect_metadata

REQUIRED_ROLES = {"DOCTOR", "PATIENT"}

class PatientAudioPipeline:
    """
    Reusable pipeline: one instance can process any number of recordings.

    Usage:
        pipeline = PatientAudioPipeline(language_hint="uk")
        tracks = pipeline.load_tracks("a.wav", {"PATIENT": 0, "DOCTOR": 1})
        audio = pipeline.get_patient_audio(tracks, out_path="a_patient.wav")
        result = pipeline.get_transcription_result(tracks)

    The recording is decoded and split into channels once (load_tracks);
    both processing methods then work on the same per-speaker tracks.
    """
    def __init__(self, language_hint: str):
        self.language_hint = language_hint
        self._model = load_model()

    def load_tracks(self, audio_path: str, channel_map: dict[str, int]) -> dict[str, AudioSegment]:
        """
        Split the recording and return the mono 16 kHz track of each role.

        Raises:
            KeyError: If channel_map lacks the DOCTOR or PATIENT role.
        """
        missing = REQUIRED_ROLES - channel_map.keys()
        if missing:
            raise KeyError(f"channel_map must contain {sorted(missing)}")
        return split(audio_path, channel_map)

    def get_patient_audio(self, tracks: dict[str, AudioSegment], out_path: str | None = None) -> AudioSegment:
        """
        Return the patient's track with everything except speech removed
        (silence, noise, artifacts), glued into one continuous clip.

        If out_path is given, the result is also saved there as WAV.

        Raises:
            ValueError: If the VAD finds no patient speech.
        """
        stitched, _timestamps = get_voice_activity(tracks["PATIENT"])

        if out_path:
            path = Path(out_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            stitched.export(str(path), format="wav")

        return stitched

    def get_transcription_result(self, tracks: dict[str, AudioSegment]) -> dict:
        """
        Transcribe both speakers:
        {"language": ..., "metadata": {...}, "segments": [...]}.

        Recognition runs on the ORIGINAL tracks (not the VAD-stitched one),
        so start_time / end_time match the real recording timeline.
        """
        segments_doctor = recognize_words(tracks["DOCTOR"], self._model, "DOCTOR")
        segments_patient = recognize_words(tracks["PATIENT"], self._model, "PATIENT")

        segments = create_output_segments(segments_patient, segments_doctor)
        metadata = collect_metadata(segments, tracks["DOCTOR"])

        return {
            "language": self.language_hint,
            "metadata": {key: round(value, 2) for key, value in metadata.items()},
            "segments": [vars(segment) for segment in segments],
        }