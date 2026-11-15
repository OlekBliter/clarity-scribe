"""Fake systems and dummy data for testing the Facade without loading ML libraries."""
from copy import deepcopy
import json
import os
from pathlib import Path
import wave
from typing import Any


def _load_fixture(filename: str) -> dict[str, Any]:
    """Load a JSON response fixture from this directory."""
    path = Path(__file__).with_name(filename)
    return json.loads(path.read_text(encoding="utf-8"))


class S1Fake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = []
        self._response = _load_fixture("s1_transcription.json")

    def transcribe(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.fail_with is not None:
            raise self.fail_with
        return deepcopy(self._response)


class S2Fake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = []
        self._response = _load_fixture("s2_biomarkers.json")

    def extract_biomarkers(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.fail_with is not None:
            raise self.fail_with
        return deepcopy(self._response)


class ClinicalFake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls_card = []
        self.calls_soap = []
        self._card_response = _load_fixture("s3_medical_card.json")
        self._soap_response = _load_fixture("s4_soap.json")

    def generate_medical_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls_card.append(payload)
        if self.fail_with is not None:
            raise self.fail_with
        return deepcopy(self._card_response)

    def generate_soap_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls_soap.append(payload)
        if self.fail_with is not None:
            raise self.fail_with
        return deepcopy(self._soap_response)


class S5Fake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = []
        self._response = _load_fixture("s5_dynamics.json")

    def calculate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.fail_with is not None:
            raise self.fail_with
        return deepcopy(self._response)


class S6Fake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = []

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.fail_with is not None:
            raise self.fail_with
        op = payload.get("operation")
        if op == "sanitize":
            return {
                "items": [{"key": it["key"], "text": it["text"]} for it in payload.get("items", [])],
                "map": payload.get("map", {})
            }
        # restore
        return {"items": [{"key": it["key"], "text": it["text"]} for it in payload.get("items", [])]}


# Generate a test tiny_stereo.wav (1 second of silence, 2 channels, 44100Hz)
_DUMMY_WAV_PATH = os.path.join(os.path.dirname(__file__), "tiny_stereo.wav")
if not os.path.exists(_DUMMY_WAV_PATH):
    os.makedirs(os.path.dirname(_DUMMY_WAV_PATH), exist_ok=True)
    with wave.open(_DUMMY_WAV_PATH, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x00" * (44100 * 2 * 2))