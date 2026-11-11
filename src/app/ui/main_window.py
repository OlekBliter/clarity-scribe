"""Головне вікно: бічна панель + стек екранів + Toast."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from src.app.ui import metrics, strings
from src.app.ui.qt_helpers import set_active
from src.app.ui.router import Route, Router
from src.app.ui.screens.add_session import AddSessionScreen
from src.app.ui.screens.archive import ArchiveScreen
from src.app.ui.screens.dynamics import DynamicsScreen
from src.app.ui.screens.medical_card import MedicalCardScreen
from src.app.ui.screens.new_patient import NewPatientScreen
from src.app.ui.screens.patient_profile import PatientProfileScreen
from src.app.ui.screens.patients import PatientsScreen
from src.app.ui.screens.session import SessionScreen
from src.app.ui.screens.settings import SettingsScreen
from src.app.ui.widgets.toast import Toast

# Який пункт меню підсвічувати для екрана (усе інше належить до "Пацієнти")
_NAV_GROUP = {Route.ARCHIVE: Route.ARCHIVE, Route.SETTINGS: Route.SETTINGS}


class MainWindow(QMainWindow):
    def __init__(self, facade) -> None:
        super().__init__()
        self.facade = facade
        self.setWindowTitle(strings.APP_NAME)
        self.setMinimumSize(metrics.WINDOW_MIN_WIDTH, metrics.WINDOW_MIN_HEIGHT)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        self._nav_buttons: dict[Route, QPushButton] = {}
        root.addWidget(self._build_sidebar())

        content = QWidget()
        content.setObjectName("ContentArea")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        root.addWidget(content, stretch=1)

        self.router = Router(self.stack, self)
        self._register_routes()
        self.router.route_changed.connect(self._on_route_changed)

        self.toast = Toast(self)
        self.router.go_root(Route.PATIENTS)

    # ---- сайдбар ----
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setFixedWidth(metrics.SIDEBAR_WIDTH)
        col = QVBoxLayout(side)
        col.setContentsMargins(*(metrics.SIDEBAR_PADDING,) * 4)
        col.setSpacing(metrics.SPACING_SMALL)

        logo = QLabel(strings.APP_NAME)
        logo.setObjectName("Logo")
        col.addWidget(logo)
        col.addSpacing(metrics.SPACING)

        for route, text in ((Route.PATIENTS, strings.NAV_PATIENTS),
                            (Route.ARCHIVE, strings.NAV_ARCHIVE),
                            (Route.SETTINGS, strings.NAV_SETTINGS)):
            btn = QPushButton(text)
            btn.setObjectName("SidebarButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, r=route: self.router.go_root(r))
            self._nav_buttons[route] = btn
            col.addWidget(btn)

        col.addStretch(1)
        note = QLabel(strings.LOCAL_DATA_NOTE)
        note.setObjectName("SidebarNote")
        note.setWordWrap(True)
        col.addWidget(note)
        return side

    # ---- маршрути ----
    def _register_routes(self) -> None:
        """Усі екрани підключені один раз. Розробники правлять лише свої
        screens/<назва>/screen.py і сюди не повертаються."""
        f, r = self.facade, self.router
        screens = {
            Route.PATIENTS: PatientsScreen,
            Route.PATIENT_PROFILE: PatientProfileScreen,
            Route.NEW_PATIENT: NewPatientScreen,
            Route.ADD_SESSION: AddSessionScreen,
            Route.SESSION: SessionScreen,
            Route.MEDICAL_CARD: MedicalCardScreen,
            Route.DYNAMICS: DynamicsScreen,
            Route.ARCHIVE: ArchiveScreen,
            Route.SETTINGS: SettingsScreen,
        }
        for route, screen_cls in screens.items():
            self.router.register(route, lambda cls=screen_cls: cls(f, r))

    def _on_route_changed(self, route: Route, _params: dict) -> None:
        active = _NAV_GROUP.get(route, Route.PATIENTS)
        for nav_route, btn in self._nav_buttons.items():
            set_active(btn, nav_route == active)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast.reposition()
