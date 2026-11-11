"""Налаштування застосунку.

Фасад (методи, які використовує цей екран):
  (поки немає в контракті фасаду: див. розділ 'Запити до фасаду' в роудмапі)

Параметри відкриття: див. on_open у README_UI.md (розділ "Маршрути").
Заготовка: замініть PlaceholderScreen на BaseScreen і верстайте за зразком
screens/patients/screen.py.
"""
from __future__ import annotations

from src.app.ui.screens.placeholder import PlaceholderScreen


class SettingsScreen(PlaceholderScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__("Налаштування застосунку", facade, router, parent)
