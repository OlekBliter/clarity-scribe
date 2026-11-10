"""Тимчасовий екран-заглушка. Кожен розробник замінює його своїм екраном."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLabel, QVBoxLayout

from src.app.ui import metrics, strings
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.buttons import secondary_button


class PlaceholderScreen(BaseScreen):
    def __init__(self, title: str, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        layout.setSpacing(metrics.SPACING)
        heading = QLabel(title)
        heading.setObjectName("ScreenTitle")
        self._info = QLabel(strings.PLACEHOLDER_HINT)
        self._info.setObjectName("Muted")
        back = secondary_button(strings.BACK)
        back.clicked.connect(router.back)
        layout.addWidget(heading)
        layout.addWidget(self._info)
        layout.addWidget(back)
        layout.addStretch(1)

    def on_open(self, **params: Any) -> None:
        extra = f" · параметри: {params}" if params else ""
        self._info.setText(strings.PLACEHOLDER_HINT + extra)
