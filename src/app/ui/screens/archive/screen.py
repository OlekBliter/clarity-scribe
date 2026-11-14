"""Архів пацієнтів.

Параметри відкриття: див. on_open у README_UI.md (розділ "Маршрути").
"""
from __future__ import annotations

from PySide6.QtCore import Qt
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

from src.app.ui import strings
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.buttons import outline_button, secondary_button


class ArchiveRow(QFrame):
    """Рядок архівного пацієнта (стиль PatientCard)."""
    def __init__(
        self,
        name: str,
        subtitle: str,
        status_text: str,
        status_variant: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PatientCard")
        self.name = name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("CardTitle")
        info_layout.addWidget(self.name_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("Muted")
        info_layout.addWidget(self.subtitle_label)

        layout.addLayout(info_layout, stretch=1)

        self.badge = Badge(status_text, variant=status_variant)
        layout.addWidget(self.badge)

        self.restore_btn = outline_button(strings.BTN_RESTORE)
        self.restore_btn.clicked.connect(self._show_soon)
        layout.addWidget(self.restore_btn)

        self.view_btn = secondary_button(strings.BTN_VIEW)
        self.view_btn.clicked.connect(self._show_soon)
        layout.addWidget(self.view_btn)

    def _show_soon(self) -> None:
        main_win = self.window()
        if hasattr(main_win, "toast") and main_win.toast:
            main_win.toast.show_message(strings.TOAST_SOON)


class ArchiveScreen(BaseScreen):
    """Екран «Архів» (статична заглушка з пошуком у пам'яті)."""

    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._row_widgets: list[ArchiveRow] = []
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        title_label = QLabel(strings.ARCHIVE_TITLE)
        title_label.setObjectName("ScreenTitle")
        main_layout.addWidget(title_label)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(strings.ARCHIVE_SEARCH_PLACEHOLDER)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_patients)
        controls_layout.addWidget(self.search_input, stretch=2)

        self.status_combo = QComboBox()
        self.status_combo.addItem(strings.ARCHIVE_STATUS_ALL)
        controls_layout.addWidget(self.status_combo, stretch=1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem(strings.ARCHIVE_SORT_DEFAULT)
        controls_layout.addWidget(self.sort_combo, stretch=1)

        main_layout.addLayout(controls_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(12)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

        patients_data = [
            {
                "name": strings.PATIENT_SIDORENKO,
                "subtitle": strings.ARCHIVE_SUBTITLE,
                "status_text": strings.STATUS_COMPLETED,
                "variant": "success",
            },
            {
                "name": strings.PATIENT_HRYHORENKO,
                "subtitle": strings.ARCHIVE_SUBTITLE,
                "status_text": strings.STATUS_SUSPENDED,
                "variant": "warning",
            },
            {
                "name": strings.PATIENT_LYSENKO,
                "subtitle": strings.ARCHIVE_SUBTITLE,
                "status_text": strings.STATUS_INTERRUPTED,
                "variant": "neutral",
            },
            {
                "name": strings.PATIENT_KRAVCHUK,
                "subtitle": strings.ARCHIVE_SUBTITLE,
                "status_text": strings.STATUS_COMPLETED,
                "variant": "success",
            },
        ]

        for p in patients_data:
            row = ArchiveRow(
                name=p["name"],
                subtitle=p["subtitle"],
                status_text=p["status_text"],
                status_variant=p["variant"],
            )
            self.container_layout.addWidget(row)
            self._row_widgets.append(row)

        self.empty_label = QLabel(strings.ARCHIVE_EMPTY)
        self.empty_label.setObjectName("Muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        self.container_layout.addWidget(self.empty_label)

    def _filter_patients(self, text: str) -> None:
        query = text.strip().lower()
        visible_count = 0
        for row in self._row_widgets:
            matches = query in row.name.lower()
            row.setVisible(matches)
            if matches:
                visible_count += 1
        self.empty_label.setVisible(visible_count == 0)

    def on_open(self, **params) -> None:
        pass