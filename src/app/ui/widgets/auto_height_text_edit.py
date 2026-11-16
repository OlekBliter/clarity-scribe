"""Plain-text editor sized to its document inside an outer scroll area."""
from __future__ import annotations

import math
from PySide6.QtCore import QSizeF, Qt, QTimer
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QTextEdit, QWidget
from src.app.ui import metrics as M


class AutoHeightTextEdit(QTextEdit):
    """Grow with wrapped content instead of introducing an inner scrollbar."""

    def __init__(self, text: str, editable: bool, parent: QWidget | None = None) -> None:
        """Create a plain-text editor and watch document layout changes."""
        super().__init__(parent)
        self.setObjectName("SoapEditor")
        self.setAcceptRichText(False)
        self.setReadOnly(not editable)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self.setPlainText(text)
        QTimer.singleShot(0, self._fit)

    def _fit(self, size: QSizeF | None = None) -> None:
        """Account for document height, frame, and styled viewport margins."""
        height = math.ceil(self.document().documentLayout().documentSize().height())
        chrome = max(0, self.height() - self.viewport().height())
        self.setFixedHeight(max(M.SOAP_EDITOR_MIN_HEIGHT, height + chrome))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute height when wrapping changes after a width adjustment."""
        super().resizeEvent(event)
        self._fit()
