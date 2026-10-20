import sys
from pathlib import Path

from .LLM import LLM
from .file_reader import FileReader
from .prompt_manager import PromptManager

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from schemas import contracts

class ClinicalService:
    def __init__(self, llm: LLM, prompt_manager: PromptManager):
        self.llm = llm
        self.prompt_manager = prompt_manager

    def generate_soap_note(self, transcription_path: Path | str, biomarkers_path: Path | str):
        subjective = self.__fetch_subjective(transcription_path)
        objective = self.__fetch_objective(biomarkers_path)
        assessment = self.__fetch_assessment(transcription_path, subjective, objective)
        plan = self.__fetch_plan(transcription_path, biomarkers_path, assessment)

        soap_note = subjective | objective | assessment | plan
        return soap_note

    def __fetch_subjective(self, transcription_path: Path | str):
        prompt = self.prompt_manager.get_prompt("subjective")
        res = self.llm.query(
            prompt=prompt,
            context_json_path=transcription_path,
            schema=contracts.Subjective
        )
        return {"subjective": res}


    def __fetch_objective(self, biomarkers_path: Path | str):
        prompt = self.prompt_manager.get_prompt("objective")
        res = self.llm.query(
            prompt=prompt,
            context_json_path=biomarkers_path,
            schema=contracts.Objective
        )
        return {"objective": res}

    def __fetch_assessment(self, transcription_path: Path | str, subjective: dict, objective: dict) -> dict:
        prompt = self.prompt_manager.get_prompt(
            "assessment",
            subjective=subjective.get("subjective"),
            objective=objective.get("objective")
        )
        res = self.llm.query(
            prompt=prompt,
            context_json_path=transcription_path,
            schema=contracts.Assessment
        )
        return {"assessment": res}

    def __fetch_plan(self, transcription_path: Path | str, biomarkers_path: Path | str, assessment: dict) -> dict:
        prompt = self.prompt_manager.get_prompt(
            "plan",
            assessment=assessment.get("assessment")
        )
        res = self.llm.query(
            prompt=prompt,
            context_json_path=transcription_path,
            schema=list[contracts.PlanItem]
        )
        return {"plan": res}