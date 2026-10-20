from dataclasses import dataclass
from enum import Enum


class NerError(Exception):
    """Base class of every error raised by the NER system."""


class ConfigurationError(NerError):
    """Missing or invalid configuration (for example, no model path)."""


class InvalidRequestError(NerError):
    """The request does not follow the agreed contract."""


class EntityType(str, Enum):
    PERSON = "PERSON"
    ADDRESS = "ADDRESS"
    ORG = "ORG"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    BIRTH_DATE = "BIRTH_DATE"
    OTHER_ID = "OTHER_ID"

    @property
    def is_named(self) -> bool:
        """Names, places and organisations are inflected, so their forms must be grouped."""
        return self in (EntityType.PERSON, EntityType.ADDRESS, EntityType.ORG)


@dataclass(frozen=True)
class Span:
    """A detected range [start, end); on overlap the higher priority decides the type."""

    start: int
    end: int
    entity_type: EntityType
    priority: int = 0


@dataclass(frozen=True)
class TagMask:
    """A range [start, end) replaced by ``tag`` in the output text."""

    start: int
    end: int
    tag: str


@dataclass
class Entity:
    """One real-world entity; ``original`` is its most complete mention."""

    tag: str
    type: EntityType
    original: str