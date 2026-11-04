class ClinicalEngineError(Exception):
    """Base exception for clinical engine failures."""


class ConfigurationError(ClinicalEngineError):
    """Raised when the clinical engine is not configured correctly."""


class LLMRequestError(ClinicalEngineError):
    """Raised when an LLM request fails after retries."""


class LLMResponseError(ClinicalEngineError):
    """Raised when an LLM response cannot be parsed or validated."""
