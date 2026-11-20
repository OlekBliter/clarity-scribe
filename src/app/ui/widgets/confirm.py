"""Єдиний діалог підтвердження (заголовок, текст, «Скасувати» + дія) у стилі застосунку.

    if ask_confirm(self, "Видалити пацієнта", "Текст…", "Видалити"):          # небезпечна дія
    if ask_confirm(self, "Затвердити", "Текст…", "Затвердити", destructive=False)

Безрамкове заокруглене вікно; Esc і «Скасувати» закривають, типова кнопка «Скасувати».
Вигляд задається в theme.qss (QDialog#ConfirmDialog, QFrame#ConfirmCard).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.app.ui import metrics, strings
from src.app.ui.widgets.buttons import danger_button, primary_button, secondary_button


class ConfirmDialog(QDialog):
    def __init__(self, parent: QWidget | None, title: str, text: str, confirm_text: str,
                 destructive: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("ConfirmDialog")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("ConfirmCard")
        outer.addWidget(card)
        col = QVBoxLayout(card)
        col.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        col.setSpacing(metrics.SPACING)

        heading = QLabel(title)
        heading.setObjectName("CardTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setWordWrap(True)
        body = QLabel(text)
        body.setWordWrap(True)
        col.addWidget(heading)
        col.addWidget(body)

        row = QHBoxLayout()
        row.setSpacing(metrics.SPACING)
        row.addStretch(1)
        cancel = secondary_button(strings.CANCEL)
        confirm = (danger_button if destructive else primary_button)(confirm_text)
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(confirm)
        col.addLayout(row)

        cancel.setDefault(True)
        cancel.setFocus()
        self.setMinimumWidth(metrics.CONFIRM_DIALOG_WIDTH)
        self.setMaximumWidth(metrics.CONFIRM_DIALOG_WIDTH)


def ask_confirm(parent: QWidget | None, title: str, text: str, confirm_text: str,
                destructive: bool = True) -> bool:
    """True, якщо лікар підтвердив."""
    return ConfirmDialog(parent, title, text, confirm_text, destructive).exec() == QDialog.DialogCode.Accepted


def confirm_destructive(parent: QWidget, title: str, text: str,
                        confirm_text: str = strings.ROW_MENU_DELETE) -> bool:
    return ask_confirm(parent, title, text, confirm_text, destructive=True)
