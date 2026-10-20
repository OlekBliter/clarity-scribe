import json
import pytest
from pydantic import ValidationError

from schemas.contracts import (
    S4Out,
    Subjective,
    Objective,
    Assessment,
    PlanItem,
)
from systems.clinical_engine.LLM import LLM
from systems.clinical_engine.clinical_service import ClinicalService
from systems.clinical_engine.file_reader import FileReader
from systems.clinical_engine.prompt_manager import PromptManager


# ==========================================
# 1. S4Out SCHEMA VALIDATION TESTS
# ==========================================

def test_s4out_valid_payload():
    """Verify that a fully populated and valid dictionary validates successfully."""
    raw_payload = {
        "subjective": {
            "text": "Patient reports depressed mood and sleep disturbances.",
            "source_segments": [1, 3, 5]
        },
        "objective": {
            "text": "Speech rate is 2.5 syllables/s, pause ratio is 34%.",
            "biomarker_refs": ["speech_rate_syllables_per_sec", "pause_ratio"]
        },
        "assessment": {
            "text": "Low mood triggered by an acute stressful life event.",
            "basis": "model_synthesis"
        },
        "plan": [
            {
                "text": "Follow-up consultation in one week",
                "origin": "doctor_stated"
            },
            {
                "text": "Consider sleep quality assessment",
                "origin": "recommended"
            }
        ]
    }

    note = S4Out.model_validate(raw_payload)

    # Assert individual section values
    assert note.subjective.source_segments == [1, 3, 5]
    assert len(note.objective.biomarker_refs) == 2
    assert note.assessment.basis == "model_synthesis"
    assert len(note.plan) == 2
    assert note.plan[0].origin == "doctor_stated"


def test_s4out_missing_required_section_raises_error():
    """Ensure that omitting mandatory sections triggers a ValidationError."""
    incomplete_payload = {
        "subjective": {
            "text": "General fatigue reported.",
            "source_segments": [1]
        },
        # Sections 'objective' and 'assessment' are strictly required without defaults
    }

    with pytest.raises(ValidationError) as exc_info:
        S4Out.model_validate(incomplete_payload)

    errors = exc_info.value.errors()
    missing_fields = {err["loc"][0] for err in errors}

    # Asserting only fields that do not have default values in the schema
    assert {"objective", "assessment"}.issubset(missing_fields)


def test_s4out_invalid_source_segments_type():
    """Ensure that source_segments requires an integer array."""
    invalid_payload = {
        "text": "Symptoms present",
        "source_segments": ["invalid_string", "12a"]
    }

    with pytest.raises(ValidationError):
        Subjective.model_validate(invalid_payload)


# ==========================================
# 2. ClinicalService INTEGRATION TESTS (MOCK LLM)
# ==========================================

class MockLLM(LLM):
    """Mock LLM implementation for deterministic local testing without API calls."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.called_prompts: list[str] = []

    def query(self, prompt: str, context_json_path=None, schema=None) -> str:
        # Record prompts sent to the engine
        self.called_prompts.append(prompt)

        # Return canned JSON responses mapped to target schemas
        if schema == Subjective:
            return self.responses.get("subjective", "{}")
        elif schema == Objective:
            return self.responses.get("objective", "{}")
        elif schema == Assessment:
            return self.responses.get("assessment", "{}")
        return self.responses.get("plan", "[]")

    def set_response_schema(self, response_schema=None):
        pass


@pytest.fixture
def sample_mock_responses():
    """Fixture providing serialized JSON payloads for individual section calls."""
    return {
        "subjective": json.dumps({
            "text": "Patient exhibits signs of situational anxiety.",
            "source_segments": [2, 4]
        }),
        "objective": json.dumps({
            "text": "Fundamental frequency variation is reduced.",
            "biomarker_refs": ["f0_variability_sd"]
        }),
        "assessment": json.dumps({
            "text": "Rule out acute stress reaction.",
            "basis": "model_synthesis"
        }),
        "plan": json.dumps([
            {"text": "Recommend daily mood tracking", "origin": "recommended"}
        ])
    }


def test_clinical_service_generates_and_merges_soap_dict(tmp_path, sample_mock_responses):
    """Verify that ClinicalService orchestrates calls and merges sections properly."""
    # Setup temporary directory and mock prompt templates
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "subjective.txt").write_text("Prompt subjective", encoding="utf-8")
    (prompts_dir / "objective.txt").write_text("Prompt objective", encoding="utf-8")
    (prompts_dir / "assessment.txt").write_text("Prompt assessment: {subjective} {objective}", encoding="utf-8")
    (prompts_dir / "plan.txt").write_text("Prompt plan: {assessment}", encoding="utf-8")

    # Create dummy file for FileReader initialization
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("dummy", encoding="utf-8")

    mock_llm = MockLLM(responses=sample_mock_responses)
    prompt_manager = PromptManager(prompts_dir=prompts_dir)

    service = ClinicalService(
        llm=mock_llm,
        prompt_manager=prompt_manager,
    )

    result_dict = service.generate_soap_note(
        transcription_path="mock_transcription.json",
        biomarkers_path="mock_biomarkers.json"
    )

    # Ensure all four sections are present in the aggregated dictionary
    assert "subjective" in result_dict
    assert "objective" in result_dict
    assert "assessment" in result_dict
    assert "plan" in result_dict

    # Reconstruct and validate the complete S4Out model
    structured_note = S4Out(
        subjective=Subjective.model_validate_json(result_dict["subjective"]),
        objective=Objective.model_validate_json(result_dict["objective"]),
        assessment=Assessment.model_validate_json(result_dict["assessment"]),
        plan=[PlanItem.model_validate(p) for p in json.loads(result_dict["plan"])]
    )

    assert structured_note.subjective.source_segments == [2, 4]
    assert structured_note.plan[0].text == "Recommend daily mood tracking"