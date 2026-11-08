import json
from pathlib import Path
from typing import Any

from .LLM import LLM
from .exceptions import ClinicalEngineError, LLMResponseError
from .prompt_manager import PromptManager
from .placeholder_validation import allowed_placeholders, invalid_placeholders
from pydantic import TypeAdapter, ValidationError
from src.schemas import contracts

class ClinicalService:
    """Generate clinical documents through dict -> dict service contracts."""

    def __init__(self, llm: LLM | None = None, prompt_manager: PromptManager | None = None):
        if llm is None:
            from .Gemini import Gemini
            llm = Gemini()
        self.llm = llm
        self.prompt_manager = prompt_manager if prompt_manager else PromptManager(prompts_dir=Path(__file__).parent / "prompts")


    @staticmethod
    def _prompt_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _query_with_placeholder_retry(
        self, *, transcription: Any, prompt: str, schema: Any,
        system_instruction: str,
    ) -> str:
        # Only source transcription authorizes tags, never template examples or
        # generated sections. Do not send the private NER map to the LLM.
        allowed = allowed_placeholders(transcription)
        for attempt in range(2):
            response = self.llm.query(
                prompt=prompt, schema=schema, system_instruction=system_instruction,
            )
            # Decode before scanning: JSON unicode escapes must not bypass checks.
            invalid = invalid_placeholders(json.loads(response), allowed)
            if not invalid:
                return response
            if attempt == 0:
                prompt += (
                    "\n=== PLACEHOLDER CORRECTION ===\n"
                    "The previous response contained invalid placeholders. "
                    "Regenerate the complete response using the original evidence. "
                    "Use only these exact placeholders: "
                    + json.dumps(sorted(allowed), ensure_ascii=False)
                    + ". Preserve brackets, prefix, case and number exactly. "
                    "Do not guess replacements or original personal data. "
                    "Omit unsupported claims. Return the required JSON only."
                )
        raise LLMResponseError(
            "Clinical engine returned invalid placeholders after one correction retry."
        )

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
            response = self._query_with_placeholder_retry(transcription=transcription, prompt=prompt,
                                      schema=contracts.S3Out,
                                      system_instruction="""You assist a psychiatrist by extracting the first-session medical card (S3Out).
Your task is structured evidence extraction, not diagnosis or treatment advice.
""")
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
            response = self._query_with_placeholder_retry(transcription=transcription, prompt=prompt,
                                      schema=contracts.Subjective,
                                      system_instruction="""You assist a psychiatrist by drafting the Subjective section of a SOAP note.
The output is a clinician-reviewable draft, not a medical decision.
""")
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
            response = self._query_with_placeholder_retry(transcription=transcription, prompt=prompt,
                                      schema=contracts.Objective,
                                      system_instruction="""You assist a psychiatrist by drafting the Objective section of a SOAP note.
The output describes available transcript observations and quantitative voice
features; it is not a psychiatric diagnosis or validated clinical risk score.
""")
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
            response = self._query_with_placeholder_retry(transcription=transcription, prompt=prompt,
                                      schema=contracts.Assessment,
                                      system_instruction="""You assist a psychiatrist by drafting the Assessment section of a SOAP note.
The draft is for clinician review and must not introduce an independent diagnosis.
""")
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
            response = self._query_with_placeholder_retry(transcription=transcription, prompt=prompt,
                                      schema=list[contracts.PlanItem],
                                      system_instruction="""You assist a psychiatrist by drafting the Plan section of a SOAP note.
The generated plan is only a proposal for the treating clinician to review.
Never present a model-generated suggestion as an already prescribed treatment.
""")
            return TypeAdapter(list[contracts.PlanItem]).validate_json(response)
        except (ValidationError, json.JSONDecodeError) as error:
            raise LLMResponseError("Gemini returned an invalid plan response.") from error