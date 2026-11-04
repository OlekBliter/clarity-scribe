from .channel_splitter import split
from .vosk_transcription import load_model, recognize_words, create_output_segments, collect_metadata
from .exceptions import AudioTranscriptionError, InvalidAudioError, UnsupportedLanguageError
from src.schemas.contracts import S1Out

REQUIRED_ROLES = {"DOCTOR", "PATIENT"}

class AudioTranscriptionService:
    """
    Transcribe a two-channel recording using a dict -> dict contract.

    Input:
        {
            "audio_path": ...,
            "channel_map": ...,
            "language_hint": ...,
        }

    Output:
        {
            "language": ...,
            "metadata": {
                "audio_duration_sec": ...,
                "doctor_speaking_time_sec": ...,
                "patient_speaking_time_sec": ...,
                "silence_time_sec": ...,
            },
            "segments": [
                {
                    "segment_id": ...,
                    "speaker": ...,
                    "start_time": ...,
                    "end_time": ...,
                    "text": ...,
                    "confidence": ...,
                }
                ...
            ],
        }
    """
    def __init__(self, use_punctuation_model: bool = False):
        self.use_punctuation_model = use_punctuation_model
        self._model = load_model()

    def transcribe(self, input_data: dict) -> dict:
        """
        Transcribe the recording described by the input dictionary.

        The input must contain ``audio_path``, ``channel_map`` and
        ``language_hint``. Recognition runs on the original timeline of each
        channel, so returned timestamps refer to the source recording.
        """
        if not isinstance(input_data, dict):
            raise InvalidAudioError("S1 input must be a dictionary.")

        required_keys = {"audio_path", "channel_map", "language_hint"}
        missing = required_keys - input_data.keys()
        if missing:
            raise InvalidAudioError(
                f"S1 input is missing required keys: {sorted(missing)}"
            )

        audio_path = input_data["audio_path"]
        channel_map = input_data["channel_map"]
        language_hint = input_data["language_hint"]
        if not isinstance(audio_path, str) or not audio_path.strip():
            raise InvalidAudioError("audio_path must be a non-empty string.")
        if not isinstance(channel_map, dict):
            raise InvalidAudioError("channel_map must be a dictionary.")
        if language_hint != "uk":
            raise UnsupportedLanguageError(
                "Only Ukrainian transcription is currently supported."
            )

        missing = REQUIRED_ROLES - channel_map.keys()
        if missing:
            raise InvalidAudioError(f"channel_map must contain {sorted(missing)}")

        try:
            tracks = split(audio_path, channel_map)
            segments_doctor = recognize_words(
                tracks["DOCTOR"], self._model, "DOCTOR", self.use_punctuation_model
            )
            segments_patient = recognize_words(
                tracks["PATIENT"], self._model, "PATIENT", self.use_punctuation_model
            )
        except AudioTranscriptionError:
            raise
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            raise InvalidAudioError("Audio transcription failed.") from error

        segments = create_output_segments(segments_patient, segments_doctor)
        metadata = collect_metadata(segments, tracks["DOCTOR"])

        result = {
            "language": language_hint,
            "metadata": {key: round(value, 2) for key, value in metadata.items()},
            "segments": [vars(segment) for segment in segments],
        }
        try:
            return S1Out.model_validate(result).model_dump()
        except ValueError as error:
            raise AudioTranscriptionError("S1 output failed contract validation.") from error
