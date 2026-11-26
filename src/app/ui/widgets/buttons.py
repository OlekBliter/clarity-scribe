"""Фабрики кнопок. Вигляд повністю в QSS (objectName)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


def _button(text: str, object_name: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(object_name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def primary_button(text: str) -> QPushButton:
    return _button(text, "PrimaryButton")


def secondary_button(text: str) -> QPushButton:
    return _button(text, "SecondaryButton")


def outline_button(text: str) -> QPushButton:
    return _button(text, "OutlineButton")


def danger_button(text: str) -> QPushButton:
    return _button(text, "DangerButton")
