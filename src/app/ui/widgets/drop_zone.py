"""Зона вибору файла: перетягування або кнопка «Додати файл».

Сигнали:
    file_selected(path)   файл обрано (шлях до файла)
    file_cleared()        лікар натиснув «Скасувати»
    file_rejected(text)   файл не підходить (текст для Toast)

Окремий запуск для перегляду:  python -m src.app.ui.widgets.drop_zone
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.app.ui import metrics, strings
from src.app.ui.qt_helpers import repolish
from src.app.ui.widgets.buttons import outline_button, secondary_button

_BYTES_IN_MB = 1024 * 1024


class DropZone(QFrame):
    file_selected = Signal(str)
    file_cleared = Signal()
    file_rejected = Signal(str)

    def __init__(self, extensions: tuple[str, ...] = (".wav",), parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self._extensions = tuple(e.lower() for e in extensions)
        self._path: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        layout.setSpacing(metrics.SPACING)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(strings.DROPZONE_TITLE)
        title.setObjectName("CardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel(strings.DROPZONE_HINT)
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(hint)

        self._file_row = QWidget()
        row = QHBoxLayout(self._file_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chip = QLabel()
        self._chip.setObjectName("FileChip")
        clear_btn = secondary_button(strings.DROPZONE_CLEAR)
        clear_btn.clicked.connect(self.clear)
        row.addWidget(self._chip)
        row.addWidget(clear_btn)
        self._file_row.hide()
        layout.addWidget(self._file_row)

        pick = outline_button(strings.DROPZONE_BUTTON)
        pick.clicked.connect(self._choose_file)
        layout.addWidget(pick, alignment=Qt.AlignmentFlag.AlignCenter)

    # ---- публічне API ----
    @property
    def path(self) -> str | None:
        return self._path

    def clear(self) -> None:
        if self._path is None:
            return
        self._path = None
        self._file_row.hide()
        self.file_cleared.emit()

    # ---- вибір файла ----
    def _choose_file(self) -> None:
        masks = " ".join(f"*{ext}" for ext in self._extensions)
        path, _ = QFileDialog.getOpenFileName(
            self, strings.DROPZONE_DIALOG_TITLE, "", f"{strings.DROPZONE_FILTER} ({masks})")
        if path:
            self._accept(path)

    def _accept(self, path: str) -> bool:
        if Path(path).suffix.lower() not in self._extensions:
            self.file_rejected.emit(
                strings.DROPZONE_BAD_TYPE.format(types=", ".join(self._extensions)))
            return False
        self._path = path
        size_mb = os.path.getsize(path) / _BYTES_IN_MB if os.path.exists(path) else 0.0
        self._chip.setText(strings.DROPZONE_FILE_FMT.format(name=Path(path).name, size_mb=size_mb))
        self._file_row.show()
        self.file_selected.emit(path)
        return True

    # ---- drag-and-drop ----
    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", "true" if active else "false")
        repolish(self)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._set_drag_active(False)
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._set_drag_active(False)
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self._accept(urls[0].toLocalFile())
            event.acceptProposedAction()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    from src.app.ui.theme.loader import load_theme

    app = QApplication(sys.argv)
    load_theme(app)
    zone = DropZone()
    zone.file_selected.connect(lambda p: print("обрано:", p))
    zone.file_cleared.connect(lambda: print("скасовано"))
    zone.file_rejected.connect(lambda t: print("відхилено:", t))
    zone.resize(460, 240)
    zone.show()
    raise SystemExit(app.exec())
