import json
from pathlib import Path
from typing import Any

from .LLM import LLM
from .Gemini import Gemini
from .exceptions import ClinicalEngineError, LLMResponseError
from .prompt_manager import PromptManager
from pydantic import TypeAdapter, ValidationError
from src.schemas import contracts

class ClinicalService:
    """Generate clinical documents through dict -> dict service contracts."""

    def __init__(self, llm: LLM | None = None, prompt_manager: PromptManager | None = None):
        self.llm = llm if llm else Gemini()
        self.prompt_manager = prompt_manager if prompt_manager else PromptManager(prompts_dir=Path(__file__).parent / "prompts")

    @staticmethod
    def _prompt_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def generate_medical_card(self, input_data: dict) -> dict:
        """
        Generate a medical card.

        Input:
            {
                "transcription": {
                    "segments": [
                        {"segment_id": int, "speaker": str, "text": str}
                    ]
                }
            }

        Output:
            {
                "fields": ...,
            }
        """
        transcription = self._get_required(input_data, "transcription")
        prompt = self.prompt_manager.get_prompt(
            prompt_name="client_card",
            transcription=self._prompt_value(transcription))
        try:
            response = self.llm.query(prompt=prompt, schema=contracts.S3Out)
            return contracts.S3Out.model_validate_json(response).model_dump()
        except (ValidationError, json.JSONDecodeError) as error:
            raise LLMResponseError(
                "Gemini returned an invalid medical card response."
            ) from error

    def generate_soap_note(self, input_data: dict) -> dict:
        """
        Generate a SOAP note.

        Input:
            {
                "transcription": {
                    "segments": [
                        {"segment_id": int, "speaker": str, "text": str}
                    ]
                },
                "biomarkers": ...,
            }

        Output:
            {
                "subjective": ...,
                "objective": ...,
                "assessment": ...,
                "plan": ...,
            }
        """
        transcription = self._get_required(input_data, "transcription")
        biomarkers = self._get_required(input_data, "biomarkers")
        subjective = self.__fetch_subjective(transcription)
        objective = self.__fetch_objective(transcription, biomarkers)
        assessment = self.__fetch_assessment(transcription, subjective, objective)
        plan = self.__fetch_plan(transcription, biomarkers, assessment)

        try:
            return contracts.S4Out(
                subjective=subjective,
                objective=objective,
                assessment=assessment,
                plan=plan,
            ).model_dump()
        except ValidationError as error:
            raise LLMResponseError("Clinical engine output failed S4 validation.") from error

    @staticmethod
    def _get_required(input_data: dict, key: str) -> Any:
        if not isinstance(input_data, dict):
            raise ClinicalEngineError("Clinical engine input must be a dictionary.")
        if key not in input_data:
            raise ClinicalEngineError(
                f"Clinical engine input is missing required key: '{key}'."
            )
        return input_data[key]

    def __fetch_subjective(self, transcription: Any) -> contracts.Subjective:
        prompt = self.prompt_manager.get_prompt(
            "subjective", transcription=self._prompt_value(transcription)
        )
        try:
            response = self.llm.query(prompt=prompt, schema=contracts.Subjective)
            return contracts.Subjective.model_validate_json(response)
        except (ValidationError, json.JSONDecodeError) as error:
            raise LLMResponseError("Gemini returned an invalid subjective response.") from error

    def __fetch_objective(self, transcription: Any, biomarkers: Any) -> contracts.Objective:
        prompt = self.prompt_manager.get_prompt(
            "objective",
            transcription=self._prompt_value(transcription),
            biomarkers=self._prompt_value(biomarkers),
        )
        try:
            response = self.llm.query(prompt=prompt, schema=contracts.Objective)
            return contracts.Objective.model_validate_json(response)
        except (ValidationError, json.JSONDecodeError) as error:
            raise LLMResponseError("Gemini returned an invalid objective response.") from error

    def __fetch_assessment(
        self,
        transcription: Any,
        subjective: contracts.Subjective,
        objective: contracts.Objective,
    ) -> contracts.Assessment:
        prompt = self.prompt_manager.get_prompt(
            "assessment",
            subjective=subjective.model_dump_json(),
            objective=objective.model_dump_json(),
            transcription=self._prompt_value(transcription),
        )
        try:
            response = self.llm.query(prompt=prompt, schema=contracts.Assessment)
            return contracts.Assessment.model_validate_json(response)
        except (ValidationError, json.JSONDecodeError) as error:
            raise LLMResponseError("Gemini returned an invalid assessment response.") from error

    def __fetch_plan(
        self,
        transcription: Any,
        biomarkers: Any,
        assessment: contracts.Assessment,
    ) -> list[contracts.PlanItem]:
        prompt = self.prompt_manager.get_prompt(
            prompt_name="plan",
            assessment=assessment.model_dump_json(),
            transcription=self._prompt_value(transcription),
            biomarkers=self._prompt_value(biomarkers),
        )
        try:
            response = self.llm.query(prompt=prompt, schema=list[contracts.PlanItem])
            return TypeAdapter(list[contracts.PlanItem]).validate_json(response)
        except (ValidationError, json.JSONDecodeError) as error:
            raise LLMResponseError("Gemini returned an invalid plan response.") from error