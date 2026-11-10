"""Список пацієнтів (еталонний екран: за ним робимо решту)."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.app.ui import metrics, strings
from src.app.ui.qt_helpers import clear_layout
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.buttons import primary_button
from src.app.ui.widgets.card import ListItemCard
from src.app.ui.widgets.search_input import SearchInput


def _to_row(p: dict) -> dict:
    """Єдине місце, де UI знає формат відповіді list_patients.
    Звірити ключі зі stub.py і поправити тут, якщо відрізняються."""
    badge = p.get("badge") or {}
    if isinstance(badge, str):
        badge = {"text": badge}
    return {
        "id": p.get("id"),
        "title": p.get("name") or strings.NO_NAME,
        "subtitle": p.get("subtitle", ""),
        "badge_text": badge.get("text", ""),
        "badge_variant": badge.get("variant", "neutral"),
    }


class PatientsScreen(BaseScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._request_id = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)

        header = QHBoxLayout()
        title = QLabel(strings.PATIENTS_TITLE)
        title.setObjectName("ScreenTitle")
        header.addWidget(title)
        header.addStretch(1)
        add = primary_button("+  " + strings.PATIENTS_ADD)
        add.clicked.connect(lambda: self.router.go(Route.NEW_PATIENT))
        header.addWidget(add)
        root.addLayout(header)

        self._search = SearchInput(strings.PATIENTS_SEARCH_PLACEHOLDER)
        self._search.search_changed.connect(self._load)
        root.addWidget(self._search)

        self._list = QVBoxLayout()
        self._list.setSpacing(metrics.SPACING)
        self._list.setAlignment(Qt.AlignmentFlag.AlignTop)
        holder = QWidget()
        holder.setLayout(self._list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(holder)
        root.addWidget(scroll, stretch=1)

    def on_open(self, **params: Any) -> None:
        self._load(self._search.text().strip())

    def _load(self, query: str = "") -> None:
        self._request_id += 1
        rid = self._request_id
        self.call(self.facade.list_patients, query,
                  on_success=lambda items: self._render(items, rid))

    def _render(self, items: list[dict], rid: int) -> None:
        if rid != self._request_id:  # застарілу відповідь ігноруємо
            return
        clear_layout(self._list)
        if not items:
            empty = QLabel(strings.PATIENTS_EMPTY)
            empty.setObjectName("Muted")
            self._list.addWidget(empty)
            return
        for raw in items:
            row = _to_row(raw)
            card = ListItemCard(row["title"], row["subtitle"],
                                row["badge_text"], row["badge_variant"])
            card.clicked.connect(lambda pid=row["id"]: self.router.go(
                Route.PATIENT_PROFILE, patient_id=pid))
            self._list.addWidget(card)
