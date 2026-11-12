"""Clickable reference to a transcript segment."""
from __future__ import annotations


from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget

from app.ui import strings as S


class SourceChip(QPushButton):
    """Timestamp reference.

    Signals:
        segment_clicked(int): Identifier of the segment activated by the user.
    """

    segment_clicked = Signal(int)

    def __init__(
        self, time_text: str, segment_id: int, parent: QWidget | None = None
    ) -> None:
        """Initialize the chip.

        Args:
            time_text: Timestamp, with or without surrounding brackets.
            segment_id: Identifier emitted on activation.
            parent: Owning widget.
        """
        super().__init__(parent)
        self._segment_id = segment_id
        self.setObjectName("SourceChip")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(S.SOURCE_TIME.format(time=time_text.strip().strip("[]")))
        self.clicked.connect(self._activate)

    def _activate(self, checked: bool = False) -> None:
        """Emit the segment identifier; ignore the button's checked state."""
        self.segment_clicked.emit(self._segment_id)
