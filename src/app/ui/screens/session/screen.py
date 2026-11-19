"""Session review screen: async loading, local editing, and audio navigation."""
from __future__ import annotations

import math
from datetime import datetime
from functools import partial
from typing import Any, cast

from PySide6.QtGui import QHideEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget
from src.app.ui import strings as S
from src.app.ui.qt_helpers import set_variant
from src.app.ui.router import Router
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.badge import badge_for
from src.app.ui.widgets.toast import Toast
from src.app.ui.widgets.transcript_view import Segment
from src.app.workers.waveform_worker import load_waveform
from src.services.facade.facade import ClarityScribeFacade
from .view import SessionView


class SessionScreen(BaseScreen):
    """Display one session and coordinate UI-only interactions.

    Attributes:
        session_id: Currently opened session identifier.
        review_started_at: Local review start time retained for K3.
    """

    def __init__(self, facade: ClarityScribeFacade, router: Router,
                 parent: QWidget | None = None) -> None:
        """Initialize the view and connect user interactions once."""
        super().__init__(facade, router, parent)
        self.session_id: str | None = None
        self.review_started_at: datetime | None = None
        self._generation = 0
        self._active = False
        self._data: dict[str, Any] = {}
        self._errors: dict[str, str] = {}
        self._pending: set[str] = set()
        self._segments: list[Segment] = []
        self._selected_id: int | None = None
        self._duration = 0.0
        self._audio_available = False
        self._fallback_toast: Toast | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = SessionView(self)
        layout.addWidget(self.view)
        # Delegate navigation to Router so its can_leave guard remains active.
        self.view.back_requested.connect(self.router.back)
        self.view.audio.position_changed.connect(self._position_changed)
        self.view.wave.seek_requested.connect(self._seek_fraction)
        self.view.transcript.segment_clicked.connect(self.view.audio.seek)
        self.view.soap.source_clicked.connect(self._source_clicked)
        self.view.audio.player.durationChanged.connect(self._duration_changed)
        self.view.audio.player.errorOccurred.connect(self._audio_error)
        self._originals: dict[str, str | list[int]] = {}
        self._busy = False
        self.view.soap.sources_changed.connect(self._update_actions)
        self.view.save.clicked.connect(self._save)
        self.view.approve.clicked.connect(self._approve)
        self.view.delete.clicked.connect(self._delete)
        self.view.export.clicked.connect(self._soon)

    def on_open(self, **params: Any) -> None:
        """Start all four facade requests and remember this review's timestamp.

        Args:
            **params: Router parameters containing session_id and patient_id.
        """
        self._generation += 1
        self._active = True
        self.session_id = params["session_id"]
        self._requested_source = params.get("source_segment_id")
        self.review_started_at = datetime.now()
        self._originals.clear()
        self._busy = False
        self._data.clear()
        self._errors.clear()
        self._segments.clear()
        self._selected_id = None
        self._duration = 0.0
        self._audio_available = False
        self.view.audio.set_source(None)
        self.view.wave.set_peaks([])
        self.view.wave.set_position(0.0)
        self.view.wave.setEnabled(False)
        self.view.transcript.search.clear()
        self.view.transcript.set_segments([])
        self.view.soap.set_soap({})
        self.view.title.clear()
        self.view.badge.hide()
        self.view.crumb.set_path([S.NAV_PATIENTS])
        self.view.set_state("loading")
        self._pending = {"soap", "transcript", "audio", "waveform"}
        generation = self._generation
        for key, fn in (("soap", self.facade.get_soap),
                        ("transcript", self.facade.get_transcript),
                        ("audio", self.facade.get_audio_info)):
            self.call(fn, self.session_id,
                      on_success=partial(self._loaded, generation, key),
                      on_error=partial(self._failed, generation, key))
        load_waveform(self.facade.get_waveform, self.session_id, owner=self,
                      on_success=partial(self._loaded, generation, "waveform"),
                      on_error=partial(self._failed, generation, "waveform"))

    def _loaded(self, generation: int, key: str, result: Any) -> None:
        """Accept only results for the currently visible review."""
        if not self._active or generation != self._generation:
            return
        self._data[key] = result
        self._pending.discard(key)
        self._finish_loading()

    def _failed(self, generation: int, key: str, error: BaseException) -> None:
        """Navigate back on SOAP failure; allow partial auxiliary-data failures."""
        if not self._active or generation != self._generation:
            return
        message = str(error) or S.ERROR_GENERIC
        self._errors[key] = message
        self._pending.discard(key)
        if key == "soap":
            self._active = False
            self.view.set_state("error", message)
            self._toast(message)
            self.router.back()
            return
        self._toast(S.SESSION_LOAD_ERROR.format(part=S.SESSION_PARTS[key], error=message))
        self._finish_loading()

    def _finish_loading(self) -> None:
        """Render once every request has either returned or failed."""
        if self._pending:
            return
        soap = self._data.get("soap")
        if not soap:
            self.view.set_state("empty", S.SESSION_EMPTY)
            return
        self.view.title.setText(S.SESSION_ROW_TITLE.format(
            number=soap["number"], date=soap["date"]))
        self.view.crumb.set_path([S.NAV_PATIENTS, soap["patient_name"],
                                  S.SESSION_CRUMB.format(number=soap["number"])])
        self._render_soap(soap)
        self._segments = sorted(cast(list[Segment], self._data.get("transcript") or []),
                                key=lambda s: s["start"])
        self.view.transcript.set_segments(self._segments)
        message = self._errors.get("transcript", "")
        self.view.transcript_status.setText(
            S.SESSION_TRANSCRIPT_ERROR if message else S.SESSION_TRANSCRIPT_EMPTY)
        self.view.transcript_status.setVisible(bool(message) or not self._segments)
        info = self._data.get("audio") or {}
        duration = float(info.get("duration", 0.0))
        self._duration = max(0.0, duration) if math.isfinite(duration) else 0.0
        self.view.audio.set_source(info.get("path"))
        self._audio_available = self.view.audio.isEnabled()
        self.view.wave.setEnabled(self._audio_available)
        peaks = self._data.get("waveform") or []
        self.view.wave.set_peaks(peaks if self._audio_available else [])
        if "audio" in self._errors:
            audio_message = S.SESSION_AUDIO_ERROR
        elif not self._audio_available:
            audio_message = S.SESSION_NO_AUDIO
        elif "waveform" in self._errors:
            audio_message = S.SESSION_WAVE_ERROR
        elif not peaks:
            audio_message = S.SESSION_WAVE_EMPTY
        else:
            audio_message = ""
        self.view.audio_status.setText(audio_message)
        self.view.audio_status.setVisible(bool(audio_message))
        self.view.set_state("ready")
        if self._requested_source is not None:
            segment_id, self._requested_source = self._requested_source, None
            self.view._show_source(segment_id)
            self._source_clicked(segment_id)

    def _render_soap(self, soap: dict[str, Any]) -> None:
        self._data["soap"] = soap
        text, variant = badge_for(soap.get("badge"))
        self.view.badge.setText(text)
        self.view.badge.set_variant(variant)
        self.view.badge.setVisible(bool(text))
        self.view.soap.setEnabled(True)
        self.view.soap.set_soap(soap)
        self.view.save.setVisible(bool(soap["editable"]))
        self.view.approve.setVisible(bool(soap["editable"]))
        self._originals = {path: editor.toPlainText()
                           for path, editor in self.view.soap.editors.items()}
        self._originals["subjective.source_segments"] = self._source_ids()
        for editor in self.view.soap.editors.values():
            editor.textChanged.connect(self._update_actions)
        self._update_actions()

    def _source_ids(self) -> list[int]:
        return [source["segment_id"] for source in self.view.soap.sources["subjective"]]

    def _edits(self) -> list[dict[str, Any]]:
        edits = []
        for path, editor in self.view.soap.editors.items():
            text = editor.toPlainText()
            if text != self._originals[path]:
                edits.append({"path": path, "new_value": text})
        ids = self._source_ids()
        if ids != self._originals["subjective.source_segments"]:
            edits.append({"path": "subjective.source_segments", "new_value": ids})
        return edits

    def _update_actions(self) -> None:
        editable = self._data["soap"]["editable"]
        variant = "dirty" if editable and self._edits() else "clean"
        if self.view.save.property("variant") != variant:
            set_variant(self.view.save, variant)
        self.view.save.setEnabled(editable and not self._busy)
        self.view.approve.setEnabled(editable and not self._busy)
        self.view.delete.setEnabled(not self._busy)

    def _confirm(self, title: str, message: str, destructive: bool = False) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message.format(number=self._data["soap"]["number"]))
        dialog.setIcon(QMessageBox.Icon.Warning if destructive else QMessageBox.Icon.Question)
        role = QMessageBox.ButtonRole
        if destructive:
            accept = dialog.addButton(S.SOURCE_REMOVE, role.DestructiveRole)
            accept.setObjectName("DeleteText")
        else:
            accept = dialog.addButton(title, role.AcceptRole)
        cancel = dialog.addButton(S.CANCEL, role.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        return dialog.clickedButton() is accept

    def _request(self, fn, *args, success, failure=None) -> None:
        generation = self._generation
        self._busy = True
        self._update_actions()

        def complete(callback, result):
            if not self._active or generation != self._generation:
                return
            self._busy = False
            callback(result)
            if self._active and generation == self._generation:
                self._update_actions()

        self.call(fn, *args, on_success=partial(complete, success),
                  on_error=partial(complete, failure or self._action_error))

    def _action_error(self, error: BaseException) -> None:
        self._toast(str(error) or S.ERROR_GENERIC)

    def _save(self) -> None:
        edits = self._edits()
        if self._busy:
            return
        if not edits:
            self._toast(S.SESSION_NO_EDITS)
            return

        def saved(_result):
            self._originals.update((edit["path"], edit["new_value"]) for edit in edits)
            self._toast(S.SESSION_SAVED)

        self._request(self.facade.save_soap, self.session_id, edits,
                      self.review_started_at, success=saved)

    def _approve(self) -> None:
        if self._busy or not self._confirm(S.SESSION_APPROVE, S.SESSION_CONFIRM_APPROVE):
            return
        # Freeze the submitted note through approval and the authoritative reread.
        self.view.soap.setEnabled(False)

        def rejected(error):
            self.view.soap.setEnabled(True)
            self._action_error(error)

        def approved(_result):
            self._request(self.facade.get_soap, self.session_id, success=self._render_soap,
                          failure=self._refresh_failed)

        self._request(self.facade.approve_soap, self.session_id, self._edits(),
                      self.review_started_at, success=approved, failure=rejected)

    def _refresh_failed(self, error: BaseException) -> None:
        self.view.set_state("error", S.SESSION_REOPEN_APPROVED)
        self._action_error(error)

    def _delete(self) -> None:
        if self._busy or not self._confirm(S.SESSION_DELETE, S.SESSION_CONFIRM_DELETE, True):
            return

        def deleted(_result):
            self._toast(S.SESSION_DELETED)
            self.router.back()

        self._request(self.facade.delete_session, self.session_id, success=deleted)

    def _audio_error(self, error: QMediaPlayer.Error, message: str) -> None:
        """Disable waveform navigation if decoding the selected file fails."""
        if error == QMediaPlayer.Error.NoError or not self._active:
            return
        self._audio_available = False
        self.view.wave.setEnabled(False)
        self.view.wave.set_peaks([])
        self.view.wave.set_position(0.0)
        self.view.audio_status.setText(S.SESSION_AUDIO_ERROR)
        self.view.audio_status.show()

    def _duration_changed(self, milliseconds: int) -> None:
        """Prefer the actual audio duration once the decoder discovers it."""
        if milliseconds > 0:
            self._duration = milliseconds / 1000.0

    def _position_changed(self, seconds: float) -> None:
        """Update progress and select the active half-open start/end interval."""
        self.view.wave.set_position(seconds / self._duration if self._duration else 0.0)
        segment = next((s for s in self._segments
                        if s["start"] <= seconds < s["end"]), None)
        identifier = segment["segment_id"] if segment else None
        if identifier == self._selected_id:
            return
        self._selected_id = identifier
        if identifier is None:
            self.view.transcript.clear_selection()
        else:
            self.view.transcript.select_segment(identifier)

    def _seek_fraction(self, fraction: float) -> None:
        """Translate normalized waveform navigation to playback seconds."""
        if self._audio_available:
            self.view.audio.seek(fraction * self._duration)

    def _source_clicked(self, segment_id: int) -> None:
        """Use transcript start time, never the source's display timestamp."""
        segment = next((s for s in self._segments if s["segment_id"] == segment_id), None)
        if segment is None:
            self._toast(S.SESSION_SOURCE_MISSING)
            return
        self._selected_id = segment_id
        self.view.transcript.select_segment(segment_id)
        self.view.audio.seek(float(segment["start"]))

    def _soon(self, checked: bool = False) -> None:
        """Present the K3/K4 placeholder without persisting or deleting data."""
        self._toast(S.SESSION_SOON)

    def _toast(self, message: str) -> None:
        """Use the application's toast, with a fallback for embedded screens."""
        toast = getattr(self.window(), "toast", None)
        if toast is None:
            if self._fallback_toast is None:
                self._fallback_toast = Toast(self.window())
            toast = self._fallback_toast
        toast.show_message(message)

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop playback and invalidate pending requests when navigating away."""
        self._active = False
        self._generation += 1
        self.view.audio.player.pause()
        super().hideEvent(event)
