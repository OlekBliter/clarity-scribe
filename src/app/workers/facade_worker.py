"""Виклик методів фасаду поза головним потоком.

Використання (зазвичай через BaseScreen.call):
    run_async(facade.list_patients, "мел", owner=self, on_success=self._render)

Колбеки on_success / on_error завжди виконуються в головному потоці.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

log = logging.getLogger(__name__)


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(object)


class FacadeWorker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.setAutoDelete(False)  # тримає relay, щоб сигнали не загубилися
        self._fn, self._args, self._kwargs = fn, args, kwargs
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # межа потоку: помилка не має зникнути мовчки
            log.exception("Помилка у фоновому виклику фасаду")
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)


class _Relay(QObject):
    """Живе в головному потоці й перекидає результат у колбеки."""

    def __init__(self, worker: FacadeWorker, on_success, on_error, parent: QObject) -> None:
        super().__init__(parent)
        self._worker = worker
        self._on_success, self._on_error = on_success, on_error
        worker.signals.finished.connect(self._ok)
        worker.signals.failed.connect(self._fail)

    @Slot(object)
    def _ok(self, result: object) -> None:
        if self._on_success:
            self._on_success(result)
        self.deleteLater()

    @Slot(object)
    def _fail(self, exc: object) -> None:
        if self._on_error:
            self._on_error(exc)
        self.deleteLater()


def run_async(
    fn: Callable[..., Any],
    *args: Any,
    owner: QObject,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[BaseException], None] | None = None,
) -> None:
    worker = FacadeWorker(fn, *args)
    _Relay(worker, on_success, on_error, parent=owner)
    QThreadPool.globalInstance().start(worker)
