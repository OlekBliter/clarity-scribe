"""Fake systems and dummy data for testing the Facade without loading ML libraries."""
import os
import wave
from typing import Any

from src.schemas.contracts import MODEL_FIELDS


class S1Fake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = []

    def transcribe(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.fail_with:
            raise self.fail_with
        return {
            "language": "uk",
            "metadata": {
                "audio_duration_sec": 1965.0,
                "doctor_speaking_time_sec": 450.0,
                "patient_speaking_time_sec": 1400.0,
                "silence_time_sec": 115.0
            },
            "segments": [
                {"segment_id": 0, "speaker": "DOCTOR", "start_time": 2.0, "end_time": 5.0, "text": "Доброго дня.", "confidence": 0.9},
                {"segment_id": 1, "speaker": "PATIENT", "start_time": 6.0, "end_time": 9.0, "text": "Дуже важко.", "confidence": 0.8}
            ]
        }


class S2Fake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = []

    def extract_biomarkers(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.fail_with:
            raise self.fail_with
        return {
            "raw_dsp_features": {
                "f0_variability_sd": 14.8, "f0_mean_hz": 185.2, "jitter_percent": 1.45,
                "shimmer_percent": 4.12, "hnr_db": 16.8, "speech_rate_syllables_per_sec": 3.4,
                "pause_ratio": 0.28, "mean_latent_response_time_sec": 1.68
            },
            "inferred_indices": {
                "affect_flatness_flag": False, "vocal_jitter_percentile": 62.0,
                "psychomotor_retardation_index": 0.30,
                "intrasession_dynamics": {
                    "f0_variability_change_percent": 10.0,
                    "speech_rate_change_percent": -5.0,
                    "pause_ratio_change_percent": 2.0,
                    "trend_summary": "activation"
                }
            },
            "window_chunks": [
                {"window_index": 0, "time_range": "00:00-03:00", "f0_variability_sd": 14.0, "speech_rate_syllables_per_sec": 3.5, "pause_ratio": 0.25}
            ]
        }


class ClinicalFake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls_card = []
        self.calls_soap = []

    def generate_medical_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls_card.append(payload)
        if self.fail_with:
            raise self.fail_with
        fields = []
        for field_id in MODEL_FIELDS:
            if field_id == "request.complaint":
                fields.append({"field_id": field_id, "status": "filled", "value": "Дуже важко", "evidence": [1]})
            else:
                fields.append({"field_id": field_id, "status": "not_discussed"})
        return {"fields": fields}

    def generate_soap_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls_soap.append(payload)
        if self.fail_with:
            raise self.fail_with
        return {
            "subjective": {"text": "Пацієнт скаржиться.", "source_segments": [1]},
            "objective": {"text": "Спостерігається втома.", "biomarker_refs": ["pause_ratio"]},
            "assessment": {"text": "Депресивна динаміка.", "basis": "model_synthesis"},
            "plan": [{"text": "Продовжити терапію.", "origin": "recommended"}]
        }


class S6Fake:
    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.calls = []

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.fail_with:
            raise self.fail_with
        op = payload.get("operation")
        if op == "sanitize":
            return {
                "items": [{"key": it["key"], "text": it["text"]} for it in payload.get("items", [])],
                "map": payload.get("map", {})
            }
        # restore
        return {"items": [{"key": it["key"], "text": it["text"]} for it in payload.get("items", [])]}


# Generate test tiny_stereo.wav (1 second of silence, 2 channels, 44100Hz)
_DUMMY_WAV_PATH = os.path.join(os.path.dirname(__file__), "tiny_stereo.wav")
if not os.path.exists(_DUMMY_WAV_PATH):
    os.makedirs(os.path.dirname(_DUMMY_WAV_PATH), exist_ok=True)
    with wave.open(_DUMMY_WAV_PATH, 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b'\x00' * 44100)