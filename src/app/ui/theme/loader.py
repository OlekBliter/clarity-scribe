"""Завантаження QSS. Єдине місце, де застосовується тема."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

QSS_PATH = Path(__file__).parent / "theme.qss"  # відносно файла, а не робочої папки
log = logging.getLogger(__name__)


def load_theme(app: QApplication) -> None:
    if not QSS_PATH.exists():
        log.warning("theme.qss не знайдено: %s", QSS_PATH)
        return
    app.setStyleSheet(QSS_PATH.read_text(encoding="utf-8"))
