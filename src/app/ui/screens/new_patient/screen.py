"""Екран створення нового пацієнта.

Фасад (методи, які використовує цей екран):
- create_patient(contacts: dict) -> str (patient_id)

Правила форми:
- усі поля «Основних контактів» обов'язкові;
- «Екстрений контакт» можна не заповнювати, але якщо заповнене або позначене
  хоч щось (ім'я, стосунок, телефон, згода), то обов'язкове все, включно зі згодою;
- «Далі» активна, лише коли форма коректна; під кнопкою пояснення, чого бракує.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QScrollArea, QVBoxLayout, QWidget)

from src.app.ui import metrics, strings, validation
from src.app.ui.errors import show_error
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.buttons import outline_button, primary_button
from src.app.ui.widgets.date_field import DateField
from src.app.ui.widgets.form_field import ChoiceWithOther, FormField

_MAIN_KEYS = ("name", "birth", "phone", "email", "channel")
_EMERG_KEYS = ("emerg_name", "emerg_relation", "emerg_phone", "emerg_consent")


class NewPatientScreen(BaseScreen):
    """Форма створення нового пацієнта з двома картками контактів."""

    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._submitting = False
        self._generation = 0
        self._fields: dict[str, FormField] = {}
        self._init_ui()

    # ------------------------------------------------------------ верстка
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)

        title = QLabel(strings.NEW_PATIENT_TITLE)
        title.setObjectName("ScreenTitle")
        subtitle = QLabel(strings.NEW_PATIENT_SUBTITLE)
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        container = QWidget()
        form = QVBoxLayout(container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(metrics.SPACING)
        form.setAlignment(Qt.AlignmentFlag.AlignTop)
        form.addWidget(self._build_main_card())
        form.addWidget(self._build_emergency_card())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(metrics.SPACING)
        self._next_hint = QLabel()
        self._next_hint.setObjectName("Muted")
        actions.addWidget(self._next_hint, stretch=1)
        self.cancel_btn = outline_button(strings.CANCEL)
        self.cancel_btn.clicked.connect(self.router.back)
        self.next_btn = primary_button(strings.BTN_NEXT)
        self.next_btn.clicked.connect(self._on_next)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.next_btn)
        root.addLayout(actions)

        for field in self._fields.values():
            field.changed.connect(self._refresh)

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        layout.setSpacing(metrics.SPACING)
        heading = QLabel(title)
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)
        return card, layout

    def _add(self, layout: QVBoxLayout, key: str, label: str | None, widget: QWidget,
             error_fn, required: bool = False) -> None:
        field = FormField(label, widget, error_fn, required)
        self._fields[key] = field
        layout.addWidget(field)

    def _build_main_card(self) -> QFrame:
        card, col = self._card(strings.NEW_PATIENT_CARD_MAIN)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(strings.NEW_PATIENT_NAME_PLACEHOLDER)
        self._add(col, "name", strings.NEW_PATIENT_NAME_LABEL, self.name_input,
                  lambda: validation.validate_name(self.name_input.text()), required=True)

        self.birth_input = DateField(allow_empty=True)
        self.birth_input.setMaximumDate(QDate.currentDate())
        self._add(col, "birth", strings.NEW_PATIENT_BIRTH_LABEL, self.birth_input,
                  lambda: None if self.birth_input.has_value() else strings.VALIDATION_DATE,
                  required=True)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText(strings.NEW_PATIENT_PHONE_PLACEHOLDER)
        self._add(col, "phone", strings.NEW_PATIENT_PHONE_LABEL, self.phone_input,
                  lambda: validation.validate_phone(self.phone_input.text()), required=True)
        self.phone_input.editingFinished.connect(
            lambda: self._format_phone(self.phone_input))

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText(strings.NEW_PATIENT_EMAIL_PLACEHOLDER)
        self._add(col, "email", strings.NEW_PATIENT_EMAIL_LABEL, self.email_input,
                  lambda: validation.validate_email(self.email_input.text()), required=True)

        self.channel_input = ChoiceWithOther(
            strings.NEW_PATIENT_CHANNELS, strings.NEW_PATIENT_CHANNEL_OTHER_PLACEHOLDER)
        self._add(col, "channel", strings.NEW_PATIENT_CHANNEL_LABEL, self.channel_input,
                  self.channel_input.error, required=True)
        return card

    def _build_emergency_card(self) -> QFrame:
        card, col = self._card(strings.NEW_PATIENT_CARD_EMERGENCY)

        self.emerg_name_input = QLineEdit()
        self.emerg_name_input.setPlaceholderText(strings.NEW_PATIENT_EMERG_NAME_PLACEHOLDER)
        self._add(col, "emerg_name", strings.NEW_PATIENT_EMERG_NAME_LABEL, self.emerg_name_input,
                  lambda: self._emerg_error(
                      not self.emerg_name_input.text().strip(),
                      lambda: validation.validate_name(self.emerg_name_input.text())))

        self.emerg_rel_input = ChoiceWithOther(
            strings.NEW_PATIENT_RELATIONS, strings.NEW_PATIENT_RELATION_OTHER_PLACEHOLDER)
        self._add(col, "emerg_relation", strings.NEW_PATIENT_EMERG_REL_LABEL, self.emerg_rel_input,
                  lambda: self._emerg_error(
                      self.emerg_rel_input.is_empty(), self.emerg_rel_input.error))

        self.emerg_phone_input = QLineEdit()
        self.emerg_phone_input.setPlaceholderText(strings.NEW_PATIENT_PHONE_PLACEHOLDER)
        self._add(col, "emerg_phone", strings.NEW_PATIENT_EMERG_PHONE_LABEL, self.emerg_phone_input,
                  lambda: self._emerg_error(
                      not self.emerg_phone_input.text().strip(),
                      lambda: validation.validate_phone(self.emerg_phone_input.text())))
        self.emerg_phone_input.editingFinished.connect(
            lambda: self._format_phone(self.emerg_phone_input))

        self.emerg_consent_check = QCheckBox(strings.NEW_PATIENT_EMERG_CONSENT)
        self.emerg_consent_check.setMinimumHeight(metrics.CHECKBOX_MIN_HEIGHT)
        self._add(col, "emerg_consent", None, self.emerg_consent_check,
                  lambda: validation.validate_consent(
                      self._emerg_active(), self.emerg_consent_check.isChecked()))
        return card

    # ------------------------------------------------------------ правила
    def _emerg_active(self) -> bool:
        """Блок екстреного контакту «в роботі»: заповнено або позначено хоч щось."""
        return (bool(self.emerg_name_input.text().strip())
                or not self.emerg_rel_input.is_empty()
                or bool(self.emerg_phone_input.text().strip())
                or self.emerg_consent_check.isChecked())

    def _emerg_error(self, is_empty: bool, check) -> str | None:
        """Порожнє поле блоку: помилка, якщо блок активний; заповнене: перевірка формату."""
        if is_empty:
            return strings.VALIDATION_REQUIRED if self._emerg_active() else None
        return check()

    @staticmethod
    def _format_phone(edit: QLineEdit) -> None:
        formatted = validation.normalize_phone(edit.text())
        if formatted:
            edit.setText(formatted)

    def _first_missing(self) -> str | None:
        """Ключ першого некоректного поля у порядку на екрані (або None)."""
        for key in _MAIN_KEYS + _EMERG_KEYS:
            if self._fields[key].error():
                return key
        return None

    def _refresh(self) -> None:
        """Оновлює помилки під полями, активність «Далі» та пояснення біля неї."""
        for field in self._fields.values():
            field.refresh()
        missing = self._first_missing()
        self.next_btn.setEnabled(missing is None and not self._submitting)
        self._next_hint.setText(
            "" if missing is None
            else strings.NEW_PATIENT_NEXT_HINT.format(what=strings.NEW_PATIENT_MISSING[missing]))

    # ------------------------------------------------------------ дії
    def _collect_contacts(self) -> dict:
        contacts = {
            "preferred_name": validation.collapse_spaces(self.name_input.text()),
            "birth_date": self.birth_input.iso(),
            "phone": validation.normalize_phone(self.phone_input.text()),
            "email": self.email_input.text().strip(),
            "preferred_channel": self.channel_input.value(),
        }
        if self._emerg_active():
            contacts.update({
                "emergency_name": validation.collapse_spaces(self.emerg_name_input.text()),
                "emergency_relation": self.emerg_rel_input.value(),
                "emergency_phone": validation.normalize_phone(self.emerg_phone_input.text()),
                "emergency_consent": True,
            })
        return contacts

    def _on_next(self) -> None:
        if self._submitting or self._first_missing() is not None:  # страховка: кнопка мала бути вимкнена
            return
        self._submitting = True
        generation = self._generation
        self.next_btn.setEnabled(False)
        self.call(self.facade.create_patient, self._collect_contacts(),
                  on_success=lambda pid: self._created_result(generation, pid),
                  on_error=lambda exc: self._created_result(generation, None, exc))

    def _created_result(self, generation, patient_id, error=None):
        self._submitting = False
        if generation != self._generation or self.router.current_route != Route.NEW_PATIENT:
            self._refresh()
            return
        if error is not None:
            self._on_create_error(error)
        else:
            self._on_created(patient_id)

    def _on_created(self, patient_id: str) -> None:
        # Звичайний потік: профіль нового пацієнта («Сесій ще немає») -> «Додати першу сесію».
        # go_root скидає історію, тож «Назад» з профілю веде до списку, а не до порожньої форми.
        self.router.go_root(Route.PATIENTS)
        self.router.go(Route.PATIENT_PROFILE, patient_id=patient_id)

    def _on_create_error(self, error: Exception) -> None:
        show_error(self, error)
        self._refresh()

    def on_open(self, **params: Any) -> None:
        self._generation += 1
        self.name_input.clear()
        self.birth_input.clear_value()
        self.phone_input.clear()
        self.email_input.clear()
        self.channel_input.reset()
        self.emerg_name_input.clear()
        self.emerg_rel_input.reset()
        self.emerg_phone_input.clear()
        self.emerg_consent_check.setChecked(False)
        for field in self._fields.values():
            field.reset()
        self._refresh()
