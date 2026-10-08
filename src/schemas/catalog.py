"""Каталог полів медкартки (контракти, розділ 6)."""
from enum import Enum


class FieldType(str, Enum):
    TEXT = "text"
    BOOL = "bool"
    DATE = "date"
    ENUM = "enum"


# filled_by = M — заповнює модель (S3). Рівно ці 22 поля мають бути у відповіді S3.
MODEL_FIELDS: dict[str, FieldType] = {
    "request.complaint": FieldType.TEXT,
    "request.onset": FieldType.TEXT,
    "request.why_now": FieldType.TEXT,
    "history.similar_before": FieldType.TEXT,
    "history.prior_therapy": FieldType.TEXT,
    "history.helpful_or_not": FieldType.TEXT,
    "history.on_medication": FieldType.BOOL,
    "history.medications_list": FieldType.TEXT,
    "safety.suicidal_past": FieldType.BOOL,
    "safety.suicidal_now": FieldType.BOOL,
    "safety.details": FieldType.TEXT,
    "context.work_study": FieldType.TEXT,
    "context.relationships_family": FieldType.TEXT,
    "context.life_changes_year": FieldType.TEXT,
    "context.social_support": FieldType.TEXT,
    "substance.alcohol": FieldType.TEXT,
    "substance.cannabis": FieldType.TEXT,
    "substance.other": FieldType.TEXT,
    "resources.coping": FieldType.TEXT,
    "resources.strengths": FieldType.TEXT,
    "goals.change": FieldType.TEXT,
    "goals.success_criteria": FieldType.TEXT,
}

# filled_by = D, але зберігаються в medical_cards.data
DOCTOR_CARD_FIELDS: dict[str, FieldType] = {
    "scales.phq9": FieldType.TEXT,
    "scales.gad7": FieldType.TEXT,
    "scales.other": FieldType.TEXT,
    "hypotheses.notes": FieldType.TEXT,
    "hypotheses.risk": FieldType.ENUM,  # low / moderate / high
    "agreements.format": FieldType.TEXT,
    "agreements.frequency": FieldType.TEXT,
    "agreements.cost": FieldType.TEXT,
    "agreements.initial_goals": FieldType.TEXT,
}

# filled_by = D, зберігаються КОЛОНКАМИ patients; через S3 і NER не проходять
PATIENT_COLUMN_FIELDS: dict[str, FieldType] = {
    "contact.preferred_name": FieldType.TEXT,
    "contact.birth_date": FieldType.DATE,
    "contact.phone": FieldType.TEXT,
    "contact.email": FieldType.TEXT,
    "contact.preferred_channel": FieldType.TEXT,
    "emergency.name": FieldType.TEXT,
    "emergency.relation": FieldType.TEXT,
    "emergency.phone": FieldType.TEXT,
    "emergency.consent": FieldType.BOOL,
}

# усе, що може лежати в medical_cards.data
CARD_DATA_FIELDS: dict[str, FieldType] = {**MODEL_FIELDS, **DOCTOR_CARD_FIELDS}
