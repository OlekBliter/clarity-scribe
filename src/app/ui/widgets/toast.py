"""Спливаюче повідомлення знизу вікна. Створюється один раз у MainWindow."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from src.app.ui import metrics


class Toast(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 16, 10)
        self._label = QLabel()
        self._label.setObjectName("ToastText")
        row.addWidget(self._label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, ms: int = metrics.TOAST_MS) -> None:
        self._label.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - metrics.TOAST_BOTTOM_OFFSET
        self.move(max(x, 0), max(y, 0))
