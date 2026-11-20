"""Animated in-screen panels for card sections and source quotes."""
from __future__ import annotations

from PySide6.QtCore import QDate, QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from shiboken6 import isValid
from src.app.ui.widgets.action_icon import ActionIcon
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from src.app.ui import metrics as M, strings as S, validation
from src.app.ui.qt_helpers import fit_combo_popup
from src.app.ui.widgets.buttons import secondary_button
from src.app.ui.widgets.form_field import FormField
from src.app.ui.widgets.source_chip import SourceChip
from src.app.ui.widgets.flow_layout import FlowLayout

from src.schemas.contracts import BOOL_FIELDS


def label(text: str, name: str = "Subtitle") -> QLabel:
    result = QLabel(text)
    result.setObjectName(name)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(True)
    return result


_BIRTH_FORMATS = ("yyyy-MM-dd", "dd.MM.yyyy")
_EMERGENCY_TEXT = ("contacts.emergency_name", "contacts.emergency_relation",
                   "contacts.emergency_phone")


def parse_birth(text: str) -> QDate | None:
    """Дата з тексту (ISO або дд.мм.рррр); None, якщо не дата, з майбутнього або надто давня."""
    for fmt in _BIRTH_FORMATS:
        date = QDate.fromString(text.strip(), fmt)
        if date.isValid() and M.DATE_MIN_YEAR <= date.year() and date <= QDate.currentDate():
            return date
    return None


def value_text(value) -> str:
    if value is None:
        return S.MEDCARD_NONE
    if isinstance(value, bool):
        return S.MEDCARD_YES if value else S.MEDCARD_NO
    return str(value)


