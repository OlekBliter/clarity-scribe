"""In-memory stub of the facade for developing the UI without a backend.

It subclasses ``ClarityScribeFacade``, so it has exactly the same methods and response
shapes as the real facade. All data lives in memory and is lost on exit.

The stub is interactive: creating patients, adding sessions, "processing", editing,
approving and deleting really change its state, with the same product rules as the
real backend (session #1 needs both SOAP and card approved, approved data is read-only,
an unfinished last session is restarted, session #1 cannot be deleted while others exist).

Usage::

    facade = ClarityScribeFacadeStub()                      # fast demo
    facade = ClarityScribeFacadeStub(step_delay=0.5)        # visible progress
    facade = ClarityScribeFacadeStub(fail_on="s2")          # first run fails on step s2
"""
from __future__ import annotations

import logging
import math
import re
import statistics
import threading
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.schemas.contracts import BOOL_FIELDS, MODEL_FIELDS

from .facade import (
    PROCESSING_STEPS,
    STAGE_KEYS,
    ClarityScribeFacade,
    FacadeError,
    ProgressCallback,
)

logger = logging.getLogger(__name__)

PROCESS_ERROR_MESSAGE = "Сталася помилка. Спробуйте ще раз"
DOCTOR_FIELDS = (
    "scales.phq9", "scales.gad7", "scales.other",
    "hypotheses.notes", "hypotheses.risk",
    "agreements.format", "agreements.frequency", "agreements.cost", "agreements.initial_goals",
)
_CONTACT_KEYS = (
    "preferred_name", "birth_date", "phone", "email", "preferred_channel",
    "emergency_name", "emergency_relation", "emergency_phone", "emergency_consent",
)
_STEP_TO_STAGE = {
    "s1": "transcription",
    "s6_sanitize": "anonymization",
    "s2": "biomarkers",
    "s3_generate": "medical_card",
    "s3_restore": "medical_card",
    "s4_generate": "soap",
    "s4_restore": "soap",
}
_METRIC_TITLES = {
    "pause_ratio": "тривалість пауз",
    "speech_rate_syllables_per_sec": "темп мовлення",
    "f0_variability_sd": "варіативність F0",
    "psychomotor_retardation_index": "індекс психомоторної загальмованості",
}
# metric -> (value at session 1, change per session)
_METRIC_SEED = {
    "pause_ratio": (0.28, 0.02),
    "speech_rate_syllables_per_sec": (3.4, -0.25),
    "f0_variability_sd": (14.8, -0.02),
    "psychomotor_retardation_index": (0.30, 0.08),
}
_TRANSCRIPT = (
    ("DOCTOR", 465.0, 470.0, "Доброго дня! Як ви почувалися протягом цього тижня?"),
    ("PATIENT", 472.0, 480.0, "Чесно кажучи, дуже важко. Майже не вставала з ліжка, зовсім немає сил."),
    ("DOCTOR", 494.0, 499.0, "Чи були якісь помітні зміни в апетиті чи сні?"),
    ("PATIENT", 503.0, 511.0, "Апетиту зовсім немає, а спати хочеться постійно, але сон дуже поверхневий."),
    ("DOCTOR", 525.0, 531.0, "Розумію. А що щодо тривожних думок чи тривоги загалом?"),
    ("PATIENT", 532.0, 541.0, "Іноді з'являється сильна тривога, особливо ввечері, не можу розслабитися."),
    ("DOCTOR", 560.0, 566.0, "Чи були думки завдати собі шкоди?"),
    ("PATIENT", 569.0, 574.0, "Раніше було, років п'ять тому. Зараз ні."),
    ("PATIENT", 730.0, 735.0, "Алкоголь? Ні, не п'ю."),
    ("PATIENT", 842.0, 849.0, "Ну, іноді п'ю вино у вихідні, небагато."),
)
_CARD_SEED = {
    "request.complaint": ("from_conversation", "Дуже важко, майже не встає з ліжка, немає сил.", [1]),
    "request.onset": ("from_conversation", "Погіршення близько місяця тому.", [1]),
    "request.why_now": ("from_conversation", "Накопичений стрес.", [3]),
    "history.on_medication": ("from_conversation", False, [3]),
    "safety.suicidal_past": ("attention", True, [7]),
    "safety.suicidal_now": ("attention", False, [7]),
    "safety.details": ("attention", "Думки були близько п'яти років тому.", [7]),
    "context.work_study": ("from_conversation", "Працює віддалено, дизайнер.", [3]),
    "context.relationships_family": ("from_conversation", "У шлюбі, виховує сина.", [5]),
    "context.social_support": ("from_conversation", "Скаржиться на брак підтримки.", [5]),
    "resources.coping": ("from_conversation", "Малювання, прогулянки, собака.", [5]),
    "goals.change": ("from_conversation", "Відновлення сил, налагодження сну.", [3]),
}
_SOAP_SEED = {
    "subjective": (
        "Пацієнтка повідомляє про тривале зниження настрою, апатію, а також значні труднощі з "
        "ранковим підйомом. Сон залишається переривчастим, апетит помітно знизився.",
        [1, 3],
    ),
    "objective": (
        "Мовлення уповільнене, зафіксовано тривалі паузи під час відповідей та збільшення часу "
        "реакції. Контакт підтримує, але швидко виснажується.",
        ["pause_ratio", "speech_rate_syllables_per_sec", "psychomotor_retardation_index"],
    ),
    "assessment": (
        "Синтез суб'єктивних скарг та об'єктивних спостережень вказує на помірно виражену "
        "депресивну динаміку з ознаками психомоторного уповільнення.",
        "model_synthesis",
    ),
    "plan": (
        ("Продовжити поточну медикаментозну терапію", "doctor_stated"),
        ("Контроль стану, наступний контакт через 1 тиждень", "doctor_stated"),
        ("Розглянути щоденний самоконтроль настрою та сну", "recommended"),
    ),
}
_SOAP_PATH_RE = re.compile(r"^(?:(subjective|objective|assessment)\.text|plan\[(\d+)\]\.text)$")


