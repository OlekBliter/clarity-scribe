"""Налаштування застосунку.

Фасад (методи, які використовує цей екран):
  (поки немає в контракті фасаду: див. розділ 'Запити до фасаду' в роудмапі)

Параметри відкриття: див. on_open у README_UI.md (розділ "Маршрути").
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
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
from src.app.ui.qt_helpers import fit_combo_popup
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.buttons import outline_button, primary_button, secondary_button

_DEFAULT_BASE_DIR = Path.home() / "ClarityScribe"
_DEFAULT_DB_PATH = _DEFAULT_BASE_DIR / "clarity_scribe.db"
_DEFAULT_AUDIO_DIR = _DEFAULT_BASE_DIR / "audio"


class SettingsScreen(BaseScreen):
    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._channels_swapped = False

        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)

        # Заголовок поза прокруткою (за зразком screens/patients/screen.py)
        header = QHBoxLayout()
        title = QLabel(strings.SETTINGS_TITLE)
        title.setObjectName("ScreenTitle")
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(metrics.SPACING)
        content.setAlignment(Qt.AlignmentFlag.AlignTop)

        content.addWidget(self._build_audio_card())
        content.addWidget(self._build_privacy_card())
        content.addWidget(self._build_storage_card())

        holder = QWidget()
        holder.setLayout(content)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(holder)
        root.addWidget(scroll, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(metrics.SPACING)
        actions.addStretch(1)

        self._reset_btn = secondary_button(strings.SETTINGS_RESET)
        self._reset_btn.clicked.connect(self._on_reset)
        actions.addWidget(self._reset_btn)

        self._save_btn = primary_button(strings.SETTINGS_SAVE)
        self._save_btn.clicked.connect(self._on_save)
        actions.addWidget(self._save_btn)

        root.addLayout(actions)

    def on_open(self, **params: Any) -> None:
        """Екран статичний до підключення методів фасаду."""

    def _build_audio_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        layout.setSpacing(metrics.SPACING)

        title = QLabel(strings.SETTINGS_CARD_AUDIO)
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel(strings.SETTINGS_CHANNELS_LABEL))
        badges_row = QHBoxLayout()
        badges_row.setSpacing(metrics.SPACING)

        self._channel_0_badge = Badge()
        self._channel_1_badge = Badge()
        self._update_channel_badges()

        badges_row.addWidget(self._channel_0_badge)
        badges_row.addWidget(self._channel_1_badge)

        self._swap_channels_btn = outline_button(strings.SETTINGS_SWAP_CHANNELS)
        self._swap_channels_btn.clicked.connect(self._on_swap_channels)
        badges_row.addWidget(self._swap_channels_btn)

        badges_row.addStretch(1)
        layout.addLayout(badges_row)

        layout.addWidget(QLabel(strings.SETTINGS_LANGUAGE_LABEL))
        self._language_combo = QComboBox()
        self._language_combo.addItem(strings.SETTINGS_LANGUAGE_UK)
        fit_combo_popup(self._language_combo)
        layout.addWidget(self._language_combo)

        input_note = QLabel(strings.SETTINGS_INPUT_NOTE)
        input_note.setObjectName("Muted")
        input_note.setWordWrap(True)
        layout.addWidget(input_note)

        return card

    def _build_privacy_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        layout.setSpacing(metrics.SPACING)

        title = QLabel(strings.SETTINGS_CARD_PRIVACY)
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        anon_row = QHBoxLayout()
        anon_row.setSpacing(metrics.SPACING)
        anon_row.addWidget(QLabel(strings.SETTINGS_ANONYMIZATION_LABEL))
        anon_row.addWidget(Badge(strings.SETTINGS_ANONYMIZATION_BADGE, variant="success"))
        anon_row.addStretch(1)
        layout.addLayout(anon_row)

        layout.addWidget(QLabel(strings.SETTINGS_LLM_PROVIDER_LABEL))
        self._provider_combo = QComboBox()
        self._provider_combo.addItems(strings.SETTINGS_LLM_PROVIDERS)
        fit_combo_popup(self._provider_combo)
        layout.addWidget(self._provider_combo)

        layout.addWidget(QLabel(strings.SETTINGS_API_KEY_LABEL))
        api_row = QHBoxLayout()
        api_row.setSpacing(metrics.SPACING)

        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText(strings.SETTINGS_API_KEY_PLACEHOLDER)
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_row.addWidget(self._api_key_input, stretch=1)

        self._test_conn_btn = outline_button(strings.SETTINGS_TEST_CONNECTION)
        self._test_conn_btn.clicked.connect(self._on_test_connection)
        api_row.addWidget(self._test_conn_btn)
        layout.addLayout(api_row)

        return card

    def _build_storage_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        layout.setSpacing(metrics.SPACING)

        title = QLabel(strings.SETTINGS_CARD_STORAGE)
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel(strings.SETTINGS_DB_PATH_LABEL))
        db_row = QHBoxLayout()
        db_row.setSpacing(metrics.SPACING)

        self._db_path_input = QLineEdit(str(_DEFAULT_DB_PATH))
        self._db_path_input.setReadOnly(True)
        db_row.addWidget(self._db_path_input, stretch=1)

        open_db_btn = outline_button(strings.SETTINGS_OPEN_FOLDER)
        open_db_btn.clicked.connect(lambda: self._open_folder(Path(self._db_path_input.text()).parent))
        db_row.addWidget(open_db_btn)
        layout.addLayout(db_row)

        layout.addWidget(QLabel(strings.SETTINGS_AUDIO_PATH_LABEL))
        audio_row = QHBoxLayout()
        audio_row.setSpacing(metrics.SPACING)

        self._audio_path_input = QLineEdit(str(_DEFAULT_AUDIO_DIR))
        self._audio_path_input.setReadOnly(True)
        audio_row.addWidget(self._audio_path_input, stretch=1)

        open_audio_btn = outline_button(strings.SETTINGS_OPEN_FOLDER)
        open_audio_btn.clicked.connect(lambda: self._open_folder(Path(self._audio_path_input.text())))
        audio_row.addWidget(open_audio_btn)
        layout.addLayout(audio_row)

        encryption_note = QLabel(strings.SETTINGS_ENCRYPTION_NOTE)
        encryption_note.setObjectName("Muted")
        encryption_note.setWordWrap(True)
        layout.addWidget(encryption_note)

        return card

    def _update_channel_badges(self) -> None:
        if self._channels_swapped:
            ch0_role, ch0_variant = strings.SETTINGS_ROLE_PATIENT, "neutral"
            ch1_role, ch1_variant = strings.SETTINGS_ROLE_DOCTOR, "info"
        else:
            ch0_role, ch0_variant = strings.SETTINGS_ROLE_DOCTOR, "info"
            ch1_role, ch1_variant = strings.SETTINGS_ROLE_PATIENT, "neutral"

        self._channel_0_badge.setText(strings.SETTINGS_CHANNEL_FMT.format(index=0, role=ch0_role))
        self._channel_0_badge.set_variant(ch0_variant)

        self._channel_1_badge.setText(strings.SETTINGS_CHANNEL_FMT.format(index=1, role=ch1_role))
        self._channel_1_badge.set_variant(ch1_variant)

    def _on_swap_channels(self) -> None:
        self._channels_swapped = not self._channels_swapped
        self._update_channel_badges()

    def _open_folder(self, folder: Path) -> None:
        if not (folder.is_dir() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))):
            self.window().toast.show_message(strings.SETTINGS_FOLDER_MISSING)

    def _on_test_connection(self) -> None:
        self.window().toast.show_message(strings.TOAST_SOON)

    def _on_reset(self) -> None:
        self._channels_swapped = False
        self._update_channel_badges()
        self._language_combo.setCurrentIndex(0)
        self._provider_combo.setCurrentIndex(0)
        self._api_key_input.clear()
        self._db_path_input.setText(str(_DEFAULT_DB_PATH))
        self._audio_path_input.setText(str(_DEFAULT_AUDIO_DIR))
        self.window().toast.show_message(strings.SETTINGS_RESET_DONE)

    def _on_save(self) -> None:
        self.window().toast.show_message(strings.SETTINGS_SAVED_DEV)