class CardPanel(QFrame):
    """Keep full content scrollable and apply local edits on close."""

    def __init__(self, host, title, fields, editable, apply, origin=None) -> None:
        super().__init__(host)
        self.setObjectName("MedcardOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._apply = apply
        self._fields = fields
        self._editable = editable
        self.editors = {}
        self._sources = {f["field_id"]: list(f.get("sources", [])) for f in fields}
        self._forms: dict[str, FormField] = {}
        self._old_focus = host.focusWidget()
        self.setGeometry(host.rect())
        self.box = QFrame(self)
        self.box.setObjectName("MedcardPanel")
        layout = QVBoxLayout(self.box)
        layout.setContentsMargins(*(M.CONTENT_MARGIN,) * 4)
        layout.setSpacing(M.SPACING)
        header = QHBoxLayout()
        header.addWidget(label(title, "SectionTitle"), 1)
        close = QPushButton(S.MEDCARD_PANEL_CLOSE)
        close.setObjectName("OutlineButton")
        close.setAccessibleName(S.MEDCARD_PANEL_CLOSE_LABEL)
        close.clicked.connect(self.finish)
        if editable:
            cancel = secondary_button(S.MEDCARD_PANEL_CANCEL)
            cancel.clicked.connect(self.discard)  # вийти без застосування (напр. при помилках)
            header.addWidget(cancel)
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
                if key in BOOL_FIELDS or key == "contacts.emergency_consent" or key == "hypotheses.risk":
                    editor = QComboBox()
                    editor.setPlaceholderText(S.MEDCARD_NONE)
                    options = S.MEDCARD_RISKS if key == "hypotheses.risk" else {True: S.MEDCARD_YES, False: S.MEDCARD_NO}
                    for code, caption in options.items():
                        editor.addItem(caption, code)
                    editor.setCurrentIndex(editor.findData(value) if value is not None else -1)
                    fit_combo_popup(editor)
                else:
                    editor = QPlainTextEdit()
                    editor.setPlainText("" if value is None else str(value))
                    editor.setFixedHeight(M.MEDCARD_PANEL_EDITOR_HEIGHT)
                editor.setAccessibleName(field["title"])
                self.editors[key] = editor
                form = FormField(None, editor, self._error_fn(key, editor, value))
                self._forms[key] = form
                form.changed.connect(self._refresh_forms)
                column.addWidget(form)
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
            sources = FlowLayout()
            for source in field.get("sources", []):
                chip = SourceChip(source["time"], source["segment_id"], body)
                chip.setToolTip(source["quote"])
                chip.set_removable(editable)
                chip.remove_requested.connect(
                    lambda _id, src=source, key=key, chip=chip:
                    self._remove_source(key, src, chip))
                chip.segment_clicked.connect(
                    lambda _id, src=source, key=key, row=chip:
                    host._open_source(src, key))
                sources.addWidget(chip)
            column.addLayout(sources)
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

    # ---- валідація правок ----
    def _text(self, key: str) -> str:
        editor = self.editors.get(key)
        return editor.toPlainText().strip() if isinstance(editor, QPlainTextEdit) else ""

    def _emergency_active(self) -> bool:
        """Екстрений контакт «в роботі»: заповнено хоч щось (текст або згода «Так»)."""
        consent = self.editors.get("contacts.emergency_consent")
        return (any(self._text(key) for key in _EMERGENCY_TEXT)
                or (isinstance(consent, QComboBox) and consent.currentData() is True))

    def _error_fn(self, key: str, editor, original):
        """Помилка поля. Незмінене значення не перевіряємо: старі дані не блокують вихід."""
        def error() -> str | None:
            if isinstance(editor, QPlainTextEdit):
                text = editor.toPlainText()
                unchanged = text == ("" if original is None else str(original))
                needs_fill = (key in _EMERGENCY_TEXT and not text.strip()
                              and self._emergency_active())
                if unchanged and not needs_fill:
                    return None
                return self._text_error(key, text)
            if key == "contacts.emergency_consent" and self._emergency_active():
                return None if editor.currentData() is True else S.VALIDATION_CONSENT
            return None
        return error

    def _text_error(self, key: str, text: str) -> str | None:
        if not key.startswith("contacts."):
            return (S.VALIDATION_MAX_LEN.format(max=M.MEDCARD_TEXT_MAX_LEN)
                    if len(text) > M.MEDCARD_TEXT_MAX_LEN else None)
        if key in _EMERGENCY_TEXT and not text.strip():
            return S.VALIDATION_REQUIRED if self._emergency_active() else None
        checks = {
            "contacts.preferred_name": validation.validate_name,
            "contacts.phone": validation.validate_phone,
            "contacts.email": validation.validate_email,
            "contacts.preferred_channel": validation.validate_other,
            "contacts.emergency_name": validation.validate_name,
            "contacts.emergency_relation": validation.validate_other,
            "contacts.emergency_phone": validation.validate_phone,
        }
        if key == "contacts.birth_date":
            return None if parse_birth(text) else S.VALIDATION_BIRTH_FORMAT
        return checks[key](text) if key in checks else None

    def _refresh_forms(self) -> None:
        for form in self._forms.values():
            form.refresh()

    def _first_invalid(self):
        return next((f for f in self._forms.values() if f.error()), None)

    def finish(self) -> None:
        invalid = self._first_invalid()
        if invalid is not None:  # панель не закривається, поки правки некоректні
            for form in self._forms.values():
                form.touch()
            invalid.widget.setFocus()
            return
        changes = {}
        for field in self._fields:
            key, original = field["field_id"], field["value"]
            editor = self.editors.get(key)
            if editor is None:
                continue
            if isinstance(editor, QComboBox):
                if editor.currentIndex() < 0:
                    continue
                value = editor.currentData()
            else:
                value = editor.toPlainText()
                if value == (original or ""):
                    continue
                if not value.strip():
                    value = None if key.startswith("contacts.") else "-"
                elif key == "contacts.phone" or key == "contacts.emergency_phone":
                    value = validation.normalize_phone(value) or value
                elif key == "contacts.birth_date":
                    value = parse_birth(value).toString("yyyy-MM-dd")
                elif key.startswith("contacts."):
                    value = validation.collapse_spaces(value)
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
