class AcousticBiomarkerError(Exception):
    """Base exception for the acoustic biomarkers domain module."""
    pass


class AudioFileNotFoundError(AcousticBiomarkerError):
    """Raised when the specified patient audio file does not exist or is unreadable."""
    pass


class AudioProcessingError(AcousticBiomarkerError):
    """Raised when Praat/Parselmouth fails to process the audio signal."""
    pass


class InvalidSegmentError(AcousticBiomarkerError):
    """Raised when segment timestamps are invalid or logically corrupted."""
    pass
