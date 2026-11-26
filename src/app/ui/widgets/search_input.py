"""Поле пошуку з debounce: сигнал спрацьовує, коли лікар зупинився друкувати."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLineEdit

from src.app.ui import metrics


class SearchInput(QLineEdit):
    search_changed = Signal(str)

    def __init__(self, placeholder: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchInput")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setMaximumWidth(metrics.SEARCH_MAX_WIDTH)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(metrics.SEARCH_DEBOUNCE_MS)
        self._timer.timeout.connect(lambda: self.search_changed.emit(self.text().strip()))
        self.textChanged.connect(lambda _: self._timer.start())
