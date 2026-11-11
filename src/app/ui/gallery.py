"""Галерея стилів для розробки: усі елементи теми на одному екрані, без фасаду.

Запуск:  python -m src.app.ui.gallery
F5 перечитує theme.qss з диска, тож стилі правляться без перезапуску.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QScrollArea, QTextEdit, QVBoxLayout, QWidget)

from src.app.ui import metrics
from src.app.ui.theme.loader import load_theme
from src.app.ui.widgets.badge import VARIANTS, Badge
from src.app.ui.widgets.buttons import (danger_button, outline_button, primary_button,
                                        secondary_button)
from src.app.ui.widgets.card import Card, ListItemCard
from src.app.ui.widgets.toast import Toast


def _section(title: str) -> QLabel:
    label = QLabel(title)
    label.setObjectName("SectionTitle")
    return label


def _row(*widgets: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(metrics.SPACING)
    for w in widgets:
        row.addWidget(w)
    row.addStretch(1)
    return row


class Gallery(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ContentArea")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("ClarityScribe · галерея стилів (F5 = перечитати QSS)")
        self.resize(900, 900)

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        col.setSpacing(metrics.SPACING)
        scroll.setWidget(body)

        title = QLabel("Галерея стилів")
        title.setObjectName("ScreenTitle")
        col.addWidget(title)
        sub = QLabel("Заголовок розділу, підзаголовок і приглушений текст")
        sub.setObjectName("Subtitle")
        muted = QLabel("Приглушений текст / хлібні крихти")
        muted.setObjectName("Muted")
        col.addWidget(sub)
        col.addWidget(muted)

        col.addWidget(_section("Кнопки"))
        disabled = primary_button("Заблокована")
        disabled.setEnabled(False)
        col.addLayout(_row(primary_button("Primary"), secondary_button("Secondary"),
                           outline_button("Outline"), danger_button("Danger"), disabled))

        col.addWidget(_section("Бейджі"))
        col.addLayout(_row(*[Badge(v, v) for v in sorted(VARIANTS)]))

        col.addWidget(_section("Чіпи біомаркерів і джерела"))
        chips = []
        for text, variant in (("тривалість пауз ↗", "danger"), ("темп мовлення ↘", "warning")):
            chip = QLabel(text)
            chip.setObjectName("Chip")
            chip.setProperty("variant", variant)
            chips.append(chip)
        src1, src2 = QPushButton("07:45"), QPushButton("12:10")
        for s in (src1, src2):
            s.setObjectName("SourceChip")
        col.addLayout(_row(*chips, src1, src2))

        col.addWidget(_section("Поля вводу"))
        name = QLineEdit()
        name.setPlaceholderText("Введіть ім'я")
        combo = QComboBox()
        combo.addItems(["Telegram", "Телефон", "Email"])
        date = QDateEdit()
        date.setDisplayFormat("dd.MM.yyyy")
        col.addLayout(_row(name, combo, date, QCheckBox("Надаю згоду")))
        note = QTextEdit()
        note.setPlaceholderText("Багаторядкове поле")
        note.setFixedHeight(70)
        col.addWidget(note)

        col.addWidget(_section("Картки"))
        col.addWidget(ListItemCard("Мельник Олена", "5 сесій • остання 02.10.2026",
                                   "Чекає на перегляд", "warning"))
        col.addWidget(ListItemCard("Коваленко Дмитро", "3 сесії • остання 28.09.2026",
                                   "Підтверджено", "success"))
        for name_, label in (("CardDanger", "Потребує уваги"), ("CardWarning", "Суперечливо"),
                             ("SummaryBox", "Підсумковий блок")):
            frame = Card()
            frame.setObjectName(name_)
            lay = QVBoxLayout(frame)
            lay.addWidget(QLabel(label))
            col.addWidget(frame)

        col.addWidget(_section("Прогрес, drop-зона, skeleton"))
        bar = QProgressBar()
        bar.setValue(60)
        col.addWidget(bar)
        drop = QFrame()
        drop.setObjectName("DropZone")
        drop.setFixedHeight(90)
        QVBoxLayout(drop).addWidget(QLabel("Перетягніть файл сюди"),
                                    alignment=Qt.AlignmentFlag.AlignCenter)
        col.addWidget(drop)
        skeleton = QWidget()
        skeleton.setObjectName("Skeleton")
        skeleton.setFixedHeight(24)
        col.addWidget(skeleton)

        toast_btn = outline_button("Показати Toast")
        col.addWidget(toast_btn)
        col.addStretch(1)

        self.toast = Toast(self)
        toast_btn.clicked.connect(lambda: self.toast.show_message("Сталася помилка. Спробуйте ще раз"))
        QShortcut(QKeySequence("F5"), self, activated=lambda: load_theme(QApplication.instance()))


def main() -> int:
    app = QApplication(sys.argv)
    load_theme(app)
    window = Gallery()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
