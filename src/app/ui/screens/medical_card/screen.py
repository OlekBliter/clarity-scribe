"""Медкартка.

Фасад (методи, які використовує цей екран):
  get_card, save_card, approve_card

Параметри відкриття: див. on_open у README_UI.md (розділ "Маршрути").
Заготовка: замініть PlaceholderScreen на BaseScreen і верстайте за зразком
screens/patients/screen.py.
"""
from __future__ import annotations

from src.app.ui.screens.placeholder import PlaceholderScreen


class MedicalCardScreen(PlaceholderScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__("Медкартка", facade, router, parent)
