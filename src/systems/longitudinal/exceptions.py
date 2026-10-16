class LongitudinalError(Exception):
    """Base exception for all errors in the longitudinal dynamics module."""
    pass


class InvalidVisitPayloadError(LongitudinalError):
    """Raised when the input visits payload is malformed or has an invalid type."""
    pass


class MissingSessionNumberError(LongitudinalError):
    """Raised when a visit dictionary is missing a valid integer 'session_number'."""
    pass


class TrendCalculationError(LongitudinalError):
    """Raised when regression or mathematical trend calculation fails."""
    pass