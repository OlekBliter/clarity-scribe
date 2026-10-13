from pathlib import Path
from pydub import AudioSegment
from channel_splitter import split
from speech_filter import get_voice_activity 
from vosk_transcription import load_model, recognize_words, create_output_segments, collect_metadata

class PatientAudioPipeline:
    """
    Processes one S1 request (see the S1.in / S1.out contract).

    Method 1, get_patient_audio():    the patient's speech with silence and noise cut out.
    Method 2, get_transcription_result(): everything else in S1.out
                                      (language, metadata, segments).

    The recording is decoded and split into channels only once; both methods
    share the same per-speaker tracks.
    """
    def __init__(self, audio_path: str, channel_map: dict[str, int], language_hint: str, patient_audio_out: str):
        self.audio_path = audio_path
        self.channel_map = channel_map
        self.language_hint = language_hint
        self.patient_audio_out = patient_audio_out
        self._tracks: dict[str, AudioSegment] | None = None

    def _get_tracks(self) -> dict[str, AudioSegment]:
        """Split the recording once and cache the mono 16 kHz track of each role."""
        if self._tracks is None:
            missing = {"DOCTOR", "PATIENT"} - self.channel_map.keys()
            if missing:
                raise KeyError(f"channel_map must contain {sorted(missing)}")
            self._tracks = split(self.audio_path, self.channel_map)
        return self._tracks

    def get_patient_audio(self) -> AudioSegment:
        """
        Return the patient's track with everything except speech removed
        (silence, noise, artifacts), glued into one continuous clip.

        If patient_audio_out was given, the result is also saved there as WAV.

        Raises:
            ValueError: If the VAD finds no patient speech.
        """
        patient_track = self._get_tracks()["PATIENT"]
        stitched, _timestamps = get_voice_activity(patient_track)

        if self.patient_audio_out:
            out_path = Path(self.patient_audio_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            stitched.export(str(out_path), format="wav")

        return stitched

    def get_transcription_result(self) -> dict:
        """
        Transcribe both speakers and return the rest of S1.out:
        {"language": ..., "metadata": {...}, "segments": [...]}.

        Recognition runs on the ORIGINAL tracks (not the VAD-stitched one),
        so start_time / end_time match the real recording timeline.
        """
        tracks = self._get_tracks()
        model = load_model()

        segments_doctor = recognize_words(tracks["DOCTOR"], model, "DOCTOR")
        segments_patient = recognize_words(tracks["PATIENT"], model, "PATIENT")

        segments = create_output_segments(segments_patient, segments_doctor)
        metadata = collect_metadata(segments, tracks["DOCTOR"])

        return {
            "language": self.language_hint,
            "metadata": {key: round(value, 2) for key, value in metadata.items()},
            "segments": [vars(segment) for segment in segments],
        }