"""Width-aware, bounded text previews."""
from PySide6.QtCore import QEvent, QPointF, QSize, Qt
from PySide6.QtGui import QPainter, QTextLayout, QTextOption
from PySide6.QtWidgets import QWidget, QSizePolicy
from src.app.ui import metrics as M


class TextPreview(QWidget):
    """Reserve a text-only area and elide the final visible line."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._text = " ".join(text.split())
        self.setObjectName("MedcardPreview")
        self.setAccessibleName(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.fontMetrics().lineSpacing() * M.MEDCARD_PREVIEW_LINES)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.setFixedHeight(self.fontMetrics().lineSpacing() * M.MEDCARD_PREVIEW_LINES)
            self.updateGeometry()

    def sizeHint(self) -> QSize:
        return QSize(M.MEDCARD_SKELETON_WIDTH, self.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        layout = QTextLayout(self._text, self.font())
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        lines = []
        for index in range(M.MEDCARD_PREVIEW_LINES):
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(1, self.width()))
            line.setPosition(QPointF(0, index * self.fontMetrics().lineSpacing()))
            lines.append(line)
        layout.endLayout()
        for index, line in enumerate(lines):
            if index == M.MEDCARD_PREVIEW_LINES - 1:
                rest = self._text[line.textStart():]
                text = self.fontMetrics().elidedText(rest, Qt.TextElideMode.ElideRight, self.width())
                painter.drawText(QPointF(0, line.y() + self.fontMetrics().ascent()), text)
            else:
                line.draw(painter, QPointF(0, 0))
