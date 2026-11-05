class AudioTranscriptionError(Exception):
    """Base exception for audio transcription failures."""


class InvalidAudioError(AudioTranscriptionError):
    """Raised when audio input is missing, invalid, or cannot be decoded."""


class UnsupportedLanguageError(AudioTranscriptionError):
    """Raised when the requested transcription language is unsupported."""


class ModelNotFoundError(AudioTranscriptionError):
    """Raised when the configured Vosk model cannot be found or loaded."""
