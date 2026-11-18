"""Clickable reference to a transcript segment."""
from __future__ import annotations


from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QMessageBox, QMenu, QPushButton, QSizePolicy, QWidget

from src.app.ui import strings as S


class SourceChip(QPushButton):
    """Timestamp reference.

    Signals:
        segment_clicked(int): Identifier of the segment activated by the user.
    """

    segment_clicked = Signal(int)
    remove_requested = Signal(int)

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
        self._removable = False
        self.setObjectName("SourceChip")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(S.SOURCE_TIME.format(time=time_text.strip().strip("[]")))
        self.clicked.connect(self._activate)

    def _activate(self, checked: bool = False) -> None:
        """Emit the segment identifier; ignore the button's checked state."""
        self.segment_clicked.emit(self._segment_id)

    def set_removable(self, removable: bool) -> None:
        self._removable = removable
        if removable:
            self.setToolTip(self.toolTip() + "\n" + S.SOURCE_REMOVE_HINT)

    def contextMenuEvent(self, event) -> None:
        if not self._removable:
            event.ignore()
            return
        menu = QMenu(self)
        menu.setObjectName("SourceMenu")
        remove = menu.addAction(S.SOURCE_REMOVE)
        if menu.exec(event.globalPos()) == remove:
            dialog = QMessageBox(self)
            dialog.setWindowTitle(S.SOURCE_REMOVE)
            dialog.setText(S.SOURCE_CONFIRM_REMOVE.format(time=self.text().strip("[]")))
            accept = dialog.addButton(S.SOURCE_REMOVE, QMessageBox.ButtonRole.DestructiveRole)
            accept.setObjectName("DeleteText")
            cancel = dialog.addButton(S.CANCEL, QMessageBox.ButtonRole.RejectRole)
            dialog.setDefaultButton(cancel)
            dialog.setEscapeButton(cancel)
            dialog.exec()
            if dialog.clickedButton() is accept:
                self.remove_requested.emit(self._segment_id)
        event.accept()
