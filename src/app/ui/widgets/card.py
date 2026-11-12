"""Картки: звичайна та клікабельний рядок списку (пацієнт / сесія)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from src.app.ui import metrics
from src.app.ui.widgets.badge import Badge


class Card(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")


class ListItemCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, subtitle: str = "", badge_text: str = "",
                 badge_variant: str = "neutral", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PatientCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(*(metrics.CARD_PADDING,) * 4)

        texts = QVBoxLayout()
        texts.setSpacing(metrics.SPACING_SMALL)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("Muted")
        texts.addWidget(self.title_label)
        texts.addWidget(self.subtitle_label)
        row.addLayout(texts, stretch=1)

        self.badge = Badge(badge_text, badge_variant, parent=self)
        row.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.badge.setVisible(bool(badge_text))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
