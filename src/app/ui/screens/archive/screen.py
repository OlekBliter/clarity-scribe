"""Архів пацієнтів.

Фасад (методи, які використовує цей екран):
  (немає: статичні дані, фасад не викликаємо)

Параметри відкриття: див. on_open у README_UI.md (розділ "Маршрути").
Заготовка: замініть PlaceholderScreen на BaseScreen і верстайте за зразком
screens/patients/screen.py.
"""
from __future__ import annotations

from src.app.ui.screens.placeholder import PlaceholderScreen


class ArchiveScreen(PlaceholderScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__("Архів пацієнтів", facade, router, parent)
