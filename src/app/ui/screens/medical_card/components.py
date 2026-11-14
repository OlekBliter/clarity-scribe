"""Compact medical card sections with consistent spacing."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate, Signal, QEvent, Property, QVariantAnimation, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from src.app.ui.widgets.action_icon import ActionIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from src.app.ui import metrics, strings as S
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.source_chip import SourceChip
from .preview import TextPreview
from .panel import label as text_label, value_text as display_value



class CardBlock(QFrame):
    """Render neutral, compact previews and expose section actions."""

    open_requested = Signal(object)
    source_requested = Signal(object, str)

    def __init__(self, title: str, fields: list[dict], editable: bool, parent=None) -> None:
        super().__init__(parent)
        self.title, self.fields, self.editable = title, fields, editable
        self._accent = QColor("#0D9488")
        self._hover = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(140)
        self._animation.valueChanged.connect(self._set_hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)
        self.setToolTip(S.MEDCARD_OPEN_BLOCK)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        self.column.setSpacing(metrics.SPACING)
        self.column.setAlignment(Qt.AlignmentFlag.AlignTop)
        header = QHBoxLayout()
        header.addWidget(text_label(title, "SectionTitle"), 1)
        self.column.addLayout(header)
        self.editors = {}
        for field in fields:
            self._add_field(field)

    def _set_accent(self, color) -> None:
        self._accent = QColor(color)
        self.update()

    accentColor = Property(QColor, lambda self: self._accent, _set_accent)

    def _set_hover(self, value) -> None:
        self._hover = float(value)
        self.update()

    def _animate(self, active) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._hover)
        self._animation.setEndValue(1.0 if active else 0.0)
        self._animation.start()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._animate(True)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._animate(False)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        strength = max(self._hover, 1.0 if self.hasFocus() else 0.0)
        if not strength:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._accent)
        color.setAlphaF(strength)
        painter.setPen(QPen(color, 1.5))
        color.setAlphaF(strength * 0.045)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 11, 11)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.open_requested.emit(self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not event.isAutoRepeat():
                self.open_requested.emit(self)
            event.accept()
        else:
            super().keyPressEvent(event)

    def event(self, event) -> bool:
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest and hasattr(self, "column"):
            self._fit_height()
        return result

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_height()

    def _fit_height(self) -> None:
        height = self.column.totalHeightForWidth(self.width())
        if height > 0 and self.height() != height:
            self.setFixedHeight(height)

    def _add_field(self, field: dict) -> None:
        key = field["field_id"]
        self.column.addWidget(text_label(S.MEDCARD_FIELDS.get(key, key), "CardTitle"))
        origin = (S.MEDCARD_DOCTOR if key.startswith(("scales.", "hypotheses.", "agreements."))
                  else S.MEDCARD_CONVERSATION if field["state"] == "from_conversation" or field["sources"]
                  else "")
        caption = S.MEDCARD_EDITED if field["edited_by_doctor"] else origin
        if caption:
            metadata = text_label(caption, "Muted")
            if field["edited_by_doctor"] and origin:
                metadata.setToolTip(origin)
            self.column.addWidget(metadata)
        if field["state"] == "attention":
            self._badge(S.MEDCARD_ATTENTION, "danger")
        elif field["state"] == "contradictory":
            self._badge(S.MEDCARD_CONTRADICTORY, "warning")
        value = field["value"]
        caption = S.MEDCARD_RISKS.get(value, display_value(value)) if key == "hypotheses.risk" else display_value(value)
        self.column.addWidget(TextPreview(caption))
        if field["contradiction_text"]:
            self.column.addWidget(TextPreview(field["contradiction_text"]))
        for source in field["sources"][:metrics.MEDCARD_PREVIEW_SOURCES]:
            chip = SourceChip(source["time"], source["segment_id"], self)
            chip.setToolTip(source["quote"])
            chip.segment_clicked.connect(lambda _id, src=source, key=key: self.source_requested.emit(src, key))
            self.column.addWidget(chip, alignment=Qt.AlignmentFlag.AlignLeft)

    def _badge(self, caption: str, variant: str) -> None:
        badge = Badge(caption, variant, self)
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.column.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)


class ContactsBlock(CardBlock):
    """Local contacts, including consent and age from the facade."""

    def __init__(self, contacts: dict, parent=None) -> None:
        super().__init__(S.MEDCARD_BLOCKS["contacts"], [], False, parent)
        self.contacts = contacts
        local = QHBoxLayout()
        lock = ActionIcon("lock", S.MEDCARD_LOCAL, self)
        lock.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lock.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        local.addWidget(lock)
        local.addWidget(text_label(S.MEDCARD_LOCAL, "Muted"), 1)
        self.column.addLayout(local)
        for key, caption in S.MEDCARD_CONTACTS.items():
            value = display_value(contacts.get(key))
            if key == "birth_date":
                raw = contacts.get(key)
                parsed = QDate.fromString(raw or "", "yyyy-MM-dd")
                if parsed.isValid():
                    value = parsed.toString("dd.MM.yyyy")
                age = contacts.get("age")
                if age is not None:
                    last, last_two = age % 10, age % 100
                    unit = S.MEDCARD_AGE_UNITS[0 if last == 1 and last_two != 11 else
                                               1 if 2 <= last <= 4 and not 12 <= last_two <= 14 else 2]
                    value = S.MEDCARD_BIRTH_AGE.format(birth=value, age=age, unit=unit)
            self.column.addWidget(text_label(caption, "CardTitle"))
            self.column.addWidget(TextPreview(value))

class CardColumns(QWidget):
    """Calculate column heights using the actual text width."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.layout().activate()
        heights = []
        for index in range(self.layout().count()):
            holder = self.layout().itemAt(index).widget()
            column = holder.layout()
            height = column.totalHeightForWidth(holder.width())
            heights.append(height if height >= 0 else column.sizeHint().height())
        self.setMinimumHeight(max(heights, default=0))
