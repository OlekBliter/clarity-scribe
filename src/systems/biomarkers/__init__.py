from .exceptions import (
    AcousticBiomarkerError,
    AudioFileNotFoundError,
    AudioProcessingError,
    InvalidSegmentError,
)

__all__ = [
    "AcousticBiomarkerService",
    "AcousticBiomarkerError",
    "AudioFileNotFoundError",
    "AudioProcessingError",
    "InvalidSegmentError",
]


def __getattr__(name):
    if name == "AcousticBiomarkerService":
        from .acoustic_biomarker_service import AcousticBiomarkerService
        return AcousticBiomarkerService
    raise AttributeError(name)
