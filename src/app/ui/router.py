"""Навігація між екранами. Екрани не відкривають один одного напряму."""
from __future__ import annotations

from enum import Enum
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QStackedWidget, QWidget


class Route(str, Enum):
    PATIENTS = "patients"
    PATIENT_PROFILE = "patient_profile"
    NEW_PATIENT = "new_patient"
    ADD_SESSION = "add_session"
    SESSION = "session"
    MEDICAL_CARD = "medical_card"
    DYNAMICS = "dynamics"
    ARCHIVE = "archive"
    SETTINGS = "settings"


class Router(QObject):
    route_changed = Signal(object, dict)  # (Route, params)

    def __init__(self, stack: QStackedWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stack = stack
        self._factories: dict[Route, Callable[[], QWidget]] = {}
        self._screens: dict[Route, QWidget] = {}
        self._history: list[tuple[Route, dict]] = []

    @property
    def current_route(self) -> Route | None:
        return self._history[-1][0] if self._history else None

    def register(self, route: Route, factory: Callable[[], QWidget]) -> None:
        """Екран створюється лениво, при першому відкритті."""
        self._factories[route] = factory

    def go(self, route: Route, **params) -> None:
        """Відкрити екран; params передаються в screen.on_open(**params)."""
        self._history.append((route, params))
        self._show(route, params)

    def go_root(self, route: Route) -> None:
        """Перехід з бічного меню: історію скидаємо."""
        self._history.clear()
        self.go(route)

    def back(self) -> None:
        if len(self._history) > 1:
            self._history.pop()
            route, params = self._history[-1]
            self._show(route, params)

    def _show(self, route: Route, params: dict) -> None:
        screen = self._screens.get(route)
        if screen is None:
            screen = self._factories[route]()
            self._screens[route] = screen
            self._stack.addWidget(screen)
        self._stack.setCurrentWidget(screen)
        on_open = getattr(screen, "on_open", None)
        if callable(on_open):
            on_open(**params)
        self.route_changed.emit(route, params)
