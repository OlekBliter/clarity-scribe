import re
from copy import deepcopy

from database.exceptions import UserInputError
from schemas import S4Out, MedicalCardData, CardField, BOOL_FIELDS

TEXT_FIELDS = {
    "subjective.text",
    "objective.text",
    "assessment.text",
}

PLAN_PATTERN = re.compile(r"plan\[(\d+)\]\.text")

def apply_soap_edits(final: S4Out | dict, edits: dict[str, str]) -> S4Out:
    data = (
        final.model_dump(mode="python")
        if isinstance(final, S4Out)
        else deepcopy(final)
    )

    for path, value in edits.items():
        if not isinstance(value, str):
            raise UserInputError('Invalid data')

        if path in TEXT_FIELDS:
            section, field = path.split(".")

            if (section not in data
                    or not isinstance(data[section], str)
                    or field not in data[section]):
                raise UserInputError('Invalid edit path')

            data[section][field] = value
            continue

        matched = PLAN_PATTERN.fullmatch(value)
        if matched:
            index = int(matched.group(1))
            plan = data.get('plan')

            if (not isinstance(plan, list)
                    or index >= len(plan)
                    or not isinstance(plan[index], dict)
                    or "text" not in plan[index]):
                raise UserInputError(
                    f"Invalid edit path: {path}"
                )

            plan[index]["text"] = value
            continue

        raise UserInputError(
            f"Unsupported edit path: {path}"
        )

    return S4Out.model_validate(data)

def apply_card_edits(data: dict | MedicalCardData, edits) -> MedicalCardData:
    card = MedicalCardData.model_validate(
        deepcopy(data)
        if isinstance(data, dict)
        else data.model_dump()
    )

    # Index existing fields by their identifiers
    fields = {
        field.field_id: field
        for field in card.fields
    }

    for edit in edits:
        path = edit.path
        value = edit.new_value

        # Patient contacts are stored separately
        if path.startswith(("contact.", "emergency.")):
            raise UserInputError(
                f"Cannot edit contact field: {path}"
            )

        if not path:
            raise UserInputError("Field path cannot be empty")

        # Validate the value type
        if path in BOOL_FIELDS:
            if type(value) is not bool:
                raise UserInputError(
                    f"Field {path} requires a boolean"
                )
        elif not isinstance(value, str):
            raise UserInputError(
                f"Field {path} requires a string"
            )

        if path in fields:
            # Update an existing field
            field = fields[path]
            field.value = value
            field.edited_by_doctor = True

        else:
            # Add a new doctor-entered field
            field = CardField(
                field_id=path,
                status="doctor_input",
                value=value,
                edited_by_doctor=True,
            )

            card.fields.append(field)
            fields[path] = field

    return MedicalCardData.model_validate(
        card.model_dump()
    )