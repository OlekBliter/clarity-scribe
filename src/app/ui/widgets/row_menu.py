"""Кнопка «⋯» з меню дій над рядком списку (пацієнт, сесія).

    RowMenuButton([(strings.ROW_MENU_DELETE, self._delete)])

Пункти меню червоні (QMenu#RowMenu у theme.qss). Небезпечні дії роблять
підтвердження самі (див. confirm.py): меню лише викликає callback.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMenu

from src.app.ui import strings
from src.app.ui.widgets.action_icon import ActionIcon


class RowMenuButton(ActionIcon):
    def __init__(self, actions: list[tuple[str, Callable[[], None]]], parent=None) -> None:
        super().__init__("more", strings.ROW_MENU_TOOLTIP, parent)
        self._actions = actions
        self.clicked.connect(self._open_menu)

    def set_actions(self, actions: list[tuple[str, Callable[[], None]]]) -> None:
        """Задати пункти пізніше (коли кнопку створює view, а дії знає екран)."""
        self._actions = actions

    def _open_menu(self) -> None:
        menu = QMenu(self)
        menu.setObjectName("RowMenu")
        # Прозоре тло без системної тіні: інакше кути меню не можуть бути заокругленими
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        for text, callback in self._actions:
            menu.addAction(text, callback)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))
