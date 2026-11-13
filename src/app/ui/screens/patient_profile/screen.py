"""Профіль пацієнта.

Фасад: get_patient_profile(patient_id) ->
  {"patient_id", "name", "contacts_line", "has_card", "has_dynamics",
   "sessions": [{"session_id", "number", "date", "subtitle", "badge", "is_ready"}]}
  is_ready=True відкриває SOAP, False відкриває екран обробки (ADD_SESSION із session_id).

РОБОЧА МІНІМАЛЬНА ВЕРСІЯ: навігація вже працює, щоб усі могли дійти до своїх
екранів. Верстку за макетом, кнопку «Видалити» (delete_patient) і стани
loading/empty/error доводить виконавець задачі V4.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from src.app.ui import metrics, strings
from src.app.ui.qt_helpers import clear_layout
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.badge import badge_for
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import outline_button, primary_button
from src.app.ui.widgets.card import ListItemCard


class PatientProfileScreen(BaseScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._patient_id: str | None = None
        self._has_dynamics: bool | None = None
        self._request_id = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)

        self._crumb = Breadcrumb()
        self._title = QLabel()
        self._title.setObjectName("ScreenTitle")
        self._contacts = QLabel()
        self._contacts.setObjectName("Subtitle")
        root.addWidget(self._crumb)
        root.addWidget(self._title)
        root.addWidget(self._contacts)

        actions = QHBoxLayout()
        self._add = primary_button(strings.PROFILE_ADD_SESSION)
        self._card = outline_button(strings.PROFILE_CARD)
        self._dynamics = outline_button(strings.PROFILE_DYNAMICS)
        self._add.clicked.connect(lambda: self.router.go(Route.ADD_SESSION, patient_id=self._patient_id))
        self._card.clicked.connect(lambda: self.router.go(Route.MEDICAL_CARD, patient_id=self._patient_id))
        self._dynamics.clicked.connect(self._open_dynamics)
        for btn in (self._add, self._card, self._dynamics):
            actions.addWidget(btn)
        actions.addStretch(1)
        root.addLayout(actions)

        heading = QLabel(strings.PROFILE_SESSIONS)
        heading.setObjectName("SectionTitle")
        root.addWidget(heading)
        self._sessions = QVBoxLayout()
        self._sessions.setSpacing(metrics.SPACING)
        self._sessions.setAlignment(Qt.AlignmentFlag.AlignTop)
        holder = QWidget()
        holder.setLayout(self._sessions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(holder)
        root.addWidget(scroll, stretch=1)

    def on_open(self, **params: Any) -> None:
        self._patient_id = params["patient_id"]
        self._has_dynamics = None
        self._request_id += 1
        request_id = self._request_id
        self.call(self.facade.get_patient_profile, self._patient_id,
                  on_success=lambda profile: self._render_current(profile, request_id))

    def _render_current(self, profile: dict, request_id: int) -> None:
        if request_id == self._request_id:
            self._render(profile)

    def _render(self, profile: dict) -> None:
        self._crumb.set_path([strings.NAV_PATIENTS, profile["name"]])
        self._title.setText(profile["name"])
        self._contacts.setText(profile["contacts_line"])
        self._card.setEnabled(profile["has_card"])
        self._has_dynamics = profile["has_dynamics"]
        self._contacts.setVisible(bool(profile["contacts_line"]))
        clear_layout(self._sessions)
        for s in profile["sessions"]:
            text, variant = badge_for(s["badge"])
            row = ListItemCard(strings.SESSION_ROW_TITLE.format(number=s["number"], date=s["date"]),
                               s["subtitle"], text, variant)
            row.clicked.connect(lambda s=s: self._open_session(s))
            self._sessions.addWidget(row)

    def _open_dynamics(self) -> None:
        if self._has_dynamics is False:
            self.window().toast.show_message(strings.DYNAMICS_NEEDS_SESSIONS)
        elif self._patient_id is not None:
            self.router.go(Route.DYNAMICS, patient_id=self._patient_id)

    def _open_session(self, s: dict) -> None:
        if s["is_ready"]:
            self.router.go(Route.SESSION, patient_id=self._patient_id, session_id=s["session_id"])
        else:
            self.router.go(Route.ADD_SESSION, patient_id=self._patient_id, session_id=s["session_id"])
