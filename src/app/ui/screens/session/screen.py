"""Сесія.

Фасад (методи, які використовує цей екран):
  get_soap, save_soap, approve_soap, get_transcript, get_audio_info, get_waveform, delete_session

Параметри відкриття: див. on_open у README_UI.md (розділ "Маршрути").
Заготовка: замініть PlaceholderScreen на BaseScreen і верстайте за зразком
screens/patients/screen.py.
"""
from __future__ import annotations

from src.app.ui.screens.placeholder import PlaceholderScreen


class SessionScreen(PlaceholderScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__("Сесія", facade, router, parent)
