"""Restore local PII in S3 and S4 document text after LLM generation.

The source documents are not modified. S6 restores only the selected non-empty
text values; structural fields, evidence and other metadata are preserved.
"""

from __future__ import annotations

from typing import Any

from src.schemas.contracts import S3Out, S4Out, S6RestoreOut
from src.systems.privacy_ner.exceptions import InvalidRequestError


def _check_items(
    expected: list[dict[str, str]],
    restored: S6RestoreOut | dict[str, Any],
) -> dict[str, str]:
    """Validate that S6 returned exactly one result for every requested key."""
    output = S6RestoreOut.model_validate(restored)
    expected_keys = {item["key"] for item in expected}
    restored_keys = [item.key for item in output.items]
    if len(restored_keys) != len(expected) or set(restored_keys) != expected_keys:
        raise InvalidRequestError("Restore returned missing, duplicated or unknown keys")
    return {item.key: item.text for item in output.items}


def s3_to_items(card: S3Out | dict[str, Any]) -> list[dict[str, str]]:
    """Select only non-empty medical-card text values for S6 restore."""
    model = S3Out.model_validate(card)
    items: list[dict[str, str]] = []
    for field in model.fields:
        if isinstance(field.value, str) and field.value:
            items.append({"key": f"{field.field_id}.value", "text": field.value})
        if isinstance(field.contradiction_text, str) and field.contradiction_text:
            items.append({
                "key": f"{field.field_id}.contradiction_text",
                "text": field.contradiction_text,
            })
    return items


def apply_items_to_s3(
    card: S3Out | dict[str, Any],
    restored: S6RestoreOut | dict[str, Any],
) -> S3Out:
    """Replace selected S3 text values and validate the complete document."""
    original = S3Out.model_validate(card)
    replacements = _check_items(s3_to_items(original), restored)
    result = original.model_dump(mode="python")
    for field in result["fields"]:
        for attr in ("value", "contradiction_text"):
            key = f"{field['field_id']}.{attr}"
            if key in replacements:
                field[attr] = replacements[key]
    return S3Out.model_validate(result)


def s4_to_items(note: S4Out | dict[str, Any]) -> list[dict[str, str]]:
    """Select SOAP text sections and plan items for S6 restore."""
    model = S4Out.model_validate(note)
    items = [
        {"key": f"{section}.text", "text": getattr(model, section).text}
        for section in ("subjective", "objective", "assessment")
        if getattr(model, section).text
    ]
    items.extend(
        {"key": f"plan.{index}.text", "text": item.text}
        for index, item in enumerate(model.plan)
        if item.text
    )
    return items


def apply_items_to_s4(
    note: S4Out | dict[str, Any],
    restored: S6RestoreOut | dict[str, Any],
) -> S4Out:
    """Restore SOAP prose without changing its evidence, flags or origins."""
    original = S4Out.model_validate(note)
    replacements = _check_items(s4_to_items(original), restored)
    result = original.model_dump(mode="python")
    for section in ("subjective", "objective", "assessment"):
        key = f"{section}.text"
        if key in replacements:
            result[section]["text"] = replacements[key]
    for index, item in enumerate(result["plan"]):
        key = f"plan.{index}.text"
        if key in replacements:
            item["text"] = replacements[key]
    return S4Out.model_validate(result)
