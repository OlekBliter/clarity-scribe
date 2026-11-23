from .exceptions import (
    AudioTranscriptionError,
    InvalidAudioError,
    ModelNotFoundError,
    UnsupportedLanguageError,
)

__all__ = [
    "AudioTranscriptionService",
    "AudioTranscriptionError",
    "InvalidAudioError",
    "ModelNotFoundError",
    "UnsupportedLanguageError",
]


def __getattr__(name):
    if name == "AudioTranscriptionService":
        from .audio_transcription_service import AudioTranscriptionService
        return AudioTranscriptionService
    raise AttributeError(name)
