"""Searchable transcript with segment and timestamp navigation."""
from __future__ import annotations

from typing import Literal, TypedDict

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QLineEdit, QListWidget,
    QListWidgetItem, QVBoxLayout, QWidget,
)

from app.ui import metrics as M, strings as S


class Segment(TypedDict):
    """Typed dictionary describing one input transcript segment.

    Attributes:
        segment_id: Unique segment identifier.
        speaker: Speaker role.
        time: Display timestamp.
        start: Start time in seconds.
        text: Plain transcript text.
    """

    segment_id: int
    speaker: Literal["DOCTOR", "PATIENT"]
    time: str
    start: float
    text: str


class TranscriptView(QWidget):
    """Filter transcript text and navigate to individual segments.

    Signals:
        segment_clicked(float): Start time in seconds for a user-activated row.
    """

    segment_clicked = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the search field, transcript list, and scroll animation."""
        super().__init__(parent)
        self.setObjectName("TranscriptView")
        self.search = QLineEdit(self)
        self.search.setObjectName("TranscriptSearch")
        self.search.setPlaceholderText(S.TRANSCRIPT_SEARCH)
        self.search.setClearButtonEnabled(True)
        self.transcript = QListWidget(self)
        self.transcript.setObjectName("Transcript")
        self.transcript.setWordWrap(True)
        self.transcript.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*M.TRANSCRIPT_MARGINS)
        layout.setSpacing(M.SPACING)
        layout.addWidget(self.search)
        layout.addWidget(self.transcript)
        self._items: dict[int, QListWidgetItem] = {}
        self._scroll = QPropertyAnimation(self.transcript.verticalScrollBar(), b"value", self)
        self._scroll.setDuration(M.TRANSCRIPT_SCROLL_MS)
        self._scroll.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.search.textChanged.connect(self._filter)
        self.transcript.itemClicked.connect(self._activate)
        self.transcript.itemActivated.connect(self._activate)

    def set_segments(self, segments: list[Segment]) -> None:
        """Replace transcript rows while preserving the current search query.

        Args:
            segments: Dictionaries with segment_id, speaker, time, start, text.

        Raises:
            ValueError: Segment identifiers are not unique.
        """
        if len({s["segment_id"] for s in segments}) != len(segments):
            raise ValueError("segment_id must be unique")
        self._scroll.stop()
        self._items.clear()
        self.transcript.clear()
        for segment in segments:
            label = S.TRANSCRIPT_ROW.format(
                time=segment["time"], speaker=S.TRANSCRIPT_SPEAKERS[segment["speaker"]],
                text=segment["text"],
            )
            item = QListWidgetItem(label, self.transcript)
            item.setData(Qt.ItemDataRole.UserRole, float(segment["start"]))
            self._items[segment["segment_id"]] = item
        self._filter(self.search.text())

    def select_segment(self, segment_id: int) -> None:
        """Select and smoothly center a row without emitting segment_clicked.

        Args:
            segment_id: Target identifier; unknown identifiers are ignored.
                A filter hiding the target is cleared before navigation.
        """
        item = self._items.get(segment_id)
        if item is None:
            return
        self._scroll.stop()
        if item.isHidden():
            self.search.clear()
        bar = self.transcript.verticalScrollBar()
        previous = bar.value()
        self.transcript.setCurrentItem(item)
        self.transcript.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        target = bar.value()
        bar.setValue(previous)
        self._scroll.setStartValue(previous)
        self._scroll.setEndValue(target)
        self._scroll.start()

    def _filter(self, query: str) -> None:
        """Filter displayed rows using Unicode-aware case-insensitive matching."""
        self._scroll.stop()
        needle = query.strip().casefold()
        for item in self._items.values():
            item.setHidden(needle not in item.text().casefold())

    def _activate(self, item: QListWidgetItem) -> None:
        """Emit the selected row's start time for mouse or keyboard activation."""
        self.segment_clicked.emit(float(item.data(Qt.ItemDataRole.UserRole)))
