"""Екран створення нового пацієнта.

Фасад (методи, які використовує цей екран):
- create_patient(contacts: dict) -> str (patient_id)
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.app.ui import metrics, strings
from src.app.ui.errors import show_error
from src.app.ui.qt_helpers import fit_combo_popup
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.action_icon import ActionIcon
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import outline_button, primary_button
from src.app.ui.widgets.date_field import DateField


class NewPatientScreen(BaseScreen):
    """Форма створення нового пацієнта з двома картками контактів."""

    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        main_layout.setSpacing(metrics.SPACING)

        top = QHBoxLayout()
        back_btn = ActionIcon("back", strings.BACK)
        back_btn.clicked.connect(self._on_cancel)
        top.addWidget(back_btn)

        crumb = Breadcrumb(self)
        crumb.set_path([strings.NAV_PATIENTS, strings.NEW_PATIENT_TITLE])
        crumb.linkActivated.connect(lambda _link: self._on_cancel())
        top.addWidget(crumb, 1)
        main_layout.addLayout(top)

        title_label = QLabel(strings.NEW_PATIENT_TITLE)
        title_label.setObjectName("ScreenTitle")
        main_layout.addWidget(title_label)

        subtitle_label = QLabel(strings.NEW_PATIENT_SUBTITLE)
        subtitle_label.setObjectName("Subtitle")
        main_layout.addWidget(subtitle_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(metrics.SPACING)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_card = QFrame()
        main_card.setObjectName("Card")
        main_card_layout = QVBoxLayout(main_card)
        main_card_layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        main_card_layout.setSpacing(metrics.SPACING)

        main_card_title = QLabel(strings.NEW_PATIENT_CARD_MAIN)
        main_card_title.setObjectName("CardTitle")
        main_card_layout.addWidget(main_card_title)

        main_card_layout.addWidget(QLabel(strings.NEW_PATIENT_NAME_LABEL))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(strings.NEW_PATIENT_NAME_PLACEHOLDER)
        main_card_layout.addWidget(self.name_input)

        main_card_layout.addWidget(QLabel(strings.NEW_PATIENT_BIRTH_LABEL))
        self.birth_input = DateField()
        self.birth_input.setMaximumDate(QDate.currentDate())
        main_card_layout.addWidget(self.birth_input)

        phone_header = QHBoxLayout()
        phone_header.addWidget(QLabel(strings.NEW_PATIENT_PHONE_LABEL))
        self.phone_hint = QLabel(strings.NEW_PATIENT_HINT_PHONE)
        self.phone_hint.setObjectName("Muted")
        self.phone_hint.setVisible(False)
        phone_header.addWidget(self.phone_hint, alignment=Qt.AlignmentFlag.AlignRight)
        main_card_layout.addLayout(phone_header)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText(strings.NEW_PATIENT_PHONE_PLACEHOLDER)
        self.phone_input.textChanged.connect(self._validate_phone)
        main_card_layout.addWidget(self.phone_input)

        email_header = QHBoxLayout()
        email_header.addWidget(QLabel(strings.NEW_PATIENT_EMAIL_LABEL))
        self.email_hint = QLabel(strings.NEW_PATIENT_HINT_EMAIL)
        self.email_hint.setObjectName("Muted")
        self.email_hint.setVisible(False)
        email_header.addWidget(self.email_hint, alignment=Qt.AlignmentFlag.AlignRight)
        main_card_layout.addLayout(email_header)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText(strings.NEW_PATIENT_EMAIL_PLACEHOLDER)
        self.email_input.textChanged.connect(self._validate_email)
        main_card_layout.addWidget(self.email_input)

        main_card_layout.addWidget(QLabel(strings.NEW_PATIENT_CHANNEL_LABEL))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(strings.NEW_PATIENT_CHANNELS)
        fit_combo_popup(self.channel_combo)
        main_card_layout.addWidget(self.channel_combo)

        form_layout.addWidget(main_card)

        emerg_card = QFrame()
        emerg_card.setObjectName("Card")
        emerg_card_layout = QVBoxLayout(emerg_card)
        emerg_card_layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        emerg_card_layout.setSpacing(metrics.SPACING)

        emerg_card_title = QLabel(strings.NEW_PATIENT_CARD_EMERGENCY)
        emerg_card_title.setObjectName("CardTitle")
        emerg_card_layout.addWidget(emerg_card_title)

        emerg_card_layout.addWidget(QLabel(strings.NEW_PATIENT_EMERG_NAME_LABEL))
        self.emerg_name_input = QLineEdit()
        self.emerg_name_input.setPlaceholderText(strings.NEW_PATIENT_EMERG_NAME_PLACEHOLDER)
        emerg_card_layout.addWidget(self.emerg_name_input)

        emerg_card_layout.addWidget(QLabel(strings.NEW_PATIENT_EMERG_REL_LABEL))
        self.emerg_rel_combo = QComboBox()
        self.emerg_rel_combo.addItems(strings.NEW_PATIENT_RELATIONS)
        fit_combo_popup(self.emerg_rel_combo)
        emerg_card_layout.addWidget(self.emerg_rel_combo)

        emerg_phone_header = QHBoxLayout()
        emerg_phone_header.addWidget(QLabel(strings.NEW_PATIENT_EMERG_PHONE_LABEL))
        self.emerg_phone_hint = QLabel(strings.NEW_PATIENT_HINT_PHONE)
        self.emerg_phone_hint.setObjectName("Muted")
        self.emerg_phone_hint.setVisible(False)
        emerg_phone_header.addWidget(self.emerg_phone_hint, alignment=Qt.AlignmentFlag.AlignRight)
        emerg_card_layout.addLayout(emerg_phone_header)

        self.emerg_phone_input = QLineEdit()
        self.emerg_phone_input.setPlaceholderText(strings.NEW_PATIENT_PHONE_PLACEHOLDER)
        self.emerg_phone_input.textChanged.connect(self._validate_emerg_phone)
        emerg_card_layout.addWidget(self.emerg_phone_input)

        self.emerg_consent_check = QCheckBox(strings.NEW_PATIENT_EMERG_CONSENT)
        emerg_card_layout.addWidget(self.emerg_consent_check)

        form_layout.addWidget(emerg_card)

        scroll_area.setWidget(form_container)
        main_layout.addWidget(scroll_area, stretch=1)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(metrics.SPACING)
        actions_layout.addStretch(1)

        self.cancel_btn = outline_button(strings.CANCEL)
        self.cancel_btn.clicked.connect(self._on_cancel)
        actions_layout.addWidget(self.cancel_btn)

        self.next_btn = primary_button(strings.BTN_NEXT)
        self.next_btn.clicked.connect(self._on_next)
        actions_layout.addWidget(self.next_btn)

        main_layout.addLayout(actions_layout)

    def _validate_phone(self, text: str) -> None:
        val = text.strip()
        is_valid = not val or val.startswith("+380")
        self.phone_hint.setVisible(not is_valid)

    def _validate_email(self, text: str) -> None:
        val = text.strip()
        is_valid = not val or ("@" in val and "." in val.split("@")[-1])
        self.email_hint.setVisible(not is_valid)

    def _validate_emerg_phone(self, text: str) -> None:
        val = text.strip()
        is_valid = not val or val.startswith("+380")
        self.emerg_phone_hint.setVisible(not is_valid)

    def _collect_contacts(self) -> dict:
        contacts: dict = {}

        if name := self.name_input.text().strip():
            contacts["preferred_name"] = name
        if self.birth_input.date() != QDate.currentDate():
            contacts["birth_date"] = self.birth_input.date().toString("yyyy-MM-dd")
        if phone := self.phone_input.text().strip():
            contacts["phone"] = phone
        if email := self.email_input.text().strip():
            contacts["email"] = email

        if self.channel_combo.currentIndex() > 0:
            contacts["preferred_channel"] = self.channel_combo.currentText().strip()

        if emerg_name := self.emerg_name_input.text().strip():
            contacts["emergency_name"] = emerg_name

        if self.emerg_rel_combo.currentIndex() > 0:
            contacts["emergency_relation"] = self.emerg_rel_combo.currentText().strip()

        if emerg_phone := self.emerg_phone_input.text().strip():
            contacts["emergency_phone"] = emerg_phone

        if self.emerg_consent_check.isChecked():
            contacts["emergency_consent"] = True

        return contacts

    def _on_cancel(self) -> None:
        self.router.back()

    def _on_next(self) -> None:
        contacts = self._collect_contacts()
        self.next_btn.setEnabled(False)
        self.call(
            self.facade.create_patient,
            contacts,
            on_success=self._on_created,
            on_error=self._on_create_error,
        )

    def _on_created(self, patient_id: str) -> None:
        self.next_btn.setEnabled(True)
        self.router.go(Route.ADD_SESSION, patient_id=patient_id)

    def _on_create_error(self, error: Exception) -> None:
        show_error(self, error)
        self.next_btn.setEnabled(True)

    def on_open(self, **params: Any) -> None:
        self.name_input.clear()
        self.birth_input.setDate(QDate.currentDate())
        self.phone_input.clear()
        self.email_input.clear()
        self.channel_combo.setCurrentIndex(0)
        self.emerg_name_input.clear()
        self.emerg_rel_combo.setCurrentIndex(0)
        self.emerg_phone_input.clear()
        self.emerg_consent_check.setChecked(False)
        self.phone_hint.setVisible(False)
        self.email_hint.setVisible(False)
        self.emerg_phone_hint.setVisible(False)
        self.next_btn.setEnabled(True)