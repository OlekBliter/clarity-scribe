"""Базовий клас екрана: фасад, роутер і безпечний виклик фасаду у фоні."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import QWidget

from src.app.ui.errors import show_error
from src.app.ui.router import Router
from src.app.workers.facade_worker import run_async


class BaseScreen(QWidget):
    def __init__(self, facade, router: Router, parent=None) -> None:
        super().__init__(parent)
        self.facade = facade
        self.router = router

    def on_open(self, **params: Any) -> None:
        """Викликається роутером щоразу, коли екран показують."""

    def call(self, fn: Callable[..., Any], *args: Any,
             on_success: Callable[[Any], None],
             on_error: Callable[[BaseException], None] | None = None) -> None:
        """Виклик методу фасаду в потоці. Без on_error помилка йде в Toast."""
        run_async(fn, *args, owner=self, on_success=on_success,
                  on_error=on_error or self._default_error)

    def _default_error(self, exc: BaseException) -> None:
        show_error(self, exc)
