from .config import NerConfig
from .exceptions import (
    ConfigurationError,
    InvalidRequestError,
    ModelError,
    NerError,
)

__all__ = [
    "NerConfig",
    "NerError",
    "ConfigurationError",
    "InvalidRequestError",
    "ModelError",
    "PrivacyNerService",
]


def __getattr__(name):
    if name == "PrivacyNerService":
        from .ner_service import PrivacyNerService
        return PrivacyNerService
    raise AttributeError(name)
