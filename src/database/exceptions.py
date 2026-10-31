class DatabaseError(Exception):
    """Base exception for database and persistence failures."""


class RepositoryError(DatabaseError):
    """Raised when a repository operation cannot be completed."""


class RecordNotFoundError(RepositoryError):
    """Raised when a requested database record does not exist."""


class UserInputError(RepositoryError):
    """Raised when user-provided data violates a repository rule."""