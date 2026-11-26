"""Хлібні крихти: Breadcrumb().set_path(["Пацієнти", "Мельник Олена"])."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel


class Breadcrumb(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Breadcrumb")

    def set_path(self, parts: list[str]) -> None:
        self.setText(" / ".join(parts))
