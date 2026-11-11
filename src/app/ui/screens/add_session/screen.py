"""Додати запис сесії.

Фасад (методи, які використовує цей екран):
  next_session_number, add_session, process_session (у воркері), get_processing_state

Параметри відкриття: див. on_open у README_UI.md (розділ "Маршрути").
Заготовка: замініть PlaceholderScreen на BaseScreen і верстайте за зразком
screens/patients/screen.py.
"""
from __future__ import annotations

from src.app.ui.screens.placeholder import PlaceholderScreen


class AddSessionScreen(PlaceholderScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__("Додати запис сесії", facade, router, parent)