# --------------------------------------------------------------------- helpers
def _fmt_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _mmss(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def _sessions_word(count: int) -> str:
    """Ukrainian plural: 1 сесія, 2-4 сесії, 5+ сесій."""
    if count % 100 in range(11, 15):
        return "сесій"
    last = count % 10
    if last == 1:
        return "сесія"
    return "сесії" if last in (2, 3, 4) else "сесій"


def _age(birth_date: str | None) -> int | None:
    if not birth_date:
        return None
    for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            born = datetime.strptime(birth_date, pattern).date()
        except ValueError:
            continue
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return None


def _direction(slope: float | None, baseline: float) -> str:
    """Slope above +5% of the baseline per session is "up", below -5% is "down"."""
    if slope is None or baseline == 0:
        return "stable"
    ratio = slope / abs(baseline)
    if ratio > 0.05:
        return "up"
    return "down" if ratio < -0.05 else "stable"


class ClarityScribeFacadeStub(ClarityScribeFacade):
    """Fake facade with demo data and the real behaviour rules."""

    def __init__(
        self,
        step_delay: float = 0.0,
        fail_on: str | None = None,
        audio_path: str | None = None,
    ) -> None:
        """Create the stub with the demo patients from the design mockups.

        Args:
            step_delay: Seconds to "work" on every pipeline step (to see progress).
            fail_on: Step name from ``PROCESSING_STEPS`` that fails on the first run.
            audio_path: Optional real ``.wav`` returned by ``get_audio_info`` so the
                player can be tried; ``None`` disables playback.
        """
        if fail_on is not None and fail_on not in PROCESSING_STEPS:
            raise ValueError(f"Unknown step: {fail_on!r}")
        self._lock = threading.RLock()
        self._step_delay = step_delay
        self._fail_on = fail_on
        self._audio_path = audio_path
        self._patients: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._cards: dict[str, dict[str, Any]] = {}
        self._active: set[str] = set()
        self._progress: dict[str, dict[str, Any]] = {}
        self._seed()

    # ------------------------------------------------------------------ seeding
    def _seed(self) -> None:
        self._seed_patient(
            "usr-anon-1a2b3c01", "Мельник Олена", date(2026, 9, 4), 5, last_open="drafted",
            contacts={"birth_date": "14.05.1989", "phone": "+380 67 123 45 67",
                      "email": "o.melnyk@email.com", "preferred_channel": "Telegram",
                      "emergency_name": "Мельник Дмитро", "emergency_relation": "чоловік",
                      "emergency_phone": "+380 67 123 45 67", "emergency_consent": True},
        )
        self._seed_patient("usr-anon-1a2b3c02", "Коваленко Дмитро", date(2026, 9, 14), 3)
        processing = self._seed_patient("usr-anon-1a2b3c03", "Бондаренко Ірина", date(2026, 10, 5), 1,
                                        last_open="uploaded")
        self._active.add(processing)
        self._seed_patient("usr-anon-1a2b3c04", "Шевченко Тарас", date(2026, 8, 3), 8)
        failed = self._seed_patient("usr-anon-1a2b3c05", "Ткаченко Василь", date(2026, 9, 23), 2,
                                    last_open="uploaded")
        self._sessions[failed]["failed_step"] = "s2"
        self._cards["usr-anon-1a2b3c01"] = self._new_card("usr-anon-1a2b3c01", approved=False)
        for patient_id in ("usr-anon-1a2b3c02", "usr-anon-1a2b3c04", "usr-anon-1a2b3c05"):
            self._cards[patient_id] = self._new_card(patient_id, approved=True)

    def _seed_patient(
        self, patient_id: str, name: str, first_date: date, count: int,
        last_open: str | None = None, contacts: dict[str, Any] | None = None,
    ) -> str:
        record = {key: None for key in _CONTACT_KEYS}
        record.update(contacts or {})
        record.update({"patient_id": patient_id, "preferred_name": name})
        self._patients[patient_id] = record
        last_id = ""
        for index in range(count):
            is_last = index == count - 1
            status = last_open if (is_last and last_open) else "approved"
            last_id = self._new_session(patient_id, index + 1,
                                        date.fromordinal(first_date.toordinal() + 7 * index), status)
        return last_id

    def _new_session(self, patient_id: str, number: int, day: date, status: str) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "session_id": session_id, "patient_id": patient_id, "number": number,
            "date": day, "status": status, "failed_step": None, "language": "uk",
            "soap": self._new_soap(approved=(status == "approved")) if status in ("drafted", "approved") else None,
            "biomarkers": {
                metric: round(base + step * (number - 1), 4) for metric, (base, step) in _METRIC_SEED.items()
            },
        }
        return session_id

    @staticmethod
    def _new_soap(approved: bool) -> dict[str, Any]:
        return {
            "status": "approved" if approved else "draft",
            "subjective": {"text": _SOAP_SEED["subjective"][0], "source_segments": list(_SOAP_SEED["subjective"][1])},
            "objective": {"text": _SOAP_SEED["objective"][0], "biomarker_refs": list(_SOAP_SEED["objective"][1])},
            "assessment": {"text": _SOAP_SEED["assessment"][0], "basis": _SOAP_SEED["assessment"][1]},
            "plan": [{"text": text, "origin": origin} for text, origin in _SOAP_SEED["plan"]],
        }

    @staticmethod
    def _new_card(patient_id: str, approved: bool) -> dict[str, Any]:
        fields: dict[str, dict[str, Any]] = {}
        for field_id in MODEL_FIELDS:
            if field_id in _CARD_SEED:
                state, value, evidence = _CARD_SEED[field_id]
                fields[field_id] = {"state": state, "value": value, "evidence": list(evidence),
                                    "contradiction_text": None}
            elif field_id == "substance.alcohol":
                fields[field_id] = {
                    "state": "contradictory", "value": None, "evidence": [8, 9],
                    "contradiction_text": "Спочатку пацієнт сказав: «не п'ю». Потім: «іноді п'ю вино у вихідні».",
                }
            else:
                fields[field_id] = {"state": "normal", "value": None, "evidence": [], "contradiction_text": None}
        doctor_seed = {"scales.phq9": "18 (Важка депресія)", "scales.gad7": "12 (Помірна тривога)",
                       "hypotheses.risk": "moderate", "agreements.format": "Онлайн",
                       "agreements.frequency": "1 раз/тиждень", "agreements.cost": "1500 грн"}
        for field_id in DOCTOR_FIELDS:
            fields[field_id] = {"state": "normal", "value": doctor_seed.get(field_id), "evidence": [],
                                "contradiction_text": None}
        return {"status": "approved" if approved else "draft", "fields": fields, "edited": set()}

    # ------------------------------------------------------------ small helpers
    def _patient(self, patient_id: str) -> dict[str, Any]:
        try:
            return self._patients[patient_id]
        except KeyError:
            raise FacadeError("Пацієнта не знайдено") from None

    def _session(self, session_id: str) -> dict[str, Any]:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise FacadeError("Сесію не знайдено") from None

    def _patient_sessions(self, patient_id: str) -> list[dict[str, Any]]:
        items = [s for s in self._sessions.values() if s["patient_id"] == patient_id]
        return sorted(items, key=lambda s: s["number"])

    def _badge(self, session: dict[str, Any]) -> str | None:
        if session["session_id"] in self._active:
            return "processing"
        if session["failed_step"]:
            return "error"
        if session["status"] == "approved":
            return "approved"
        if session["status"] == "drafted":
            return "review"
        return "error"  # unfinished and not active: treated as an error

    def _patient_badge(self, patient_id: str) -> str | None:
        badges = {self._badge(s) for s in self._patient_sessions(patient_id)}
        for kind in ("error", "processing", "review", "approved"):
            if kind in badges:
                return kind
        return None

    def _sources(self, segment_ids: list[int]) -> list[dict[str, Any]]:
        result = []
        for segment_id in segment_ids:
            if 0 <= segment_id < len(_TRANSCRIPT):
                _, start, _, text = _TRANSCRIPT[segment_id]
                result.append({"segment_id": segment_id, "time": _mmss(start), "quote": text})
        return result

    # ----------------------------------------------------------------- patients
    def list_patients(self, query: str = "") -> list[dict[str, Any]]:
        needle = query.strip().lower()
        with self._lock:
            rows = []
            for patient_id, patient in self._patients.items():
                name = patient["preferred_name"] or ""
                if needle and needle not in name.lower():
                    continue
                sessions = self._patient_sessions(patient_id)
                if sessions:
                    last = max(s["date"] for s in sessions)
                    subtitle = f"{len(sessions)} {_sessions_word(len(sessions))} • остання {_fmt_date(last)}"
                else:
                    subtitle = "Немає сесій"
                rows.append({"patient_id": patient_id, "name": name, "subtitle": subtitle,
                             "badge": self._patient_badge(patient_id)})
            return rows

    def create_patient(self, contacts: dict[str, Any]) -> str:
        unknown = set(contacts) - set(_CONTACT_KEYS)
        if unknown:
            raise FacadeError("Некоректні дані пацієнта")
        with self._lock:
            patient_id = f"usr-anon-{uuid.uuid4().hex[:8]}"
            record = {key: (contacts.get(key) or None) for key in _CONTACT_KEYS}
            record["patient_id"] = patient_id
            record["preferred_name"] = record["preferred_name"] or "Без імені"
            self._patients[patient_id] = record
            return patient_id

    def delete_patient(self, patient_id: str) -> None:
        with self._lock:
            self._patient(patient_id)
            for session_id in [s["session_id"] for s in self._patient_sessions(patient_id)]:
                self._sessions.pop(session_id, None)
                self._active.discard(session_id)
                self._progress.pop(session_id, None)
            self._cards.pop(patient_id, None)
            del self._patients[patient_id]

    def get_patient_profile(self, patient_id: str) -> dict[str, Any]:
        with self._lock:
            patient = self._patient(patient_id)
            parts = [patient["phone"], patient["email"]]
            if patient["preferred_channel"]:
                parts.append(f"зручний канал: {patient['preferred_channel']}")
            sessions = []
            for session in reversed(self._patient_sessions(patient_id)):
                subtitle = "SOAP-нотатка • медкартка" if session["number"] == 1 else "SOAP-нотатка"
                sessions.append({
                    "session_id": session["session_id"], "number": session["number"],
                    "date": _fmt_date(session["date"]), "subtitle": subtitle,
                    "badge": self._badge(session),
                    "is_ready": session["status"] in ("drafted", "approved"),
                })
            return {
                "patient_id": patient_id, "name": patient["preferred_name"],
                "contacts_line": " • ".join(p for p in parts if p),
                "has_card": patient_id in self._cards,
                "has_dynamics": len(self._approved_sessions(patient_id)) >= 2,
                "sessions": sessions,
            }

    # ----------------------------------------------------------- session upload
    def _restartable(self, patient_id: str) -> dict[str, Any] | None:
        sessions = self._patient_sessions(patient_id)
        if sessions and sessions[-1]["status"] not in ("drafted", "approved"):
            return sessions[-1]
        return None

    def next_session_number(self, patient_id: str) -> int:
        with self._lock:
            self._patient(patient_id)
            restart = self._restartable(patient_id)
            if restart:
                return restart["number"]
            sessions = self._patient_sessions(patient_id)
            return sessions[-1]["number"] + 1 if sessions else 1

    def add_session(self, patient_id: str, wav_path: str, language: str, session_date: str) -> str:
        if Path(wav_path).suffix.lower() != ".wav":
            raise FacadeError("Потрібен двоканальний .wav")
        if language != "uk":
            raise FacadeError("Підтримується лише українська мова")
        try:
            day = datetime.strptime(session_date, "%Y-%m-%d").date()
        except ValueError:
            raise FacadeError("Некоректна дата сесії") from None
        with self._lock:
            self._patient(patient_id)
            restart = self._restartable(patient_id)
            if restart:  # the doctor repeats the same actions: restart the session from scratch
                restart.update({"date": day, "status": "uploaded", "failed_step": None, "soap": None,
                                "language": language})
                self._progress.pop(restart["session_id"], None)
                if restart["number"] == 1:
                    self._cards.pop(patient_id, None)
                return restart["session_id"]
            sessions = self._patient_sessions(patient_id)
            number = sessions[-1]["number"] + 1 if sessions else 1
            return self._new_session(patient_id, number, day, "uploaded")

    def process_session(self, session_id: str, on_progress: ProgressCallback | None = None) -> None:
        with self._lock:
            session = self._session(session_id)
            if session["status"] != "uploaded":
                raise FacadeError("Сесію вже оброблено")
            self._active.add(session_id)
            self._progress[session_id] = {"done": set(), "running": None, "error": None}
        try:
            for step in PROCESSING_STEPS:
                if step.startswith("s3") and session["number"] != 1:
                    continue
                self._run_step(session_id, step, on_progress)
            with self._lock:
                session["status"] = "drafted"
                session["soap"] = self._new_soap(approved=False)
                if session["number"] == 1:
                    self._cards[session["patient_id"]] = self._new_card(session["patient_id"], approved=False)
        finally:
            with self._lock:
                self._active.discard(session_id)

    def _run_step(self, session_id: str, step: str, on_progress: ProgressCallback | None) -> None:
        stage = _STEP_TO_STAGE.get(step)
        with self._lock:
            self._progress[session_id]["running"] = stage
        if on_progress:
            on_progress(step, "running")
        time.sleep(self._step_delay)
        if self._fail_on == step:
            self._fail_on = None  # fails once; the doctor repeats the actions and it passes
            with self._lock:
                self._sessions[session_id]["failed_step"] = step
                self._progress[session_id].update({"running": None, "error": stage})
            logger.warning("Stub: step %s failed for session %s", step, session_id)
            raise FacadeError(PROCESS_ERROR_MESSAGE)
        with self._lock:
            progress = self._progress[session_id]
            progress["running"] = None
            if stage and not (step == "s3_generate" or step == "s4_generate"):
                progress["done"].add(stage)
            self._sessions[session_id]["failed_step"] = None
        if on_progress:
            on_progress(step, "done")

    def get_processing_state(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._session(session_id)
            finished = session["status"] in ("drafted", "approved")
            progress = self._progress.get(session_id, {"done": set(), "running": None, "error": None})
            failed_stage = progress["error"] or (
                _STEP_TO_STAGE.get(session["failed_step"]) if session["failed_step"] else None
            )
            stages = []
            first_pending_seen = False
            for key in STAGE_KEYS:
                if key == "medical_card" and session["number"] != 1:
                    state = "not_needed"
                elif finished or key in progress["done"]:
                    state = "done"
                elif key == failed_stage:
                    state = "error"
                elif key == progress["running"] or (
                    session_id in self._active and not first_pending_seen
                ):
                    state = "running"
                    first_pending_seen = True
                else:
                    state = "pending"
                stages.append({"key": key, "state": state})
            return {"stages": stages, "error": PROCESS_ERROR_MESSAGE if failed_stage else None,
                    "finished": finished}

    # --------------------------------------------------------------------- SOAP
    def _soap(self, session_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        session = self._session(session_id)
        if not session["soap"]:
            raise FacadeError("Нотатка ще не готова")
        return session, session["soap"]

    def get_soap(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session, soap = self._soap(session_id)
            first = next(s for s in self._patient_sessions(session["patient_id"]) if s["number"] == 1)
            chips = []
            for metric in soap["objective"]["biomarker_refs"]:
                value = session["biomarkers"].get(metric)
                baseline = None if session["number"] == 1 else first["biomarkers"].get(metric)
                arrow = None
                if value is not None and baseline is not None and not math.isclose(value, baseline):
                    arrow = "up" if value > baseline else "down"
                chips.append({"metric": metric, "value": value, "baseline": baseline, "arrow": arrow})
            approved = soap["status"] == "approved"
            return {
                "session_id": session_id, "patient_id": session["patient_id"],
                "patient_name": self._patients[session["patient_id"]]["preferred_name"],
                "number": session["number"], "date": _fmt_date(session["date"]),
                "status": soap["status"], "badge": "approved" if approved else "review",
                "editable": not approved,
                "subjective": {"text": soap["subjective"]["text"],
                               "sources": self._sources(soap["subjective"]["source_segments"])},
                "objective": {"text": soap["objective"]["text"], "chips": chips},
                "assessment": dict(soap["assessment"]),
                "plan": [dict(item) for item in soap["plan"]],
            }

    def _apply_soap_edits(self, soap: dict[str, Any], edits: list[dict[str, Any]]) -> None:
        parsed = []
        for edit in edits:
            match = _SOAP_PATH_RE.match(str(edit.get("path", "")))
            value = edit.get("new_value")
            if not match or not isinstance(value, str):
                raise FacadeError("Не вдалося зберегти правки")
            if match.group(2) is not None and int(match.group(2)) >= len(soap["plan"]):
                raise FacadeError("Не вдалося зберегти правки")
            parsed.append((match, value))
        for match, value in parsed:  # apply only after everything is valid
            if match.group(1):
                soap[match.group(1)]["text"] = value
            else:
                soap["plan"][int(match.group(2))]["text"] = value

    def save_soap(self, session_id: str, edits: list[dict[str, Any]], review_started_at: datetime) -> None:
        with self._lock:
            _, soap = self._soap(session_id)
            if soap["status"] == "approved":
                raise FacadeError("Підтверджені дані змінювати не можна")
            self._apply_soap_edits(soap, edits)

    def approve_soap(self, session_id: str, edits: list[dict[str, Any]], review_started_at: datetime) -> None:
        with self._lock:
            session, soap = self._soap(session_id)
            if soap["status"] == "approved":
                raise FacadeError("Підтверджені дані змінювати не можна")
            self._apply_soap_edits(soap, edits)
            soap["status"] = "approved"
            self._maybe_approve_session(session)

    def _maybe_approve_session(self, session: dict[str, Any]) -> None:
        """Session becomes approved when SOAP is approved (and the card too for session #1)."""
        if not session["soap"] or session["soap"]["status"] != "approved":
            return
        if session["number"] == 1:
            card = self._cards.get(session["patient_id"])
            if card is None or card["status"] != "approved":
                return
        session["status"] = "approved"

    def get_transcript(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._soap(session_id)
        return [
            {"segment_id": index, "speaker": speaker, "start": start, "end": end,
             "time": _mmss(start), "text": text}
            for index, (speaker, start, end, text) in enumerate(_TRANSCRIPT)
        ]

    def get_audio_info(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self._soap(session_id)
        return {"path": self._audio_path, "duration": 1965.0}

    def get_waveform(self, session_id: str) -> list[float]:
        with self._lock:
            self._soap(session_id)
        return [round(0.15 + 0.85 * abs(math.sin(i / 7.0) * math.sin(i / 53.0)), 3) for i in range(900)]

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            session = self._session(session_id)
            siblings = self._patient_sessions(session["patient_id"])
            if session["number"] == 1 and len(siblings) > 1:
                raise FacadeError("Сесію №1 не можна видалити, поки є інші сесії")
            if session["number"] == 1:
                self._cards.pop(session["patient_id"], None)
            del self._sessions[session_id]
            self._active.discard(session_id)
            self._progress.pop(session_id, None)

    # ------------------------------------------------------------- medical card
    def _card(self, patient_id: str) -> dict[str, Any]:
        self._patient(patient_id)
        try:
            return self._cards[patient_id]
        except KeyError:
            raise FacadeError("Медкартки ще немає") from None

    def get_card(self, patient_id: str) -> dict[str, Any]:
        with self._lock:
            card = self._card(patient_id)
            patient = self._patients[patient_id]
            first = self._patient_sessions(patient_id)[0]
            approved = card["status"] == "approved"
            emergency_consent = patient["emergency_consent"]
            fields = [
                {"field_id": field_id, "state": data["state"], "value": data["value"],
                 "contradiction_text": data["contradiction_text"],
                 "sources": self._sources(data["evidence"]),
                 "edited_by_doctor": field_id in card["edited"]}
                for field_id, data in card["fields"].items()
            ]
            return {
                "patient_id": patient_id, "patient_name": patient["preferred_name"],
                "date": _fmt_date(first["date"]), "status": card["status"],
                "badge": "approved" if approved else "review", "editable": not approved,
                "contacts": {
                    "preferred_name": patient["preferred_name"], "birth_date": patient["birth_date"],
                    "age": _age(patient["birth_date"]), "phone": patient["phone"], "email": patient["email"],
                    "preferred_channel": patient["preferred_channel"],
                    "emergency_name": patient["emergency_name"],
                    "emergency_relation": patient["emergency_relation"],
                    "emergency_phone": patient["emergency_phone"],
                    "emergency_consent": None if emergency_consent is None else bool(emergency_consent),
                },
                "fields": fields,
            }

    def _apply_card_edits(self, card: dict[str, Any], edits: list[dict[str, Any]]) -> None:
        checked = []
        for edit in edits:
            field_id = edit.get("path")
            value = edit.get("new_value")
            if field_id not in card["fields"]:
                raise FacadeError("Не вдалося зберегти правки")
            if field_id in BOOL_FIELDS:
                valid = isinstance(value, bool)
            else:
                valid = value is None or isinstance(value, str)
            if not valid:
                raise FacadeError("Не вдалося зберегти правки")
            checked.append((field_id, value))
        for field_id, value in checked:
            card["fields"][field_id]["value"] = value
            card["edited"].add(field_id)

    def save_card(self, patient_id: str, edits: list[dict[str, Any]], review_started_at: datetime) -> None:
        with self._lock:
            card = self._card(patient_id)
            if card["status"] == "approved":
                raise FacadeError("Підтверджені дані змінювати не можна")
            self._apply_card_edits(card, edits)

    def approve_card(self, patient_id: str, edits: list[dict[str, Any]], review_started_at: datetime) -> None:
        with self._lock:
            card = self._card(patient_id)
            if card["status"] == "approved":
                raise FacadeError("Підтверджені дані змінювати не можна")
            self._apply_card_edits(card, edits)
            card["status"] = "approved"
            first = self._patient_sessions(patient_id)[0]
            self._maybe_approve_session(first)

    # ----------------------------------------------------------------- dynamics
    def _approved_sessions(self, patient_id: str) -> list[dict[str, Any]]:
        return [s for s in self._patient_sessions(patient_id) if s["status"] == "approved"]

    def get_dynamics(self, patient_id: str) -> dict[str, Any]:
        with self._lock:
            self._patient(patient_id)
            sessions = self._approved_sessions(patient_id)
            if len(sessions) < 2:
                return {"available": False, "sessions_label": "", "trends": [], "summary_text": ""}
            numbers = [s["number"] for s in sessions]
            trends = []
            for metric in _METRIC_SEED:
                values = [s["biomarkers"][metric] for s in sessions]
                slope = statistics.linear_regression(numbers, values).slope
                trends.append({
                    "metric": metric,
                    "values": [{"session_number": n, "value": v} for n, v in zip(numbers, values)],
                    "slope": round(slope, 4),
                    "direction": _direction(slope, values[0]),
                })
            return {
                "available": True,
                "sessions_label": f"{numbers[0]}–{numbers[-1]}",
                "trends": trends,
                "summary_text": self._summary(trends),
            }

    @staticmethod
    def _summary(trends: list[dict[str, Any]]) -> str:
        """Template summary built from the directions (S5Out has no text)."""
        phrases = {"up": "зростає", "down": "зменшується", "stable": "стабільна"}
        parts = [f"{_METRIC_TITLES.get(t['metric'], t['metric'])} — {phrases[t['direction']]}" for t in trends]
        return "Порівняно з першим візитом: " + "; ".join(parts) + "."
