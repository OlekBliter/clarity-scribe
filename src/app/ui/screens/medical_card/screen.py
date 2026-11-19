"""Initial-visit medical card screen. Review and approve a medical card."""
from __future__ import annotations

from typing import Any
from datetime import datetime
from functools import partial
from copy import deepcopy
from PySide6.QtCore import Qt, QRect, QDate
from PySide6.QtWidgets import (
    QMessageBox, QHBoxLayout, QLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from src.app.ui import metrics, strings as S
from src.app.ui.medcard_layout import MEDCARD_LAYOUT
from src.app.ui.widgets.action_icon import ActionIcon
from src.app.ui.qt_helpers import set_variant
from src.app.ui.router import Route
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.badge import Badge, badge_for
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import outline_button, primary_button
from src.app.ui.widgets.skeleton import Skeleton
from .components import CardBlock, CardColumns, ContactsBlock, text_label
from .panel import CardPanel


class MedicalCardScreen(BaseScreen):
    """Display all facade fields in two columns with shared scrolling."""

    def __init__(self, facade, router, parent=None) -> None:
        super().__init__(facade, router, parent)
        self._request_id = 0
        self._busy = False
        self._original = None
        self.editors = {}
        self._drafts = {}
        self._source_edits = {}
        self._panels = []
        self._data = None
        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        root.setSpacing(metrics.SPACING)
        top = QHBoxLayout()
        back = ActionIcon("back", S.BACK)
        back.clicked.connect(router.back)
        top.addWidget(back)
        self._crumb = Breadcrumb(self)
        self._crumb.setTextFormat(Qt.TextFormat.PlainText)
        self._crumb.setWordWrap(True)
        top.addWidget(self._crumb, 1)
        export = outline_button(S.MEDCARD_EXPORT)
        export.clicked.connect(lambda: self.window().toast.show_message(S.MEDCARD_SOON))
        top.addWidget(export)
        root.addLayout(top)
        heading = QHBoxLayout()
        self._title = text_label(S.MEDCARD_BREADCRUMB, "ScreenTitle")
        heading.addWidget(self._title, 1)
        self._badge = Badge(parent=self)
        heading.addWidget(self._badge)
        root.addLayout(heading)
        self._status = text_label("")
        root.addWidget(self._status)
        self._skeleton = Skeleton(metrics.MEDCARD_SKELETON_WIDTH,
                                  metrics.MEDCARD_SKELETON_HEIGHT, self)
        root.addWidget(self._skeleton)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(self._scroll, 1)
        footer = QHBoxLayout()
        footer.addStretch()
        self.save = outline_button(S.MEDCARD_SAVE)
        self.save.setObjectName("SessionSave")
        self.approve = primary_button(S.MEDCARD_APPROVE)
        self.save.clicked.connect(lambda: self._submit(False))
        self.approve.clicked.connect(lambda: self._submit(True))
        footer.addWidget(self.save)
        footer.addWidget(self.approve)
        root.addLayout(footer)

    def on_open(self, **params: Any) -> None:
        for panel in list(reversed(self._panels)):
            panel.discard()
        self._drafts.clear()
        self._source_edits.clear()
        self.review_started_at = datetime.now()
        self._busy = False
        self._original = None
        self.save.hide()
        self.approve.hide()
        self._scroll.setEnabled(True)
        self._request_id += 1
        request_id = self._request_id
        patient_id = params["patient_id"]
        self._patient_id = patient_id
        self.editors.clear()
        self._title.setText(S.MEDCARD_BREADCRUMB)
        self._crumb.set_path([S.NAV_PATIENTS, S.MEDCARD_BREADCRUMB])
        self._badge.hide()
        self._scroll.hide()
        old = self._scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._status.setText(S.MEDCARD_LOADING)
        self._status.show()
        self._skeleton.show()
        self.call(self.facade.get_card, patient_id,
                  on_success=lambda data: self._render_current(data, request_id),
                  on_error=lambda exc: self._failed(exc, patient_id, request_id))

    def _current(self, request_id: int) -> bool:
        return request_id == self._request_id and self.router.current_route == Route.MEDICAL_CARD

    def _render_current(self, data: dict, request_id: int) -> None:
        if not self._current(request_id):
            return
        self._original = data
        self._data = deepcopy(data)
        data = self._data
        draft = self._drafts
        if data["editable"]:
            for field in data["fields"]:
                if field["field_id"] in self._source_edits:
                    field["sources"] = deepcopy(self._source_edits[field["field_id"]])
                    field["edited_by_doctor"] = True
                if field["field_id"] in draft:
                    if field["state"] != "attention":
                        field["state"] = "normal"
                    field["contradiction_text"] = None
                    field["value"] = draft[field["field_id"]]
                    field["edited_by_doctor"] = True
            for key, value in draft.items():
                if key.startswith("contacts."):
                    data["contacts"][key.split(".", 1)[1]] = value
            if "contacts.birth_date" in draft:
                raw = data["contacts"]["birth_date"] or ""
                birth = QDate.fromString(raw, "yyyy-MM-dd")
                if not birth.isValid():
                    birth = QDate.fromString(raw, "dd.MM.yyyy")
                today = QDate.currentDate()
                data["contacts"]["age"] = (
                    today.year() - birth.year() -
                    ((today.month(), today.day()) < (birth.month(), birth.day()))
                    if birth.isValid() and birth <= today else None)
        self._skeleton.hide()
        self._status.hide()
        self._title.setText(S.MEDCARD_TITLE.format(date=data["date"]))
        self._crumb.set_path([S.NAV_PATIENTS, data["patient_name"] or S.NO_NAME,
                              S.MEDCARD_BREADCRUMB])
        caption, variant = badge_for(data["badge"])
        self._badge.setText(caption)
        self._badge.set_variant(variant)
        self._badge.setToolTip(S.MEDCARD_STATUSES.get(data["status"], data["status"]))
        self._badge.show()

        content = CardColumns()
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(metrics.SPACING)
        columns.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        fields = {field["field_id"]: field for field in data["fields"]}
        used = set()
        layouts = {}
        for column, blocks in MEDCARD_LAYOUT.items():
            holder = QWidget(content)
            holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            layout = QVBoxLayout(holder)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(metrics.SPACING)
            layout.addWidget(text_label(S.MEDCARD_COLUMNS[column], "SectionTitle"))
            for block, field_ids in blocks.items():
                if block == "contacts":
                    widget = ContactsBlock(data["contacts"], holder)
                else:
                    entries = [fields[field_id] for field_id in field_ids if field_id in fields]
                    used.update(field_ids)
                    if not entries:
                        continue
                    widget = CardBlock(S.MEDCARD_BLOCKS[block], entries, data["editable"], holder)
                    self.editors.update(widget.editors)
                widget.open_requested.connect(self._open_block)
                widget.source_requested.connect(self._open_source)
                widget.source_removed.connect(self._remove_source)
                layout.addWidget(widget)
            layouts[column] = layout
            columns.addWidget(holder, 1)
        remaining = [field for key, field in fields.items() if key not in used]
        if remaining:
            extra = CardBlock(S.MEDCARD_EXTRA, remaining, data["editable"], content)
            extra.open_requested.connect(self._open_block)
            extra.source_requested.connect(self._open_source)
            extra.source_removed.connect(self._remove_source)
            layouts["left"].addWidget(extra)
            self.editors.update(extra.editors)
        for layout in layouts.values():
            layout.addStretch()
        old = self._scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._scroll.setWidget(content)
        self._scroll.verticalScrollBar().setValue(0)
        self._scroll.show()
        self._update_actions()

    def _failed(self, exc: BaseException, patient_id: str, request_id: int) -> None:
        if not self._current(request_id):
            return
        self._skeleton.hide()
        self._status.setText(S.MEDCARD_ERROR)
        self._default_error(exc)
        # Check card presence through the contract instead of matching error text.
        self.call(self.facade.get_patient_profile, patient_id,
                  on_success=lambda profile: self._check_empty(profile, request_id),
                  on_error=lambda _exc: None)

    def _check_empty(self, profile: dict, request_id: int) -> None:
        if self._current(request_id):
            self._crumb.set_path([S.NAV_PATIENTS, profile["name"] or S.NO_NAME,
                                  S.MEDCARD_BREADCRUMB])
            if not profile["has_card"]:
                self._status.setText(S.MEDCARD_EMPTY)

    def _open_block(self, block) -> None:
        if isinstance(block, ContactsBlock):
            fields = [
                {"field_id": "contacts." + key, "title": title,
                 "value": self._data["contacts"].get(key)}
                for key, title in S.MEDCARD_CONTACTS.items()
            ]
        else:
            fields = [dict(field, title=S.MEDCARD_FIELDS.get(field["field_id"], field["field_id"]))
                      for field in block.fields]
        origin = QRect(block.mapTo(self, block.rect().topLeft()), block.size())
        panel = CardPanel(self, block.title, fields, self._data["editable"],
                          self._apply_changes, origin)
        self._panels.append(panel)

    def _apply_changes(self, changes: dict, source_changes: dict) -> None:
        if not changes and not source_changes:
            return
        originals = {f["field_id"]: f["value"] for f in self._original["fields"]}
        originals.update({"contacts." + k: v for k, v in self._original["contacts"].items()})
        for key, value in changes.items():
            if value == originals[key]:
                self._drafts.pop(key, None)
            else:
                self._drafts[key] = value
        self._source_edits.update(source_changes)
        position = self._scroll.verticalScrollBar().value()
        self._render_current(self._original, self._request_id)
        self._scroll.verticalScrollBar().setValue(position)

    def _update_actions(self):
        editable = bool(self._data and self._data["editable"])
        self.save.setVisible(editable)
        self.approve.setVisible(editable)
        self.save.setEnabled(not self._busy)
        self.approve.setEnabled(not self._busy)
        self._scroll.setEnabled(not self._busy)
        set_variant(self.save, "dirty" if self._drafts or self._source_edits else "clean")

    def _submit(self, approve: bool):
        if self._busy or self._panels or not self._data or not self._data["editable"]:
            return
        toast = self.window().toast.show_message
        if not approve and not (self._drafts or self._source_edits):
            toast(S.MEDCARD_NO_EDITS)
            return
        edits = [{"path": key, "new_value": value} for key, value in self._drafts.items()
                 if not key.startswith("contacts.")]
        contacts = {k.split(".", 1)[1]: v for k, v in self._drafts.items() if k.startswith("contacts.")}
        evidence = {key: [s["segment_id"] for s in sources] for key, sources in self._source_edits.items()}
        action = self.facade.approve_card if approve else self.facade.save_card
        if contacts or evidence:
            action = partial(action, contacts=contacts, evidence=evidence)
        if approve:
            box = QMessageBox(self)
            box.setWindowTitle(S.MEDCARD_APPROVE)
            box.setText(S.MEDCARD_CONFIRM_APPROVE)
            yes = box.addButton(S.MEDCARD_APPROVE, QMessageBox.ButtonRole.AcceptRole)
            cancel = box.addButton(S.CANCEL, QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel)
            box.setEscapeButton(cancel)
            box.exec()
            if box.clickedButton() is not yes:
                return
        position = self._scroll.verticalScrollBar().value()
        generation = self._request_id
        self._busy = True
        self._update_actions()

        def failed(error):
            if self._current(generation):
                self._busy = False
                self._update_actions()
                self._default_error(error)

        def saved(_result):
            if not self._current(generation):
                return
            self._drafts.clear()
            self._source_edits.clear()
            if not approve:
                toast(S.MEDCARD_SAVED)
            self.save.hide()
            self.approve.hide()
            self._scroll.hide()
            self._status.setText(S.MEDCARD_LOADING)
            self._status.show()
            self.call(self.facade.get_card, self._patient_id, on_success=reloaded,
                      on_error=lambda err: self._failed(err, self._patient_id, generation))

        def reloaded(card):
            if self._current(generation):
                self._busy = False
                self._render_current(card, generation)
                self._scroll.verticalScrollBar().setValue(position)

        self.call(action, self._patient_id, edits, self.review_started_at,
                  on_success=saved, on_error=failed)

    def _remove_source(self, source: dict, field_id: str) -> None:
        if not self._data or not self._data["editable"]:
            return
        field = next(f for f in self._data["fields"] if f["field_id"] == field_id)
        sources = list(self._source_edits.get(field_id, field["sources"]))
        if source in sources:
            sources.remove(source)
            self._apply_changes({}, {field_id: sources})

    def _open_source(self, source: dict, field_id=None) -> None:
        patient_id, request_id = self._patient_id, self._request_id

        def open_session(profile):
            if not self._current(request_id):
                return
            first = next((item for item in profile["sessions"] if item["number"] == 1), None)
            if first is None:
                return
            self.router.go(Route.SESSION, patient_id=patient_id,
                           session_id=first["session_id"], source_segment_id=source["segment_id"])

        self.call(self.facade.get_patient_profile, patient_id, on_success=open_session,
                  on_error=lambda exc: self.window().toast.show_message(str(exc)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        for panel in getattr(self, "_panels", []):
            panel.setGeometry(self.rect())

    def hideEvent(self, event) -> None:
        if self.router.current_route != Route.MEDICAL_CARD:
            for panel in list(reversed(self._panels)):
                panel.discard()
            self._drafts.clear()
            self._source_edits.clear()
            self._data = None
        super().hideEvent(event)
