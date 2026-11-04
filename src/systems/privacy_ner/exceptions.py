class NerError(Exception):
    """Base class of every error raised by the NER system."""


class ConfigurationError(NerError):
    """Missing or invalid configuration, such as a model path."""


class InvalidRequestError(NerError):
    """The request does not follow the agreed contract."""


class ModelError(NerError):
    """The model could not be loaded or failed during inference."""
