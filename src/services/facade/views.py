"""Pure functions that transform raw database dicts into UI-ready screen models."""
from datetime import date
import math
from typing import Any

from .registry import mmss, age, fmt_date


def build_sources(segment_ids: list[int], segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Maps raw segment IDs to quote dictionaries for the UI[cite: 7]."""
    seg_map = {s["segment_id"]: s for s in segments}
    result = []
    for sid in segment_ids:
        if sid in seg_map:
            seg = seg_map[sid]
            result.append({
                "segment_id": sid,
                "time": mmss(seg["start_time"]),
                "quote": seg["text_raw"]
            })
    return result


def build_soap_view(
    soap: dict[str, Any], session: dict[str, Any], patient: dict[str, Any],
    first_session: dict[str, Any] | None, segments: list[dict[str, Any]]
) -> dict[str, Any]:
    """Builds the dictionary for the SOAP note screen[cite: 7]."""
    soap_data = soap["final"]
    biomarkers = session.get("biomarkers") or {}
    first_biomarkers = (first_session.get("biomarkers") or {}) if first_session else {}

    chips = []
    for metric in soap_data.get("objective", {}).get("biomarker_refs", []):
        val = biomarkers.get(metric)
        baseline = first_biomarkers.get(metric) if session["session_number"] > 1 else None
        arrow = None
        if val is not None and baseline is not None and not math.isclose(val, baseline):
            arrow = "up" if val > baseline else "down"
        
        chips.append({
            "metric": metric,
            "value": val,
            "baseline": baseline,
            "arrow": arrow
        })

    approved = soap["status"] == "approved"
    session_date = session["session_date"]
    dt = date.fromisoformat(session_date[:10])

    return {
        "session_id": session["session_id"],
        "patient_id": session["patient_id"],
        "patient_name": patient["preferred_name"],
        "number": session["session_number"],
        "date": fmt_date(dt),
        "status": soap["status"],
        "badge": "approved" if approved else "review",
        "editable": not approved,
        "subjective": {
            "text": soap_data.get("subjective", {}).get("text", ""),
            "sources": build_sources(soap_data.get("subjective", {}).get("source_segments", []), segments)
        },
        "objective": {
            "text": soap_data.get("objective", {}).get("text", ""),
            "chips": chips
        },
        "assessment": dict(soap_data.get("assessment", {})),
        "plan": [dict(item) for item in soap_data.get("plan", [])]
    }


def build_card_view(
    card: dict[str, Any], patient: dict[str, Any], segments: list[dict[str, Any]], session_date: str
) -> dict[str, Any]:
    """Builds the dictionary for the Medical Card screen[cite: 7]."""
    draft_fields = {f["field_id"]: f for f in card["draft"]["fields"]}
    data_fields = {f["field_id"]: f for f in card["data"]["fields"]}

    fields = []
    for field_id, d_field in data_fields.items():
        dr_field = draft_fields.get(field_id, {})
        
        # Визначення стану (normal, from_conversation, attention, contradictory)[cite: 2]
        if dr_field.get("attention"):
            state = "attention"
        elif d_field.get("status") == "contradictory" or dr_field.get("status") == "contradictory":
            state = "contradictory"
        elif d_field.get("status") == "filled" or dr_field.get("status") == "filled":
            state = "from_conversation"
        else:
            state = "normal"

        fields.append({
            "field_id": field_id,
            "state": state,
            "value": d_field.get("value"),
            "contradiction_text": dr_field.get("contradiction_text"),
            "sources": build_sources(dr_field.get("evidence", []), segments),
            "edited_by_doctor": d_field.get("edited_by_doctor", False)
        })

    dt = date.fromisoformat(session_date[:10])
    emergency_consent = patient.get("emergency_consent")

    return {
        "patient_id": patient["patient_id"],
        "patient_name": patient["preferred_name"],
        "date": fmt_date(dt),
        "status": card["status"],
        "badge": "approved" if card["status"] == "approved" else "review",
        "editable": card["status"] != "approved",
        "contacts": {
            "preferred_name": patient.get("preferred_name"),
            "birth_date": patient.get("birth_date"),
            "age": age(patient.get("birth_date")),
            "phone": patient.get("phone"),
            "email": patient.get("email"),
            "preferred_channel": patient.get("preferred_channel"),
            "emergency_name": patient.get("emergency_name"),
            "emergency_relation": patient.get("emergency_relation"),
            "emergency_phone": patient.get("emergency_phone"),
            "emergency_consent": bool(emergency_consent) if emergency_consent is not None else None,
        },
        "fields": fields
    }