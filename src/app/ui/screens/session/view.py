"""Session screen layout and loading/empty/error presentation."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractButton, QBoxLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QSplitter,
    QStackedWidget, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)
from src.app.ui import metrics as M, strings as S
from src.app.ui.widgets.action_icon import ActionIcon
from src.app.ui.widgets.audio_player import AudioPlayer
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import outline_button, primary_button
from src.app.ui.widgets.card import Card
from src.app.ui.widgets.row_menu import RowMenuButton
from src.app.ui.widgets.skeleton import Skeleton
from src.app.ui.widgets.transcript_view import TranscriptView
from src.app.ui.widgets.waveform_widget import WaveformWidget
from .soap_panel import SoapPanel


def _heading(text: str) -> QLabel:
    """Column heading in the same style as the medical-card columns."""
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _muted(label: QLabel) -> QLabel:
    """Style a status line as secondary text."""
    label.setObjectName("Muted")
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class SessionView(QWidget):
    """Compose the scrollable SOAP column and independently scrolling transcript.

    Signals:
        back_requested(): User asked to navigate back through the Router.
    """

    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the session header, state pages, columns, and action buttons."""
        super().__init__(parent)
        self.setObjectName("SessionView")
        self._compact = None
        self._split_sizes = []
        root = QVBoxLayout(self)
        root.setContentsMargins(*(M.SESSION_MARGIN,) * 4)
        root.setSpacing(M.SPACING)
        self.back = ActionIcon("back", S.SESSION_BACK, self)
        self.back.clicked.connect(lambda _checked=False: self.back_requested.emit())
        self.crumb = Breadcrumb()
        self.crumb.setWordWrap(True)
        self.crumb.setTextFormat(Qt.TextFormat.PlainText)
        self.title = QLabel()
        self.title.setObjectName("ScreenTitle")
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.badge = Badge()
        # Header actions: destructive and export live top-right, like the medical card.
        self.delete = RowMenuButton([], self)  # «⋯» із пунктом «Видалити» (дію задає екран)
        self.delete.setAccessibleName(S.SESSION_DELETE)
        self.export = outline_button(S.SESSION_EXPORT)
        self.top_actions = QWidget()
        top_actions = QHBoxLayout(self.top_actions)
        top_actions.setContentsMargins(0, 0, 0, 0)
        top_actions.setSpacing(M.SPACING)
        top_actions.addWidget(self.export)
        top_actions.addWidget(self.delete)  # «⋯» крайня справа
        top = self._top = QGridLayout()
        top.setSpacing(M.SPACING)
        top.addWidget(self.back, 0, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.crumb, 0, 1)
        top.setColumnStretch(1, 1)
        top.addWidget(self.top_actions, 0, 2, Qt.AlignmentFlag.AlignRight)
        header = self._header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        header.setSpacing(M.SPACING)
        header.addWidget(self.title, 1)
        header.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(top)
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
        self.message.setObjectName("Subtitle")
        self.message.setWordWrap(True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.pages.addWidget(self.message)
        self.columns = QSplitter(Qt.Orientation.Horizontal)
        self.columns.setChildrenCollapsible(False)
        self.columns.setHandleWidth(M.SPACING)

        # Left column: heading + "copy whole note" + scrollable S/O/A/P cards.
        left = self._left = QWidget()
        left.setMinimumWidth(M.SESSION_COLUMN_MIN_WIDTH)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(M.SPACING)
        self.soap = SoapPanel()
        soap_heading = _heading(S.SOAP_TITLE)
        soap_heading.setWordWrap(False)
        left_layout.addWidget(soap_heading)
        left_layout.addWidget(self.soap, 1)
        self.columns.addWidget(left)

        # Right column: one card holding waveform + transport, then the transcript.
        right = self._right = QWidget()
        right.setMinimumWidth(M.SESSION_COLUMN_MIN_WIDTH)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(M.SPACING)
        self.audio = AudioPlayer()
        self.audio.setFixedHeight(M.SESSION_PLAYER_HEIGHT)
        self.wave = WaveformWidget()
        self.wave.setFixedHeight(M.SESSION_WAVE_HEIGHT)
        self.player_card = Card()
        card_layout = QVBoxLayout(self.player_card)
        card_layout.setContentsMargins(*(M.CARD_PADDING,) * 4)
        card_layout.setSpacing(M.SPACING)
        divider = QFrame()
        divider.setObjectName("AudioDivider")
        divider.setFixedHeight(1)
        card_layout.addWidget(self.wave)
        card_layout.addWidget(divider)
        card_layout.addWidget(self.audio)
        self.audio_status = _muted(QLabel())
        self.transcript_status = _muted(QLabel())
        self.transcript = TranscriptView()
        self.transcript.setMinimumHeight(M.SESSION_TRANSCRIPT_MIN_HEIGHT)
        right_layout.addWidget(_heading(S.SESSION_MEDIA_TITLE))
        for widget in (self.player_card, self.audio_status, self.transcript_status):
            right_layout.addWidget(widget)
        right_layout.addWidget(self.transcript, 1)
        self.columns.addWidget(right)
        self.columns.setStretchFactor(0, 1)
        self.columns.setStretchFactor(1, 1)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("SessionTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setDrawBase(False)
        self.pages.addWidget(self.columns)
        self.pages.addWidget(self.tabs)
        self.soap.source_clicked.connect(self._show_source)

        # Footer: same order and styles as the medical card (outline, then primary).
        self.save = outline_button(S.SESSION_SAVE)
        self.save.setObjectName("SessionSave")
        self.approve = primary_button(S.SESSION_APPROVE)
        self.action_bar = QWidget()
        actions = self._actions = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.action_bar)
        actions.setContentsMargins(0, M.SPACING_SMALL, 0, 0)
        actions.setSpacing(M.SPACING)
        actions.addStretch(1)
        actions.addWidget(self.save)
        actions.addWidget(self.approve)
        root.addWidget(self.action_bar)
        self._adapt_layout(self.width())
        self.set_state("loading")

    @property
    def buttons(self) -> tuple[QAbstractButton, ...]:
        """Return the four actions in display order."""
        return self.save, self.approve, self.delete, self.export

    def set_state(self, state: str, text: str = "") -> None:
        """Show loading, content, empty, or error without compressing content."""
        self.setProperty("state", state)
        self.action_bar.setVisible(state == "ready")
        self.top_actions.setVisible(state == "ready")
        if state == "loading":
            self.pages.setCurrentWidget(self.loading)
        elif state == "ready":
            self.pages.setCurrentWidget(self.tabs if self._compact else self.columns)
        else:
            self.message.setText(text)
            self.pages.setCurrentWidget(self.message)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._adapt_layout(event.size().width())

    def _adapt_layout(self, width: int) -> None:
        compact = width < M.SESSION_COMPACT_WIDTH
        narrow = width < M.SESSION_NARROW_WIDTH
        margin = M.SESSION_COMPACT_MARGIN if compact else M.SESSION_MARGIN
        self.layout().setContentsMargins(margin, margin, margin, margin)
        direction = (QBoxLayout.Direction.TopToBottom if narrow
                     else QBoxLayout.Direction.LeftToRight)
        self._header.setDirection(direction)
        self._actions.setDirection(direction)
        self._actions.setStretch(0, 0 if narrow else 1)
        self._top.removeWidget(self.top_actions)
        if narrow:
            self._top.addWidget(self.top_actions, 1, 0, 1, 3, Qt.AlignmentFlag.AlignRight)
        else:
            self._top.addWidget(self.top_actions, 0, 2, Qt.AlignmentFlag.AlignRight)
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            self._split_sizes = self.columns.sizes()
            self.tabs.addTab(self._left, S.SOAP_TITLE)
            self.tabs.addTab(self._right, S.SESSION_MEDIA_TITLE)
        else:
            while self.tabs.count():
                self.tabs.removeTab(0)
            self.columns.addWidget(self._left)
            self.columns.addWidget(self._right)
            self._left.show()
            self._right.show()
            if any(self._split_sizes):
                self.columns.setSizes(self._split_sizes)
        if self.property("state") == "ready":
            self.pages.setCurrentWidget(self.tabs if compact else self.columns)

    def _show_source(self, _segment_id: int) -> None:
        if self._compact:
            self.tabs.setCurrentWidget(self._right)
