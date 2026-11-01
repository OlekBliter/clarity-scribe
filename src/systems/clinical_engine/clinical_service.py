import sys
import json
from pathlib import Path
from typing import Any

from .LLM import LLM
from .Gemini import Gemini
from .prompt_manager import PromptManager
from pydantic import TypeAdapter

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    (sys
     .path.insert(0, str(SRC_DIR)))
from schemas import contracts

class ClinicalService:
    def __init__(self, llm: LLM | None = None, prompt_manager: PromptManager | None = None):
        self.llm = llm if llm else Gemini()
        self.prompt_manager = prompt_manager if prompt_manager else PromptManager(prompts_dir=Path(__file__).parent / "prompts")

    @staticmethod
    def _prompt_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def generate_soap_note(self, transcription: Any, biomarkers: Any) -> dict:
        subjective = self.__fetch_subjective(transcription)
        objective = self.__fetch_objective(transcription, biomarkers)
        assessment = self.__fetch_assessment(transcription, subjective, objective)
        plan = self.__fetch_plan(transcription, biomarkers, assessment)

        return contracts.S4Out(
            subjective=subjective,
            objective=objective,
            assessment=assessment,
            plan=plan,
        ).model_dump()

    def __fetch_subjective(self, transcription: Any) -> contracts.Subjective:
        prompt = self.prompt_manager.get_prompt(
            "subjective", transcription=self._prompt_value(transcription)
        )
        response = self.llm.query(
            prompt=prompt,
            schema=contracts.Subjective
        )
        return contracts.Subjective.model_validate_json(response)

    def __fetch_objective(self, transcription: Any, biomarkers: Any) -> contracts.Objective:
        prompt = self.prompt_manager.get_prompt(
            "objective",
            transcription=self._prompt_value(transcription),
            biomarkers=self._prompt_value(biomarkers),
        )
        response = self.llm.query(
            prompt=prompt,
            schema=contracts.Objective
        )
        return contracts.Objective.model_validate_json(response)

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
        response = self.llm.query(
            prompt=prompt,
            schema=contracts.Assessment
        )
        return contracts.Assessment.model_validate_json(response)

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
        response = self.llm.query(
            prompt=prompt,
            schema=list[contracts.PlanItem]
        )
        return TypeAdapter(list[contracts.PlanItem]).validate_json(response)

    def generate_medical_card(self, transcription: Any) -> dict:
        prompt = self.prompt_manager.get_prompt(
            prompt_name="client_card",
            transcription=self._prompt_value(transcription))
        response = self.llm.query(
            prompt=prompt,
            schema=contracts.S3Out
        )
        return contracts.S3Out.model_validate_json(response).model_dump()