"""Бейдж стану. Варіанти відповідають QSS: QLabel#Badge[variant="..."]."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from src.app.ui import strings
from src.app.ui.qt_helpers import set_variant

VARIANTS = {"success", "warning", "info", "danger", "neutral"}

# Значення badge з фасаду -> (текст, variant). Єдине місце мапінгу.
_BADGE_KINDS = {
    "review": (strings.BADGE_REVIEW, "warning"),
    "approved": (strings.BADGE_APPROVED, "success"),
    "processing": (strings.BADGE_PROCESSING, "info"),
    "error": (strings.BADGE_ERROR, "danger"),
}


def badge_for(kind: str | None) -> tuple[str, str]:
    """('Чекає на перегляд', 'warning') для 'review'; ('', 'neutral') якщо бейджа немає."""
    return _BADGE_KINDS.get(kind or "", ("", "neutral"))


class Badge(QLabel):
    def __init__(self, text: str = "", variant: str = "neutral", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Badge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set_variant(variant)

    @classmethod
    def from_kind(cls, kind: str | None, parent=None) -> "Badge":
        text, variant = badge_for(kind)
        badge = cls(text, variant, parent)
        badge.setVisible(bool(text))
        return badge

    def set_variant(self, variant: str) -> None:
        set_variant(self, variant if variant in VARIANTS else "neutral")
