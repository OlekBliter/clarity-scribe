"""JSON-колонки SQLite ↔ Pydantic. Решту (статуси, зв'язки) перевіряє Оркестратор."""
from pydantic import TypeAdapter

from .contracts import MedicalCardData, NerMap, S1Metadata, S2Out, S3Out, SoapNote

JSON_COLUMNS: dict[tuple[str, str], TypeAdapter] = {
    ("sessions", "channel_map"): TypeAdapter(dict[str, int]),
    ("sessions", "transcript_meta"): TypeAdapter(S1Metadata),
    ("sessions", "ner_map"): TypeAdapter(NerMap),
    ("biomarkers", "data"): TypeAdapter(S2Out),
    ("medical_cards", "draft"): TypeAdapter(S3Out),
    ("medical_cards", "data"): TypeAdapter(MedicalCardData),
    ("soap_notes", "draft"): TypeAdapter(SoapNote),
    ("soap_notes", "final"): TypeAdapter(SoapNote),
}


def load_column(table: str, column: str, text: str | None):
    """Рядок з БД → модель (None лишається None)."""
    return None if text is None else JSON_COLUMNS[(table, column)].validate_json(text)


def dump_column(table: str, column: str, obj) -> str:
    """Модель (або dict) → валідований JSON-рядок для INSERT/UPDATE."""
    ta = JSON_COLUMNS[(table, column)]
    return ta.dump_json(ta.validate_python(obj)).decode()
