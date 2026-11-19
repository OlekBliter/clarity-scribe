"""Підтвердження незворотної дії (єдиний діалог для всіх «Видалити»)."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from src.app.ui import strings


def confirm_destructive(parent: QWidget, title: str, text: str,
                        confirm_text: str = strings.ROW_MENU_DELETE) -> bool:
    """True, якщо лікар підтвердив. Типова кнопка — «Скасувати»."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning)
    confirm_btn = box.addButton(confirm_text, QMessageBox.ButtonRole.DestructiveRole)
    confirm_btn.setObjectName("DangerButton")
    cancel_btn = box.addButton(strings.CANCEL, QMessageBox.ButtonRole.RejectRole)
    cancel_btn.setObjectName("SecondaryButton")
    box.setDefaultButton(cancel_btn)
    box.exec()
    return box.clickedButton() is confirm_btn
