"""Показ помилок лікарю. FacadeError.text вже зрозумілий, не переписуємо."""
from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

from src.app.ui import strings

log = logging.getLogger(__name__)


def show_error(widget: QWidget, error: BaseException | str) -> None:
    text = str(error) or strings.ERROR_GENERIC
    log.warning("UI error: %r", error)
    toast = getattr(widget.window(), "toast", None)
    if toast is not None:
        toast.show_message(text)