from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from copy import deepcopy
from typing import Any

from src.schemas.contracts import S3Out, S4Out

_S3_RESTORABLE_ATTRS: frozenset[str] = frozenset({"value", "contradiction_text"})
_S4_TEXT_SECTIONS: tuple[str, ...] = ("subjective", "objective", "assessment")


def _to_plain_dict(model_or_dict: Any) -> dict[str, Any]:
    """Convert a Pydantic model or mapping into a deep-copied plain dictionary."""
    if hasattr(model_or_dict, "model_dump"):
        return deepcopy(model_or_dict.model_dump())
    if isinstance(model_or_dict, Mapping):
        return deepcopy(dict(model_or_dict))

    from src.services.orchestrator.orchestrator import OrchestratorError

    raise OrchestratorError(
        f"Expected Pydantic model or mapping, got {type(model_or_dict).__name__}"
    )


def _get_s3_fields_container(raw: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Return the dictionary holding S3 field objects (supports nested 'fields' or top-level)."""
    fields_sub = raw.get("fields")
    if isinstance(fields_sub, MutableMapping):
        return fields_sub
    return raw


def _normalize_restored_items(restored_items: Any) -> list[tuple[str, str]]:
    """Normalize restored items from S6 into a list of (key, text) pairs.

    Supports S6RestoreOut instances, lists of dicts [{'key': ..., 'text': ...}],
    lists of Pydantic item models, or plain {key: text} mappings.
    """
    from src.services.orchestrator.orchestrator import OrchestratorError

    if hasattr(restored_items, "items") and not isinstance(restored_items, Mapping):
        restored_items = getattr(restored_items, "items")

    if isinstance(restored_items, Mapping):
        return [(str(k), str(v)) for k, v in restored_items.items()]

    if not isinstance(restored_items, Iterable) or isinstance(restored_items, (str, bytes)):
        raise OrchestratorError("Invalid restored_items format for entity restoration")

    pairs: list[tuple[str, str]] = []
    for item in restored_items:
        if isinstance(item, Mapping):
            if "key" not in item or "text" not in item:
                raise OrchestratorError("Restored item dict is missing 'key' or 'text'")
            pairs.append((str(item["key"]), str(item["text"])))
        elif hasattr(item, "key") and hasattr(item, "text"):
            pairs.append((str(getattr(item, "key")), str(getattr(item, "text"))))
        else:
            raise OrchestratorError(
                f"Unsupported restored item element type: {type(item).__name__}"
            )
    return pairs


def s3_to_items(s3_out: S3Out | Mapping[str, Any]) -> list[dict[str, str]]:
    """Extract non-empty string fields from S3 output for S6 restoration.

    Inspects every field in S3Out and extracts only non-empty strings under keys:
    - `<field_id>.value` (only if `value` is a non-empty `str`; ignores bool/None/empty)
    - `<field_id>.contradiction_text` (only if `contradiction_text` is a non-empty `str`)

    Args:
        s3_out: Validated S3Out instance or raw dictionary.

    Returns:
        List of {"key": str, "text": str} items for `build_s6_in("restore", ...)`.
    """
    raw = _to_plain_dict(s3_out)
    fields_container = _get_s3_fields_container(raw)
    items: list[dict[str, str]] = []

    for field_id, field_data in fields_container.items():
        if not isinstance(field_data, Mapping):
            continue

        value = field_data.get("value")
        if isinstance(value, str) and value.strip():
            items.append({"key": f"{field_id}.value", "text": value})

        contradiction_text = field_data.get("contradiction_text")
        if isinstance(contradiction_text, str) and contradiction_text.strip():
            items.append(
                {
                    "key": f"{field_id}.contradiction_text",
                    "text": contradiction_text,
                }
            )

    return items


def apply_items_to_s3(
    s3_out: S3Out | Mapping[str, Any],
    restored_items: Any,
) -> S3Out:
    """Apply restored text items back into S3 structure and re-validate as S3Out.

    Note: Do NOT convert the result to MedicalCardData here; `MedicalCardsRepo.save_restored`
    handles that conversion.

    Args:
        s3_out: Original generated S3Out model or dict before restoration.
        restored_items: List of {"key": str, "text": str} (or S6RestoreOut) from S6 restore.

    Returns:
        Re-validated S3Out model with restored entity strings.
    """
    from src.services.orchestrator.orchestrator import OrchestratorError

    raw = _to_plain_dict(s3_out)
    fields_container = _get_s3_fields_container(raw)

    for key, restored_text in _normalize_restored_items(restored_items):
        if "." not in key:
            raise OrchestratorError(f"Invalid S3 restore key format: {key!r}")

        field_id, attr_name = key.rsplit(".", 1)
        if attr_name not in _S3_RESTORABLE_ATTRS:
            raise OrchestratorError(
                f"Unsupported S3 field attribute {attr_name!r} in key {key!r}"
            )

        field_obj = fields_container.get(field_id)
        if not isinstance(field_obj, MutableMapping):
            raise OrchestratorError(f"Unknown S3 field_id {field_id!r} in key {key!r}")

        field_obj[attr_name] = restored_text

    return S3Out.model_validate(raw)


def s4_to_items(s4_out: S4Out | Mapping[str, Any]) -> list[dict[str, str]]:
    """Extract non-empty string fields from S4 SOAP note output for S6 restoration.

    Extracts only non-empty strings using the exact keys:
    - `subjective.text`
    - `objective.text`
    - `assessment.text`
    - `plan.<i>.text` (for each item at index `i` in `plan`)

    Args:
        s4_out: Validated S4Out instance or raw dictionary.

    Returns:
        List of {"key": str, "text": str} items for `build_s6_in("restore", ...)`.
    """
    raw = _to_plain_dict(s4_out)
    items: list[dict[str, str]] = []

    for section in _S4_TEXT_SECTIONS:
        section_obj = raw.get(section)
        if isinstance(section_obj, Mapping):
            text = section_obj.get("text")
            if isinstance(text, str) and text.strip():
                items.append({"key": f"{section}.text", "text": text})

    plan_list = raw.get("plan")
    if isinstance(plan_list, list):
        for idx, plan_item in enumerate(plan_list):
            if isinstance(plan_item, Mapping):
                text = plan_item.get("text")
                if isinstance(text, str) and text.strip():
                    items.append({"key": f"plan.{idx}.text", "text": text})

    return items


def apply_items_to_s4(
    s4_out: S4Out | Mapping[str, Any],
    restored_items: Any,
) -> S4Out:
    """Apply restored text items back into S4 SOAP note and re-validate as S4Out.

    Args:
        s4_out: Original generated S4Out model or dict before restoration.
        restored_items: List of {"key": str, "text": str} (or S6RestoreOut) from S6 restore.

    Returns:
        Re-validated S4Out model with restored entity strings.
    """
    from src.services.orchestrator.orchestrator import OrchestratorError

    raw = _to_plain_dict(s4_out)

    for key, restored_text in _normalize_restored_items(restored_items):
        if key in ("subjective.text", "objective.text", "assessment.text"):
            section_name, _ = key.split(".", 1)
            section_obj = raw.get(section_name)
            if not isinstance(section_obj, MutableMapping):
                raise OrchestratorError(
                    f"Missing or invalid SOAP section {section_name!r} in S4 payload"
                )
            section_obj["text"] = restored_text
            continue

        parts = key.split(".")
        if len(parts) == 3 and parts[0] == "plan" and parts[2] == "text":
            try:
                idx = int(parts[1])
            except ValueError as exc:
                raise OrchestratorError(
                    f"Invalid plan index in S4 restore key: {key!r}"
                ) from exc

            plan_list = raw.get("plan")
            if not isinstance(plan_list, list) or idx < 0 or idx >= len(plan_list):
                raise OrchestratorError(
                    f"Plan index {idx} out of range in S4 restore key: {key!r}"
                )

            plan_item = plan_list[idx]
            if not isinstance(plan_item, MutableMapping):
                raise OrchestratorError(f"Invalid plan item at index {idx}")

            plan_item["text"] = restored_text
            continue

        raise OrchestratorError(f"Unsupported S4 restore key: {key!r}")

    return S4Out.model_validate(raw)