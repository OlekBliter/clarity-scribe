"""Scrollable SOAP form without persistence or clinical business logic."""
from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from src.app.ui import metrics as M, strings as S
from src.app.ui.widgets.auto_height_text_edit import AutoHeightTextEdit
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.source_chip import SourceChip


class SoapPanel(QScrollArea):
    """Render editable SOAP fields and source references.

    Signals:
        source_clicked(int): Transcript identifier selected through a source chip.
    """

    source_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize an independently scrollable form."""
        super().__init__(parent)
        self.setObjectName("SoapScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editors: dict[str, AutoHeightTextEdit] = {}
        self.setMinimumWidth(M.SESSION_COLUMN_MIN_WIDTH)
        self.set_soap({})

    def set_soap(self, soap: dict[str, Any]) -> None:
        """Replace the form, preserving contract paths for future save actions."""
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self.editors.clear()
        body = QWidget()
        body.setObjectName("SoapBody")
        column = QVBoxLayout(body)
        column.setContentsMargins(*(M.CARD_PADDING,) * 4)
        column.setSpacing(M.SPACING)
        editable = bool(soap.get("editable", False))
        for key, heading in S.SOAP_SECTIONS:
            label = QLabel(heading)
            label.setObjectName("SectionTitle")
            column.addWidget(label)
            if key == "plan":
                plan = soap.get("plan", [])
                for index, item in enumerate(plan):
                    title, variant = S.PLAN_ORIGINS.get(
                        item.get("origin"), (S.PLAN_UNKNOWN, "neutral"))
                    column.addWidget(Badge(title, variant))
                    self._editor(column, f"plan[{index}].text", item.get("text", ""), editable)
                if not plan:
                    self._label(column, S.SESSION_EMPTY_SECTION)
                continue
            section = soap.get(key, {})
            self._editor(column, f"{key}.text", section.get("text", ""), editable)
            if key == "subjective" and section.get("sources"):
                self._label(column, S.SOAP_SOURCES)
                sources = QGridLayout()
                sources.setSpacing(M.SPACING_SMALL)
                for index, source in enumerate(section["sources"]):
                    chip = SourceChip(source["time"], source["segment_id"])
                    chip.setToolTip(source.get("quote", ""))
                    chip.segment_clicked.connect(self.source_clicked.emit)
                    sources.addWidget(chip, index // M.SOAP_SOURCE_COLUMNS,
                                      index % M.SOAP_SOURCE_COLUMNS)
                column.addLayout(sources)
            if key == "objective":
                for chip in section.get("chips", []):
                    title = S.METRIC_TITLES.get(chip["metric"], chip["metric"])
                    arrow = S.METRIC_ARROWS.get(chip.get("arrow"), "")
                    label = self._label(column, S.METRIC_CHIP.format(title=title, arrow=arrow).strip())
                    label.setObjectName("Chip")
                    label.setProperty("variant", "neutral")
                self._label(column, S.SOAP_BIOMARKER_HINT)
        column.addStretch()
        self.setWidget(body)

    def _editor(self, column: QVBoxLayout, path: str, text: str, editable: bool) -> None:
        """Add an auto-height field indexed by its facade edit path."""
        editor = AutoHeightTextEdit(text, editable)
        editor.setPlaceholderText(S.SESSION_EMPTY_SECTION)
        self.editors[path] = editor
        column.addWidget(editor)

    @staticmethod
    def _label(column: QVBoxLayout, text: str) -> QLabel:
        """Add wrapping plain text that cannot render transcript HTML."""
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        column.addWidget(label)
        return label
