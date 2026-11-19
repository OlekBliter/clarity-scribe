"""Список пацієнтів (еталонний екран: за ним робимо решту).

Фасад: list_patients(query) ->
  [{"patient_id", "name", "subtitle", "badge": review|approved|processing|error|None}]
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.app.ui import metrics, strings
from src.app.ui.qt_helpers import clear_layout
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.badge import badge_for
from src.app.ui.widgets.buttons import primary_button
from src.app.ui.widgets.card import ListItemCard
from src.app.ui.widgets.confirm import confirm_destructive
from src.app.ui.errors import show_error
from src.app.ui.widgets.search_input import SearchInput


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
        for p in items:
            text, variant = badge_for(p.get("badge"))
            name = p.get("name") or strings.NO_NAME
            card = ListItemCard(
                name, p.get("subtitle", ""), text, variant,
                actions=[(strings.ROW_MENU_DELETE,
                          lambda pid=p["patient_id"], n=name: self._confirm_delete(pid, n))])
            card.clicked.connect(lambda pid=p["patient_id"]: self.router.go(
                Route.PATIENT_PROFILE, patient_id=pid))
            self._list.addWidget(card)

    def _confirm_delete(self, patient_id: str, name: str) -> None:
        """Видалення пацієнта з меню «⋯» рядка: підтвердження, фасад, оновлення списку."""
        if not confirm_destructive(
            self, strings.PATIENT_ROW_DELETE_TITLE,
            strings.PROFILE_DELETE_TEXT.format(name=name), strings.PROFILE_DELETE_CONFIRM,
        ):
            return
        self.call(self.facade.delete_patient, patient_id,
                  on_success=lambda _r=None: self._load(self._search.text().strip()),
                  on_error=lambda err: show_error(self, err))
