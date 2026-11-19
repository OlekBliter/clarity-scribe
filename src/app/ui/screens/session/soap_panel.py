"""Scrollable SOAP form without persistence or clinical business logic."""
from __future__ import annotations

from typing import Any
from copy import deepcopy

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from src.app.ui import metrics as M, strings as S
from src.app.ui.qt_helpers import repolish, set_variant
from src.app.ui.widgets.auto_height_text_edit import AutoHeightTextEdit
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.card import Card
from src.app.ui.widgets.source_chip import SourceChip
from src.app.ui.widgets.flow_layout import FlowLayout


class CopyButton(QPushButton):
    """Copy-style button that briefly confirms the action, keeping a stable width."""

    def __init__(self, object_name: str, parent: QWidget | None = None) -> None:
        """Create a button styled through the given QSS object name."""
        super().__init__(S.SOAP_COPY, parent)
        self.setObjectName(object_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._idle_text = S.SOAP_COPY
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(M.SOAP_COPY_FEEDBACK_MS)
        self._timer.timeout.connect(self._reset)

    def set_idle_text(self, text: str) -> None:
        """Change the resting caption."""
        self._idle_text = text
        if not self._timer.isActive():
            self.setText(text)
        self.updateGeometry()

    def flash(self) -> None:
        """Show the confirmation caption for a short moment."""
        self.setText(S.SOAP_COPIED)
        self.setProperty("copied", "true")
        repolish(self)
        self._timer.start()

    def _reset(self) -> None:
        """Return to the resting caption."""
        self.setText(self._idle_text)
        self.setProperty("copied", "false")
        repolish(self)

    def sizeHint(self) -> QSize:
        """Reserve room for the longer of the two captions so the layout never jumps."""
        hint = super().sizeHint()
        metrics = self.fontMetrics()
        widest = max(metrics.horizontalAdvance(self._idle_text),
                     metrics.horizontalAdvance(S.SOAP_COPIED))
        extra = max(0, widest - metrics.horizontalAdvance(self.text()))
        return QSize(hint.width() + extra, hint.height())

    def minimumSizeHint(self) -> QSize:
        """Never shrink below the stable size."""
        return self.sizeHint()


class SoapPanel(QScrollArea):
    """Render editable SOAP fields and source references.

    Each of S/O/A/P is a card matching the medical-card blocks.

    Signals:
        source_clicked(int): Transcript identifier selected through a source chip.
    """

    source_clicked = Signal(int)
    sources_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize an independently scrollable form."""
        super().__init__(parent)
        self.setObjectName("SoapScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editors: dict[str, AutoHeightTextEdit] = {}
        self._section_paths: dict[str, list[str]] = {}
        self.setMinimumWidth(M.SESSION_COLUMN_MIN_WIDTH)
        self.set_soap({})

    def set_soap(self, soap: dict[str, Any]) -> None:
        """Replace the form, preserving contract paths for future save actions."""
        self._displayed_soap = deepcopy(soap)
        self.sources = {key: deepcopy(soap.get(key, {}).get("sources", []))
                        for key in ("subjective", "objective", "assessment")}
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self.editors.clear()
        self._section_paths.clear()
        body = QWidget()
        body.setObjectName("SoapBody")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, M.SOAP_SCROLL_GUTTER, 0)
        column.setSpacing(M.SPACING)
        editable = bool(soap.get("editable", False))
        for key, heading in S.SOAP_SECTIONS:
            self._section_paths[key] = []
            card = self._card(key, heading)
            box = card.layout()
            assert isinstance(box, QVBoxLayout)
            if key == "plan":
                plan = soap.get("plan", [])
                for index, item in enumerate(plan):
                    title, variant = S.PLAN_ORIGINS.get(
                        item.get("origin"), (S.PLAN_UNKNOWN, "neutral"))
                    # Badge and text share one inner block, so the status clearly
                    # belongs to the item below it.
                    block = QFrame()
                    block.setObjectName("PlanItem")
                    inner = QVBoxLayout(block)
                    inner.setContentsMargins(*(M.SPACING,) * 4)
                    inner.setSpacing(M.SPACING_SMALL * 2)
                    inner.addWidget(Badge(title, variant), alignment=Qt.AlignmentFlag.AlignLeft)
                    self._editor(inner, f"plan[{index}].text", item.get("text", ""),
                                 editable, key, heading)
                    box.addWidget(block)
                if not plan:
                    self._label(box, S.SESSION_EMPTY_SECTION, "Muted")
                column.addWidget(card)
                continue
            section = soap.get(key, {})
            self._editor(box, f"{key}.text", section.get("text", ""), editable, key, heading)
            if self.sources.get(key):
                sources_label = self._label(box, S.SOAP_SOURCES, "Muted")
                sources = FlowLayout()
                for source in list(self.sources[key]):
                    chip = SourceChip(source["time"], source["segment_id"])
                    chip.setToolTip(source.get("quote", ""))
                    chip.segment_clicked.connect(self.source_clicked.emit)
                    chip.set_removable(editable)
                    chip.remove_requested.connect(
                        lambda _id, k=key, src=source, c=chip, layout=sources, label=sources_label:
                        self._remove_source(k, src, c, layout, label))
                    sources.addWidget(chip)
                box.addLayout(sources)
            if key == "objective":
                chips = FlowLayout()
                for chip in section.get("chips", []):
                    title = S.METRIC_TITLES.get(chip["metric"], chip["metric"])
                    arrow = S.METRIC_ARROWS.get(chip.get("arrow"), "")
                    label = QLabel(S.METRIC_CHIP.format(title=title, arrow=arrow).strip())
                    label.setTextFormat(Qt.TextFormat.PlainText)
                    label.setObjectName("Chip")
                    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
                    # Same encoding as the dynamics screen: rising = warning, falling = info.
                    set_variant(label, {"up": "warning", "down": "info"}.get(
                        chip.get("arrow"), "neutral"))
                    chips.addWidget(label)
                box.addLayout(chips)
                self._label(box, S.SOAP_BIOMARKER_HINT, "Muted")
            column.addWidget(card)
        column.addStretch()
        self.setWidget(body)

    def export_data(self) -> dict[str, Any]:
        """Capture the displayed document, including local edits and source removals."""
        data = deepcopy(self._displayed_soap)
        for key, paths in self._section_paths.items():
            if key == "plan":
                for item, path in zip(data.get(key, []), paths):
                    item["text"] = self.editors[path].toPlainText()
            else:
                data.setdefault(key, {})["text"] = self.editors[f"{key}.text"].toPlainText()
                data[key]["sources"] = deepcopy(self.sources[key])
        return data

    def section_text(self, key: str) -> str:
        """Return the current (possibly edited) text of one SOAP block."""
        paths = self._section_paths.get(key, [])
        texts = [self.editors[path].toPlainText().strip() for path in paths]
        texts = [text for text in texts if text]
        if key == "plan":
            return "\n".join(S.SOAP_PLAN_LINE.format(text=text) for text in texts)
        return "\n".join(texts)

    def note_text(self) -> str:
        """Return the whole note as plain text, skipping empty blocks."""
        parts = []
        for key, heading in S.SOAP_SECTIONS:
            text = self.section_text(key)
            if text:
                parts.append(f"{heading}\n{text}")
        return "\n\n".join(parts)

    def copy_section(self, key: str) -> None:
        """Copy one block to the clipboard."""
        QGuiApplication.clipboard().setText(self.section_text(key))

    def copy_note(self) -> None:
        """Copy the whole note to the clipboard."""
        QGuiApplication.clipboard().setText(self.note_text())

    def _card(self, key: str, heading: str) -> Card:
        """Create a block card with a letter badge, title and copy action."""
        card = Card()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        box = QVBoxLayout(card)
        box.setContentsMargins(*(M.CARD_PADDING,) * 4)
        box.setSpacing(M.SPACING)
        header = QHBoxLayout()
        header.setSpacing(M.SPACING)
        letter = QLabel(key[:1].upper())
        letter.setObjectName("SoapLetter")
        letter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        letter.setFixedSize(M.SOAP_LETTER_SIZE, M.SOAP_LETTER_SIZE)
        title = QLabel(heading)
        title.setObjectName("SectionTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        copy = CopyButton("SoapCopy")
        copy.setAccessibleName(S.SOAP_COPY_BLOCK.format(title=heading))
        copy.setToolTip(S.SOAP_COPY_BLOCK.format(title=heading))
        copy.clicked.connect(lambda _checked=False, k=key, b=copy: (self.copy_section(k), b.flash()))
        align = Qt.AlignmentFlag.AlignVCenter
        header.addWidget(letter, 0, align)
        header.addWidget(title, 1, align)
        header.addWidget(copy, 0, align)
        box.addLayout(header)
        return card

    def _editor(self, column: QVBoxLayout, path: str, text: str, editable: bool,
                section: str = "", heading: str = "") -> None:
        """Add an auto-height field indexed by its facade edit path."""
        editor = AutoHeightTextEdit(text, editable)
        editor.setPlaceholderText(S.SESSION_EMPTY_SECTION)
        if heading:
            editor.setAccessibleName(heading)
        self.editors[path] = editor
        if section:
            self._section_paths.setdefault(section, []).append(path)
        column.addWidget(editor)

    @staticmethod
    def _label(column: QVBoxLayout, text: str, name: str = "") -> QLabel:
        """Add wrapping plain text that cannot render transcript HTML."""
        label = QLabel(text)
        if name:
            label.setObjectName(name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        column.addWidget(label)
        return label

    def _remove_source(self, key, source, chip, layout, label) -> None:
        if source not in self.sources[key]:
            return
        self.sources[key].remove(source)
        layout.removeWidget(chip)
        chip.hide()
        chip.deleteLater()
        label.setVisible(bool(self.sources[key]))
        layout.invalidate()
        self.sources_changed.emit(key, deepcopy(self.sources[key]))
