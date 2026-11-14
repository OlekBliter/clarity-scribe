"""Animated in-screen panels for card sections and source quotes."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from shiboken6 import isValid
from src.app.ui.widgets.action_icon import ActionIcon
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from src.app.ui import metrics as M, strings as S
from src.app.ui.qt_helpers import fit_combo_popup
from src.app.ui.widgets.source_chip import SourceChip

BOOL_FIELDS = {"history.on_medication", "safety.suicidal_past",
               "safety.suicidal_now", "contacts.emergency_consent"}


def label(text: str, name: str = "Subtitle") -> QLabel:
    result = QLabel(text)
    result.setObjectName(name)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(True)
    return result


def value_text(value) -> str:
    if value is None:
        return S.MEDCARD_NONE
    if isinstance(value, bool):
        return S.MEDCARD_YES if value else S.MEDCARD_NO
    return str(value)


class CardPanel(QFrame):
    """Keep full content scrollable and apply local edits on close."""

    def __init__(self, host, title, fields, editable, apply, origin=None, remove_source=None) -> None:
        super().__init__(host)
        self.setObjectName("MedcardOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._apply = apply
        self._fields = fields
        self._editable = editable
        self.editors = {}
        self._sources = {f["field_id"]: list(f.get("sources", [])) for f in fields}
        self._old_focus = host.focusWidget()
        self.setGeometry(host.rect())
        self.box = QFrame(self)
        self.box.setObjectName("MedcardPanel")
        layout = QVBoxLayout(self.box)
        layout.setContentsMargins(*(M.CONTENT_MARGIN,) * 4)
        layout.setSpacing(M.SPACING)
        header = QHBoxLayout()
        header.addWidget(label(title, "SectionTitle"), 1)
        if remove_source is not None:
            remove = ActionIcon("trash", S.MEDCARD_REMOVE_SOURCE, self.box)
            def remove_and_close():
                remove_source()
                self.finish()
            remove.clicked.connect(remove_and_close)
            header.addWidget(remove)
        close = QPushButton(S.MEDCARD_PANEL_CLOSE)
        close.setObjectName("OutlineButton")
        close.setAccessibleName(S.MEDCARD_PANEL_CLOSE_LABEL)
        close.clicked.connect(self.finish)
        header.addWidget(close)
        layout.addLayout(header)
        if editable:
            layout.addWidget(label(S.MEDCARD_LOCAL_EDITS, "Muted"))
        scroll = QScrollArea(self.box)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(M.SPACING)
        for field in fields:
            key, value = field["field_id"], field["value"]
            column.addWidget(label(field["title"], "CardTitle"))
            if editable:
                if key in BOOL_FIELDS or isinstance(value, bool) or key == "hypotheses.risk":
                    editor = QComboBox()
                    editor.addItem(S.MEDCARD_NONE, None)
                    options = S.MEDCARD_RISKS if key == "hypotheses.risk" else {True: S.MEDCARD_YES, False: S.MEDCARD_NO}
                    for code, caption in options.items():
                        editor.addItem(caption, code)
                    if value is not None and editor.findData(value) < 0:
                        editor.addItem(str(value), value)
                    editor.setCurrentIndex(max(0, editor.findData(value)))
                    fit_combo_popup(editor)
                else:
                    editor = QPlainTextEdit()
                    editor.setPlainText("" if value is None else str(value))
                    editor.setFixedHeight(M.MEDCARD_PANEL_EDITOR_HEIGHT)
                editor.setAccessibleName(field["title"])
                self.editors[key] = editor
                column.addWidget(editor)
            else:
                full = QPlainTextEdit()
                full.setReadOnly(True)
                full.setPlainText(S.MEDCARD_RISKS.get(value, value_text(value))
                                  if key == "hypotheses.risk" else value_text(value))
                if key == "quote":
                    full.setMinimumHeight(M.MEDCARD_PANEL_EDITOR_HEIGHT)
                    column.addWidget(full, 1)
                else:
                    full.setFixedHeight(M.MEDCARD_PANEL_EDITOR_HEIGHT)
                    column.addWidget(full)
            if field.get("contradiction_text"):
                column.addWidget(label(field["contradiction_text"]))
            for source in field.get("sources", []):
                chip = SourceChip(source["time"], source["segment_id"], body)
                chip.setToolTip(source["quote"])
                row = QWidget(body)
                source_layout = QHBoxLayout(row)
                source_layout.setContentsMargins(0, 0, 0, 0)
                source_layout.addWidget(chip)
                chip.segment_clicked.connect(
                    lambda _id, src=source, key=key, row=row:
                    host._show_quote(src, key, self, row))
                source_layout.addStretch()
                column.addWidget(row)
        if not (len(fields) == 1 and fields[0]["field_id"] == "quote"):
            column.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(self.finish)
        self._animation = QPropertyAnimation(self.box, b"geometry", self)
        self._animation.setDuration(M.MEDCARD_PANEL_ANIMATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        target = self._target()
        start = origin.intersected(self.rect()) if origin else target.adjusted(
            M.MEDCARD_PANEL_INSET, M.MEDCARD_PANEL_INSET,
            -M.MEDCARD_PANEL_INSET, -M.MEDCARD_PANEL_INSET)
        self._animation.setStartValue(start if start.isValid() else target)
        self._animation.setEndValue(target)
        self.show()
        self.raise_()
        close.setFocus()
        self._animation.start()

    def _target(self) -> QRect:
        return self.rect().adjusted(*( (M.MEDCARD_PANEL_INSET,) * 2 +
                                      (-M.MEDCARD_PANEL_INSET,) * 2 ))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_animation"):
            self._animation.stop()
            self.box.setGeometry(self._target())

    def _remove_source(self, key, source, row) -> None:
        self._sources[key].remove(source)
        row.hide()
        row.deleteLater()

    def discard(self) -> None:
        self._animation.stop()
        if self in self.parentWidget()._panels:
            self.parentWidget()._panels.remove(self)
        self.hide()
        self.deleteLater()

    def finish(self) -> None:
        changes = {}
        for field in self._fields:
            key, original = field["field_id"], field["value"]
            editor = self.editors.get(key)
            if editor is None:
                continue
            if isinstance(editor, QComboBox):
                value = editor.currentData()
            else:
                value = editor.toPlainText()
                if original is None and value == "":
                    value = None
            if value != original:
                changes[key] = value
        if self in self.parentWidget()._panels:
            self.parentWidget()._panels.remove(self)
        source_changes = {
            field["field_id"]: self._sources[field["field_id"]]
            for field in self._fields
            if self._sources[field["field_id"]] != field.get("sources", [])
        }
        self._apply(changes, source_changes)
        self.hide()
        self.deleteLater()
        if self._old_focus is not None and isValid(self._old_focus):
            self._old_focus.setFocus()
