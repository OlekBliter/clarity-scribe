"""Session screen layout and loading/empty/error presentation."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QStackedWidget, QVBoxLayout, QWidget,
)
from src.app.ui import metrics as M, strings as S
from src.app.ui.widgets.audio_player import AudioPlayer
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.skeleton import Skeleton
from src.app.ui.widgets.transcript_view import TranscriptView
from src.app.ui.widgets.waveform_widget import WaveformWidget
from .soap_panel import SoapPanel


class SessionView(QWidget):
    """Compose the scrollable SOAP column and independently scrolling transcript."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the session header, state pages, columns, and action buttons."""
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(*(M.SESSION_MARGIN,) * 4)
        root.setSpacing(M.SPACING)
        self.crumb = Breadcrumb()
        self.crumb.setWordWrap(True)
        self.crumb.setTextFormat(Qt.TextFormat.PlainText)
        self.title = QLabel()
        self.title.setObjectName("ScreenTitle")
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.badge = Badge()
        header = QHBoxLayout()
        header.addWidget(self.title, 1)
        header.addWidget(self.badge)
        root.addWidget(self.crumb)
        root.addLayout(header)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.loading = QWidget()
        loading_layout = QVBoxLayout(self.loading)
        loading_layout.addWidget(QLabel(S.SESSION_LOADING))
        for _ in range(M.SESSION_SKELETON_COUNT):
            loading_layout.addWidget(Skeleton(width=M.SESSION_SKELETON_WIDTH,
                                              height=M.SESSION_SKELETON_HEIGHT), 1)
        self.pages.addWidget(self.loading)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.pages.addWidget(self.message)
        self.columns = QSplitter(Qt.Orientation.Horizontal)
        self.columns.setChildrenCollapsible(False)
        self.soap = SoapPanel()
        self.columns.addWidget(self.soap)
        right = QWidget()
        right.setMinimumWidth(M.SESSION_COLUMN_MIN_WIDTH)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(M.SPACING)
        self.audio = AudioPlayer()
        self.audio.setFixedHeight(M.SESSION_PLAYER_HEIGHT)
        self.wave = WaveformWidget()
        self.wave.setFixedHeight(M.SESSION_WAVE_HEIGHT)
        self.audio_status = QLabel()
        self.audio_status.setWordWrap(True)
        self.audio_status.setTextFormat(Qt.TextFormat.PlainText)
        self.transcript_status = QLabel()
        self.transcript_status.setWordWrap(True)
        self.transcript_status.setTextFormat(Qt.TextFormat.PlainText)
        self.transcript = TranscriptView()
        self.transcript.setMinimumHeight(M.SESSION_TRANSCRIPT_MIN_HEIGHT)
        for widget in (self.audio, self.wave, self.audio_status, self.transcript_status):
            right_layout.addWidget(widget)
        right_layout.addWidget(self.transcript, 1)
        self.columns.addWidget(right)
        self.columns.setStretchFactor(0, 1)
        self.columns.setStretchFactor(1, 1)
        self.pages.addWidget(self.columns)
        self.action_bar = QWidget()
        actions = QGridLayout(self.action_bar)
        actions.setContentsMargins(0, M.SPACING_SMALL, 0, 0)
        actions.setSpacing(M.SPACING)
        actions.setColumnStretch(0, 1)
        actions.setColumnStretch(1, 1)
        self.save = QPushButton(S.SESSION_SAVE)
        self.approve = QPushButton(S.SESSION_APPROVE)
        self.delete = QPushButton(S.SESSION_DELETE)
        self.export = QPushButton(S.SESSION_EXPORT)
        for index, (button, variant) in enumerate(zip(
            self.buttons, ("primary", "outline", "danger", "secondary")
        )):
            button.setObjectName("SessionAction")
            button.setProperty("variant", variant)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            actions.addWidget(button, index // 2, index % 2)
        root.addWidget(self.action_bar)
        self.set_state("loading")

    @property
    def buttons(self) -> tuple[QPushButton, ...]:
        """Return the four actions in display order."""
        return self.save, self.approve, self.delete, self.export

    def set_state(self, state: str, text: str = "") -> None:
        """Show loading, content, empty, or error without compressing content."""
        self.setProperty("state", state)
        self.action_bar.setVisible(state == "ready")
        if state == "loading":
            self.pages.setCurrentWidget(self.loading)
        elif state == "ready":
            self.pages.setCurrentWidget(self.columns)
        else:
            self.message.setText(text)
            self.pages.setCurrentWidget(self.message)
