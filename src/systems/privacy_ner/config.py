import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .models import EntityType

# Zero-shot labels sent to GLiNER and the entity type each one means.
GLINER_LABELS = {
    "person": EntityType.PERSON, "людина": EntityType.PERSON, "пацієнт": EntityType.PERSON,
    "лікар": EntityType.PERSON, "ім'я та прізвище": EntityType.PERSON, "ім'я": EntityType.PERSON,
    "прізвище": EntityType.PERSON, "surname": EntityType.PERSON,
    "address": EntityType.ADDRESS, "адреса": EntityType.ADDRESS, "street address": EntityType.ADDRESS,
    "місто": EntityType.ADDRESS, "населений пункт": EntityType.ADDRESS, "вулиця": EntityType.ADDRESS,
    "street": EntityType.ADDRESS, "адреса проживання": EntityType.ADDRESS,
    "organization": EntityType.ORG, "організація": EntityType.ORG, "компанія": EntityType.ORG,
    "лікарня": EntityType.ORG, "медичний заклад": EntityType.ORG, "місце роботи": EntityType.ORG,
}

# Latin tags
TAG_PREFIXES = {
    EntityType.PERSON: "PER", EntityType.ADDRESS: "LOC", EntityType.ORG: "ORG",
    EntityType.PHONE: "TEL", EntityType.EMAIL: "MAIL", EntityType.BIRTH_DATE: "DOB",
    EntityType.OTHER_ID: "ID",
}

# Kinship and role words stay visible
KEEP_WORDS = (
    "мама", "мати", "тато", "батько", "баба", "бабуся", "дід", "дідусь", "брат", "сестра", "син",
    "донька", "чоловік", "дружина", "тітка", "дядько", "кум", "кума", "друг", "подруга", "колега",
    "сусід", "сусідка", "лікар", "лікарка",
)

IGNORE_WORDS = ("центр", "телефон", "вулиця", "пошта", "компанія", "організація", "лікарня", "клініка")

# Local GLiNER weights live next to the other models: <project root>/models/gliner_multi-v2.1.
# The location is set by GLINER_MODEL_DIR (see .env.example); the default matches the example value.
DEFAULT_GLINER_DIR = os.path.join("models", "gliner_multi-v2.1")


def _model_dir_from_env() -> str:
    load_dotenv()  # reads .env if present; real environment variables take precedence
    return os.environ.get("GLINER_MODEL_DIR") or DEFAULT_GLINER_DIR


@dataclass(frozen=True)
class NerConfig:
    gliner_model: str = field(default_factory=_model_dir_from_env)
    gliner_threshold: float = 0.15
    window_words: int = 100
    window_overlap: int = 20
    min_word_len: int = 3
    gliner_labels: dict = field(default_factory=lambda: dict(GLINER_LABELS))
    tag_prefixes: dict = field(default_factory=lambda: dict(TAG_PREFIXES))
    keep_words: tuple = KEEP_WORDS
    ignore_words: tuple = IGNORE_WORDS