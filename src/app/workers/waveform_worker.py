"""Run expensive facade waveform extraction outside the GUI thread."""
from collections.abc import Callable
from PySide6.QtCore import QObject
from src.app.workers.facade_worker import run_async


def load_waveform(
    get_waveform: Callable[[str], list[float]],
    session_id: str,
    *,
    owner: QObject,
    on_success: Callable[[list[float]], None],
    on_error: Callable[[BaseException], None],
) -> None:
    """Schedule extraction using the project's GUI-thread callback relay.

    Args:
        get_waveform: Bound facade method; no audio work runs in the GUI thread.
        session_id: Session whose peaks should be extracted.
        owner: QObject controlling the callback lifetime.
        on_success: Receives normalized peaks in the GUI thread.
        on_error: Receives extraction failures in the GUI thread.
    """
    run_async(get_waveform, session_id, owner=owner,
              on_success=on_success, on_error=on_error)
