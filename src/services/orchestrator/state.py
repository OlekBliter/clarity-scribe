from enum import Enum
from unittest import case


class Step(str, Enum):
    S1 = "S1"
    S6_SANITIZE = "S6_SANITIZE"
    S2 = "S2"
    S3_GENERATE = "S3_GENERATE"
    S3_RESTORE = "S3_RESTORE"
    S4_GENERATE = "S4_GENERATE"
    S4_RESTORE = "S4_RESTORE"
    MARK_DRAFTED = "MARK_DRAFTED"

def next_step(session: dict, card, note) -> Step | None:
    session_status_transitions = {
        'drafted': None,
        'approved': None,
        'transcribed': Step.S6_SANITIZE,
        'uploaded': Step.S1,
        'sanitized': Step.S2
    }

    if session['status'] in session_status_transitions.keys():
        return session_status_transitions[session.status]

    is_first_session = (session['session_number'] == 1)
    if is_first_session and card is None and session['status'] == 'analyzed':
        return Step.S3_GENERATE

    if card is not None and card.status == "generated":
        return Step.S3_RESTORE

    card_ready = (card is not None and card.status == "draft") if is_first_session else True

    if session['status'] == "analyzed" and card_ready and note is None:
        return Step.S4_GENERATE

    if note is not None and note.status == "generated":
        return Step.S4_RESTORE

    if note is not None and note.status == "draft" and card_ready:
        return Step.MARK_DRAFTED

    return None

def session_badge(session: dict, is_processing: bool) -> str | None:
    if session['failed_step'] is not None:
        return 'Помилка'

    status = session['status']

    match status:
        case 'approved':
            return 'Підтверджено'
        case 'drafted':
            return 'Чекає на розгляд'

    if is_processing:
        return 'Обробка запису'

    return None

def patient_badge(sessions: list[dict], active_ids: set[str]) -> str | None:
    if not sessions:
        return None

    active_ids = active_ids or set()

    if any(s.get('failed_step') for s in sessions):
        return 'Помилка'

    if any(s['status'] == 'drafted' for s in sessions):
        return 'Чекає розгляду'

    if any(s['session_id'] in active_ids for s in sessions):
        return 'Обробка запису'

    if all(s['status'] == 'approved' for s in sessions):
        return 'Підтверджено'

    return None

def describe_stages(
    session: dict,
    card: dict | None = None,
    note: dict | None = None,
) -> list[dict]:
    stage_names = [
        "Транскрибація",
        "Анонімізація тексту",
        "Біомаркери голосу",
        "Медкартка",
        "SOAP-нотатка",
    ]

    status_order = {
        "uploaded": 0,
        "transcribed": 1,
        "sanitized": 2,
        "analyzed": 3,
        "drafted": 5,
        "approved": 5,
    }

    step_to_stage = {
        Step.S1: 0,
        Step.S6_SANITIZE: 1,
        Step.S2: 2,
        Step.S3_GENERATE: 3,
        Step.S3_RESTORE: 3,
        Step.S4_GENERATE: 4,
        Step.S4_RESTORE: 4,
        Step.MARK_DRAFTED: 4,
    }

    status = session["status"]
    session_number = session["session_number"]
    failed_step = session.get("failed_step")

    stages = [
        {"name": name, "status": "Очікує"}
        for name in stage_names
    ]

    # Mark completed processing stages
    progress = status_order[status]

    for i in range(min(progress, 3)):
        stages[i]["status"] = "Готово"

    # Medical card is generated only for the first session
    if session_number >= 2:
        stages[3]["status"] = "Не потрібно"
    elif status in ("drafted", "approved") or (
            card is not None
            and card["status"] in ("draft", "approved")
    ):
        stages[3]["status"] = "Готово"

    # SOAP note is ready after restore
    if status in ("drafted", "approved") or (
            note is not None
            and note["status"] in ("draft", "approved")
    ):
        stages[4]["status"] = "Готово"

    # Show the failed stage
    if failed_step is not None:
        failed_stage = step_to_stage.get(failed_step)

        if failed_stage is not None:
            stages[failed_stage]["status"] = "Помилка"

    return stages
