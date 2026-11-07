"""Apply doctor edits (path -> new_value) to SOAP notes and medical cards."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable

from pydantic import ValidationError

from src.schemas.contracts import (
    BOOL_FIELDS,
    MODEL_FIELDS,
    CardField,
    Edit,
    MedicalCardData,
    S4Out,
)
from src.services.orchestrator.errors import DoctorInputError

SAVE_FAILED = "Не вдалося зберегти правки."

SOAP_TEXT_PATHS = {"subjective.text", "objective.text", "assessment.text"}
PLAN_TEXT_PATTERN = re.compile(r"plan\[(\d+)\]\.text")

# Fields entered by the doctor (Appendix A of the documentation).
DOCTOR_FIELDS = frozenset({
    "scales.phq9", "scales.gad7", "scales.other",
    "hypotheses.notes", "hypotheses.risk",
    "agreements.format", "agreements.frequency",
    "agreements.cost", "agreements.initial_goals",
})
CARD_FIELDS = frozenset(MODEL_FIELDS) | DOCTOR_FIELDS
RISK_VALUES = frozenset({"low", "moderate", "high"})


def apply_soap_edits(final: S4Out | dict[str, Any], edits: Iterable[Edit]) -> S4Out:
    """Return a new S4Out with edits applied. The input is not modified.

    Supported paths: ``subjective.text``, ``objective.text``,
    ``assessment.text`` and ``plan[i].text``.
    """
    data = final.model_dump(mode="python") if isinstance(final, S4Out) else deepcopy(final)

    for edit in edits:
        path, value = edit.path, edit.new_value
        if not isinstance(value, str) or not value.strip():
            raise DoctorInputError(SAVE_FAILED)

        if path in SOAP_TEXT_PATHS:
            section, field = path.split(".")
            target = data.get(section)
            if not isinstance(target, dict) or field not in target:
                raise DoctorInputError(SAVE_FAILED)
            target[field] = value
            continue

        matched = PLAN_TEXT_PATTERN.fullmatch(path)
        if matched:
            index = int(matched.group(1))
            plan = data.get("plan")
            if (
                not isinstance(plan, list)
                or index >= len(plan)
                or not isinstance(plan[index], dict)
                or "text" not in plan[index]
            ):
                raise DoctorInputError(SAVE_FAILED)
            plan[index]["text"] = value
            continue

        raise DoctorInputError(SAVE_FAILED)

    try:
        return S4Out.model_validate(data)
    except ValidationError as exc:
        raise DoctorInputError(SAVE_FAILED) from exc


def apply_card_edits(data: dict[str, Any] | MedicalCardData, edits: Iterable[Edit]) -> MedicalCardData:
    """Return a new MedicalCardData with edits applied. The input is not modified.

    The path is a ``field_id``. Contact and emergency fields live in the
    ``patients`` table and cannot be edited here.
    """
    try:
        card = MedicalCardData.model_validate(
            deepcopy(data) if isinstance(data, dict) else data.model_dump()
        )
    except ValidationError as exc:
        raise DoctorInputError(SAVE_FAILED) from exc

    fields = {field.field_id: field for field in card.fields}

    for edit in edits:
        path, value = edit.path, edit.new_value

        if path not in CARD_FIELDS:
            raise DoctorInputError(SAVE_FAILED)

        if path in BOOL_FIELDS:
            if type(value) is not bool:
                raise DoctorInputError(SAVE_FAILED)
        elif not isinstance(value, str):
            raise DoctorInputError(SAVE_FAILED)
        elif path == "hypotheses.risk" and value not in RISK_VALUES:
            raise DoctorInputError(SAVE_FAILED)

        field = fields.get(path)
        if field is not None:
            field.value = value
            field.edited_by_doctor = True
            # A doctor-provided value resolves "not discussed" / "contradictory".
            if field.status in ("not_discussed", "contradictory") and value != "":
                field.status = "filled"
        else:
            field = CardField(
                field_id=path,
                status="doctor_input",
                value=value,
                edited_by_doctor=True,
            )
            card.fields.append(field)
            fields[path] = field

    try:
        return MedicalCardData.model_validate(card.model_dump())
    except ValidationError as exc:
        raise DoctorInputError(SAVE_FAILED) from exc
