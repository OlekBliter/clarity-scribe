"""Профіль пацієнта.

Фасад: get_patient_profile(patient_id) ->
  {"patient_id", "name", "contacts_line", "has_card", "has_dynamics",
   "sessions": [{"session_id", "number", "date", "subtitle", "badge", "is_ready"}]}
  is_ready=True відкриває SOAP, False відкриває екран обробки (ADD_SESSION із session_id).
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.app.ui import metrics, strings
from src.app.ui.errors import show_error
from src.app.ui.qt_helpers import clear_layout
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.action_icon import ActionIcon
from src.app.ui.widgets.badge import badge_for
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import outline_button, primary_button
from src.app.ui.widgets.card import ListItemCard
from src.app.ui.widgets.confirm import confirm_destructive
from src.app.ui.widgets.row_menu import RowMenuButton
from src.app.ui.widgets.skeleton import Skeleton


class PatientProfileScreen(BaseScreen):
    """Екран профілю пацієнта: контакти, список сесій і дії (додати сесію, медкартка, динаміка)."""

    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._patient_id: str | None = None
        self._patient_name: str = ""
        self._has_card: bool | None = None
        self._has_dynamics: bool | None = None
        self._request_id = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)

        self._crumb = Breadcrumb()
        self._crumb.linkActivated.connect(lambda _link: self.router.go_root(Route.PATIENTS))
        self._title = QLabel()
        self._title.setObjectName("ScreenTitle")
        self._contacts = QLabel()
        self._contacts.setObjectName("Subtitle")

        top = QHBoxLayout()
        top.setSpacing(metrics.SPACING)
        back = ActionIcon("back", strings.BACK)
        back.clicked.connect(self.router.back)
        top.addWidget(back)
        top.addWidget(self._crumb, alignment=Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        root.addLayout(top)
        root.addWidget(self._title)
        root.addWidget(self._contacts)

        actions = QHBoxLayout()
        actions.setSpacing(metrics.SPACING)
        self._add = primary_button(strings.PROFILE_ADD_SESSION_BUTTON)
        self._card = outline_button(strings.PROFILE_CARD)
        self._dynamics = outline_button(strings.PROFILE_DYNAMICS)
        self._add.clicked.connect(lambda *_: self.router.go(Route.ADD_SESSION, patient_id=self._patient_id))
        self._card.clicked.connect(self._open_card)
        self._dynamics.clicked.connect(self._open_dynamics)
        for btn in (self._add, self._card, self._dynamics):
            actions.addWidget(btn)
        actions.addStretch(1)
        self._menu = RowMenuButton(
            [(strings.PROFILE_DELETE_TITLE, self._confirm_delete_patient)],
            self,
        )
        actions.addWidget(self._menu, alignment=Qt.AlignmentFlag.AlignVCenter)
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
        """Завантажує профіль пацієнта; застарілі відповіді відсікаються за номером запиту."""
        self._patient_id = params["patient_id"]
        self._has_card = None
        self._has_dynamics = None
        self._request_id += 1
        request_id = self._request_id
        self._show_loading()
        self.call(
            self.facade.get_patient_profile,
            self._patient_id,
            on_success=lambda profile: self._render_current(profile, request_id),
            on_error=lambda err: self._on_load_error(err, request_id),
        )

    def _show_loading(self) -> None:
        """Стан завантаження: skeleton замість сесій, кнопки дій вимкнені."""
        self._crumb.set_path([strings.NAV_PATIENTS])
        self._patient_name = ""
        self._title.clear()
        self._contacts.clear()
        self._contacts.setVisible(False)
        self._card.setEnabled(False)
        self._dynamics.setEnabled(False)
        self._menu.setEnabled(False)
        clear_layout(self._sessions)
        for _ in range(metrics.PROFILE_SKELETON_COUNT):
            self._sessions.addWidget(
                Skeleton(width=metrics.PROFILE_SKELETON_WIDTH, height=metrics.PROFILE_SKELETON_HEIGHT)
            )

    def _on_load_error(self, error: Exception, request_id: int) -> None:
        """Показує помилку Toast-ом і повертає лікаря назад (якщо відповідь не застаріла)."""
        if request_id == self._request_id:
            show_error(self, error)
            self.router.back()

    def _render_current(self, profile: dict, request_id: int) -> None:
        """Малює профіль лише для актуального запиту."""
        if request_id == self._request_id:
            self._render(profile)

    def _render(self, profile: dict) -> None:
        """Малює заголовок, контакти, доступність кнопок і список сесій (або порожній стан)."""
        name = profile.get("name") or strings.NO_NAME
        self._patient_name = name
        self._crumb.set_path([strings.NAV_PATIENTS, name])
        self._title.setText(name)
        self._contacts.setText(profile["contacts_line"])
        self._contacts.setVisible(bool(profile["contacts_line"]))
        self._has_card = bool(profile["has_card"])
        self._has_dynamics = bool(profile["has_dynamics"])
        self._card.setEnabled(self._has_card)
        self._dynamics.setEnabled(self._has_dynamics)
        self._menu.setEnabled(True)

        clear_layout(self._sessions)
        if not profile["sessions"]:
            # Одна кнопка на екрані: верхня, підписана «Додати першу сесію»
            self._add.setText(strings.PROFILE_ADD_FIRST_SESSION_BUTTON)
            empty = QLabel(strings.PROFILE_SESSIONS_EMPTY)
            empty.setObjectName("Muted")
            self._sessions.addWidget(empty)
            return
        self._add.setText(strings.PROFILE_ADD_SESSION_BUTTON)
        for session in profile["sessions"]:
            text, variant = badge_for(session["badge"])
            row = ListItemCard(
                strings.SESSION_ROW_TITLE.format(number=session["number"], date=session["date"]),
                session["subtitle"],
                text,
                variant,
                actions=[(strings.ROW_MENU_DELETE, lambda s=session: self._confirm_delete_session(s))],
            )
            row.clicked.connect(lambda *_, s=session: self._open_session(s))
            self._sessions.addWidget(row)

    def _confirm_delete_patient(self) -> None:
        """Видалення пацієнта з меню «⋯»: підтвердження, фасад, повернення до списку."""
        if self._patient_id is None:
            return
        if not confirm_destructive(
            self,
            strings.PROFILE_DELETE_TITLE,
            strings.PROFILE_DELETE_TEXT.format(name=self._patient_name or strings.NO_NAME),
            strings.PROFILE_DELETE_CONFIRM,
        ):
            return
        self.call(
            self.facade.delete_patient,
            self._patient_id,
            on_success=self._on_patient_deleted,
            on_error=lambda err: show_error(self, err),
        )

    def _on_patient_deleted(self, _result=None) -> None:
        self.window().toast.show_message(strings.PROFILE_DELETED_TOAST)
        self.router.go_root(Route.PATIENTS)

    def _confirm_delete_session(self, session: dict) -> None:
        """Видалення сесії з меню «⋯» рядка: підтвердження, фасад, перезавантаження профілю."""
        if not confirm_destructive(
            self, strings.SESSION_ROW_DELETE_TITLE,
            strings.SESSION_ROW_DELETE_TEXT.format(number=session["number"], date=session["date"]),
        ):
            return
        self.call(
            self.facade.delete_session,
            session["session_id"],
            on_success=lambda _r=None: self.on_open(patient_id=self._patient_id),
            on_error=lambda err: show_error(self, err),
        )

    def _open_dynamics(self) -> None:
        """Відкриває динаміку; страховка на випадок, якщо кнопку активовано без даних."""
        if self._has_dynamics is False:
            self.window().toast.show_message(strings.DYNAMICS_NEEDS_SESSIONS)
        elif self._patient_id is not None:
            self.router.go(Route.DYNAMICS, patient_id=self._patient_id)

    def _open_card(self) -> None:
        """Відкриває медкартку; страховка на випадок, якщо кнопку активовано без картки."""
        if self._has_card is False:
            self.window().toast.show_message(strings.MEDCARD_EMPTY)
        elif self._patient_id is not None:
            self.router.go(Route.MEDICAL_CARD, patient_id=self._patient_id)

    def _open_session(self, session: dict) -> None:
        """Готову сесію відкриває як SOAP, необроблену веде на екран обробки."""
        if session["is_ready"]:
            self.router.go(Route.SESSION, patient_id=self._patient_id, session_id=session["session_id"])
        else:
            self.router.go(Route.ADD_SESSION, patient_id=self._patient_id, session_id=session["session_id"])