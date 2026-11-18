"""Pure formatters shared by ``impl.py`` and ``views.py``.

Every function takes plain values and returns plain values: no database,
no Orchestrator, no systems. Only the standard library is imported.
The output formats match ``stub.py`` and the contract in ``facade.py``.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

_METRIC_TITLES = {
    "pause_ratio": "тривалість пауз",
    "speech_rate_syllables_per_sec": "темп мовлення",
    "f0_variability_sd": "варіативність F0",
    "psychomotor_retardation_index": "індекс психомоторної загальмованості",
}
_DIRECTION_PHRASES = {"up": "зростає", "down": "зменшується", "stable": "стабільна"}

def fmt_date(value: date) -> str:
    """Format a date the way the UI shows it: ``02.10.2026``."""
    return value.strftime("%d.%m.%Y")


def mmss(seconds: float) -> str:
    """Format a duration in seconds as ``mm:ss`` (472 -> ``07:52``)."""
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def sessions_word(count: int) -> str:
    """Return the Ukrainian plural form: 1 сесія, 2-4 сесії, 5+ сесій."""
    if count % 100 in range(11, 15):
        return "сесій"
    last = count % 10
    if last == 1:
        return "сесія"
    return "сесії" if last in (2, 3, 4) else "сесій"


def age(birth_date: str | None) -> int | None:
    """Return the age in full years, or ``None`` if the date is missing or invalid.

    Accepts ``DD.MM.YYYY`` (as typed by the doctor) and ``YYYY-MM-DD``.
    """
    if not birth_date:
        return None
    for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            born = datetime.strptime(birth_date, pattern).date()
        except ValueError:
            continue
        today = date.today()
        # Subtract one year if this year's birthday has not come yet.
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return None


def patients_subtitle(patient: dict[str, Any]) -> str:
    """Build the patient-row subtitle: ``5 сесій • остання 02.10.2026``.

    Args:
        patient: A row from ``PatientsRepo.list_with_sessions`` with
            ``sessions_count`` and ``last_session_date`` (``YYYY-MM-DD``).

    Returns:
        The subtitle, or ``Немає сесій`` if the patient has no sessions.
    """
    count = patient["sessions_count"]
    if count == 0:
        return "Немає сесій"
    last = date.fromisoformat(patient["last_session_date"])
    return f"{count} {sessions_word(count)} • остання {fmt_date(last)}"

def sessions_label(numbers: list[int]) -> str:
    """``1–5`` for a range, ``3`` for a single session, ``""`` for none."""
    if not numbers:
        return ""
    first, last = min(numbers), max(numbers)
    return str(first) if first == last else f"{first}–{last}"


def trend_direction(slope: float | None, baseline: float) -> str:
    """``stable`` if |slope| < 5% of the baseline (0.05 when the baseline is 0)."""
    if slope is None:
        return "stable"
    threshold = 0.05 * abs(baseline) if baseline != 0 else 0.05
    if abs(slope) < threshold:
        return "stable"
    return "up" if slope > 0 else "down"


def dynamics_summary(trends: list[dict[str, Any]]) -> str:
    """Template sentence built from the trend directions."""
    parts = [
        f"{_METRIC_TITLES.get(t['metric'], t['metric'])} — {_DIRECTION_PHRASES[t['direction']]}"
        for t in trends
    ]
    return "Порівняно з першим візитом: " + "; ".join(parts) + "."