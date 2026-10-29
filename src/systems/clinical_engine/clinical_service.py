import sys
from pathlib import Path

from .LLM import LLM
from .Gemini import Gemini
from .prompt_manager import PromptManager

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    (sys
     .path.insert(0, str(SRC_DIR)))
from schemas import contracts

class ClinicalService:
    def __init__(self, llm: LLM | None = None, prompt_manager: PromptManager | None = None):
        self.llm = llm if llm else Gemini()
        self.prompt_manager = prompt_manager if prompt_manager else PromptManager(prompts_dir=Path(__file__).parent / "prompts")

    def generate_soap_note(self, transcription, biomarkers):
        subjective = self.__fetch_subjective(transcription)
        objective = self.__fetch_objective(transcription, biomarkers)
        assessment = self.__fetch_assessment(transcription, subjective, objective)
        plan = self.__fetch_plan(transcription, biomarkers, assessment)

        soap_note = subjective | objective | assessment | plan
        return soap_note

    def __fetch_subjective(self, transcription):
        prompt = self.prompt_manager.get_prompt("subjective", transcription=transcription)
        res = self.llm.query(
            prompt=prompt,
            schema=contracts.Subjective
        )
        return {"subjective": res}


    def __fetch_objective(self, transcription, biomarkers):
        prompt = self.prompt_manager.get_prompt("objective", transcription=transcription, biomarkers=biomarkers)
        res = self.llm.query(
            prompt=prompt,
            schema=contracts.Objective
        )
        return {"objective": res}

    def __fetch_assessment(self, transcription, subjective: dict, objective: dict) -> dict:
        prompt = self.prompt_manager.get_prompt(
            "assessment",
            subjective=subjective.get("subjective"),
            objective=objective.get("objective"),
            transcription=transcription
        )
        res = self.llm.query(
            prompt=prompt,
            schema=contracts.Assessment
        )
        return {"assessment": res}

    def __fetch_plan(self, transcription, biomarkers, assessment: dict) -> dict:
        prompt = self.prompt_manager.get_prompt(
            prompt_name="plan",
            assessment=assessment.get("assessment"),
            transcription=transcription,
            biomarkers=biomarkers
        )
        res = self.llm.query(
            prompt=prompt,
            schema=list[contracts.PlanItem]
        )
        return {"plan": res}
    def generate_medical_card(self, transcription_path :Path| str)->dict:
        prompt = self.prompt_manager.get_prompt(
            prompt_name="client_card",
            transcription=transcription_path)
        res = self.llm.query(
            prompt=prompt,
            schema=contracts.S3Out
        )
        return res