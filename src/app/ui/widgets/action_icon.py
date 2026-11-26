"""Small vector actions with accessible labels and theme-aware strokes."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QToolButton

from src.app.ui import metrics


class ActionIcon(QToolButton):
    def __init__(self, kind: str, caption: str, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName("CardIconAction")
        self.setFixedSize(metrics.ROW_MENU_SIZE, metrics.ROW_MENU_SIZE)
        self.setToolTip(caption)
        self.setAccessibleName(caption)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate((self.width() - 24) / 2, (self.height() - 24) / 2)
        painter.setPen(QPen(self.palette().buttonText().color(), 1.7,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        if self.kind == "back":
            painter.drawLine(5, 12, 19, 12)
            painter.drawLine(5, 12, 11, 6)
            painter.drawLine(5, 12, 11, 18)
        elif self.kind == "more":
            painter.setBrush(painter.pen().color())
            for x in (5, 12, 19):
                painter.drawEllipse(QRectF(x - 1.5, 10.5, 3, 3))
        elif self.kind == "lock":
            painter.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
            painter.drawArc(QRectF(8, 3, 8, 14), 0, 180 * 16)
            painter.drawLine(12, 14, 12, 17)
