"""Показ помилок лікарю. FacadeError.text вже зрозумілий, не переписуємо."""
from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

from src.app.ui import strings

from src.services.facade import FacadeError

log = logging.getLogger(__name__)


def error_message(error: BaseException | str) -> str:
    if isinstance(error, (str, FacadeError)):
        return str(error) or strings.ERROR_GENERIC
    return strings.ERROR_GENERIC


def show_error(widget: QWidget, error: BaseException | str) -> None:
    text = error_message(error)
    log.warning("UI error: %s", type(error).__name__)
    toast = getattr(widget.window(), "toast", None)
    if toast is not None:
        toast.show_message(text)