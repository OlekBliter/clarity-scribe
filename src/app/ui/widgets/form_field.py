"""Поле форми з підписом і помилкою під ним + вибір зі списку з варіантом «Інше».

Єдиний спосіб показати помилку валідації в застосунку:

    field = FormField(strings.LABEL, QLineEdit(), error_fn, required=True)
    field.changed.connect(self._refresh)       # значення змінилось
    field.error()                              # текст помилки або None (без показу)
    field.show_error(True)                     # показати/сховати помилку

error_fn() -> str | None повертає текст помилки (див. validation.py).
Помилка показується лише після того, як лікар «торкнувся» поля
(вийшов із нього або змінив значення), тож порожня форма не червона.
Підсвітку (червона рамка) задає QSS: *[invalid="true"].
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QLabel, QLineEdit, QPlainTextEdit,
                               QVBoxLayout, QWidget)

from src.app.ui import metrics, strings, validation
from src.app.ui.qt_helpers import fit_combo_popup, repolish
from src.app.ui.widgets.date_field import DateField


class ChoiceWithOther(QWidget):
    """Список варіантів + «Інше»: для «Інше» з'являється поле для власного тексту."""

    changed = Signal()
    touched = Signal()

    def __init__(self, options: tuple[str, ...], other_placeholder: str, parent=None) -> None:
        super().__init__(parent)
        self._combo = QComboBox()
        self._combo.addItems(options)
        self._combo.addItem(strings.CHOICE_OTHER)
        self._combo.setPlaceholderText(strings.CHOICE_PLACEHOLDER)
        self._combo.setCurrentIndex(-1)
        fit_combo_popup(self._combo)
        self._other = QLineEdit()
        self._other.setPlaceholderText(other_placeholder)
        self._other.setMaxLength(metrics.OTHER_MAX_LEN * 2)  # запас під зайві пробіли
        self._other.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metrics.SPACING_SMALL)
        layout.addWidget(self._combo)
        layout.addWidget(self._other)

        self._combo.currentIndexChanged.connect(self._on_choice)
        self._other.textChanged.connect(lambda _t: self.changed.emit())
        self._other.editingFinished.connect(self.touched.emit)

    def _is_other(self) -> bool:
        return self._combo.currentIndex() == self._combo.count() - 1

    def _on_choice(self, _index: int) -> None:
        self._other.setVisible(self._is_other())
        self.changed.emit()
        self.touched.emit()

    def is_empty(self) -> bool:
        if self._combo.currentIndex() < 0:
            return True
        return self._is_other() and not self._other.text().strip()

    def value(self) -> str | None:
        """Обране значення (власний текст для «Інше») або None."""
        if self._combo.currentIndex() < 0:
            return None
        if self._is_other():
            return validation.collapse_spaces(self._other.text()) or None
        return self._combo.currentText()

    def error(self) -> str | None:
        """Помилка обраного значення; порожній вибір — це VALIDATION_CHOOSE."""
        if self._combo.currentIndex() < 0:
            return strings.VALIDATION_CHOOSE
        if self._is_other():
            return validation.validate_other(self._other.text())
        return None

    def reset(self) -> None:
        self._combo.setCurrentIndex(-1)
        self._other.clear()
        self._other.hide()

    def set_invalid(self, invalid: bool) -> None:
        for widget in (self._combo, self._other):
            widget.setProperty("invalid", "true" if invalid else "false")
            repolish(widget)


class FormField(QWidget):
    changed = Signal()

    def __init__(self, label: str | None, widget: QWidget,
                 error_fn: Callable[[], str | None], required: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self.widget = widget
        self._error_fn = error_fn
        self._touched = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metrics.SPACING_SMALL)
        if label:
            layout.addWidget(QLabel(label + (strings.REQUIRED_MARK if required else "")))
        layout.addWidget(widget)
        self._error_label = QLabel()
        self._error_label.setObjectName("ErrorText")
        # без setWordWrap: переносний QLabel у QScrollArea збиває висоту карток (стискає поля)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self._wire(widget)

    def _wire(self, widget: QWidget) -> None:
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._on_changed)
            widget.editingFinished.connect(self.touch)
        elif isinstance(widget, DateField):
            widget.dateChanged.connect(lambda _d: (self._on_changed(), self.touch()))
        elif isinstance(widget, ChoiceWithOther):
            widget.changed.connect(self._on_changed)
            widget.touched.connect(self.touch)
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(lambda: (self._on_changed(), self.touch()))
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(lambda _i: (self._on_changed(), self.touch()))
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda _c: (self._on_changed(), self.touch()))

    def _on_changed(self, *_args) -> None:
        self.changed.emit()

    def error(self) -> str | None:
        return self._error_fn()

    def touch(self) -> None:
        self._touched = True
        self.refresh()

    def refresh(self) -> None:
        """Перемальовує помилку, якщо поля вже торкались."""
        self.show_error(self._touched)

    def show_error(self, visible: bool) -> None:
        text = self._error_fn() if visible else None
        self._error_label.setText(text or "")
        self._error_label.setVisible(bool(text))
        invalid = "true" if text else "false"
        if hasattr(self.widget, "set_invalid"):
            self.widget.set_invalid(bool(text))
        else:
            self.widget.setProperty("invalid", invalid)
            repolish(self.widget)

    def reset(self) -> None:
        """Прибирає «торкнуте» і помилку (виклик після очищення значення)."""
        self._touched = False
        self.show_error(False)
