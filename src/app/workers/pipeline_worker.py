"""Запуск process_session у фоновому потоці з сигналами прогресу.

process_session синхронний і довгий, тож без потоку вікно зависне.

    worker = PipelineWorker(self.facade, session_id, parent=self)
    worker.progress.connect(self._on_progress)    # (step, state)
    worker.succeeded.connect(self._on_done)
    worker.failed.connect(self._on_failed)        # FacadeError з готовим текстом
    worker.start()

Тримайте посилання на worker (self._worker = worker), поки він працює.
Сигнали приходять у головний потік, з ними можна безпечно чіпати віджети.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class PipelineWorker(QThread):
    progress = Signal(str, str)   # (step, state): state = "running" | "done"
    succeeded = Signal()
    failed = Signal(object)       # виняток (зазвичай FacadeError)

    def __init__(self, facade, session_id: str, parent=None) -> None:
        super().__init__(parent)
        self._facade = facade
        self._session_id = session_id

    def run(self) -> None:
        try:
            self._facade.process_session(self._session_id, on_progress=self._on_progress)
        except Exception as exc:  # межа потоку: помилка не має зникнути мовчки
            log.exception("process_session failed for %s", self._session_id)
            self.failed.emit(exc)
        else:
            self.succeeded.emit()

    def _on_progress(self, step: str, state: str) -> None:
        self.progress.emit(step, state)  # викликається з потоку воркера
