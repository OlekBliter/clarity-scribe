"""SQLite JSON columns ↔ Pydantic. The rest (statuses, relationships) is verified by the Orchestrator."""
from pydantic import TypeAdapter

from .contracts import MedicalCardData, NerMap, S1Metadata, S2Out, S3Out, S4Out

JSON_COLUMNS: dict[tuple[str, str], TypeAdapter] = {
    ("sessions", "channel_map"): TypeAdapter(dict[str, int]),
    ("sessions", "transcript_meta"): TypeAdapter(S1Metadata),
    ("sessions", "ner_map"): TypeAdapter(NerMap),
    ("biomarkers", "data"): TypeAdapter(S2Out),
    ("medical_cards", "draft"): TypeAdapter(S3Out),
    ("medical_cards", "data"): TypeAdapter(MedicalCardData),
    ("soap_notes", "draft"): TypeAdapter(S4Out),
    ("soap_notes", "final"): TypeAdapter(S4Out),
}


def load_column(table: str, column: str, text: str | None):
    """DB row → model (None remains None)."""
    return None if text is None else JSON_COLUMNS[(table, column)].validate_json(text)


def dump_column(table: str, column: str, obj) -> str:
    """Model (or dict) → validated JSON string for INSERT/UPDATE."""
    ta = JSON_COLUMNS[(table, column)]
    return ta.dump_json(ta.validate_python(obj)).decode()