"""Session screen layout and loading/empty/error presentation."""
from __future__ import annotations

from PySide6.QtCore import Property, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QSplitter,
    QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)
from src.app.ui import metrics as M, strings as S
from src.app.ui.widgets.action_icon import ActionIcon
from src.app.ui.widgets.audio_player import AudioPlayer
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import outline_button, primary_button
from src.app.ui.widgets.card import Card
from src.app.ui.widgets.skeleton import Skeleton
from src.app.ui.widgets.transcript_view import TranscriptView
from src.app.ui.widgets.waveform_widget import WaveformWidget
from .soap_panel import SoapPanel


class _BackArrowButton(QToolButton):
    """Icon-only back control matching the medical-card header screenshot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._arrow_color = QColor(Qt.GlobalColor.darkGray)
        self.setObjectName("SessionBack")
        self.setFixedSize(M.SESSION_BACK_SIZE, M.SESSION_BACK_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(S.SESSION_BACK)
        self.setAccessibleName(S.SESSION_BACK)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _get_arrow_color(self) -> QColor:
        return self._arrow_color

    def _set_arrow_color(self, color: QColor) -> None:
        self._arrow_color = color
        self.update()

    arrowColor = Property(QColor, _get_arrow_color, _set_arrow_color)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._arrow_color, M.SESSION_BACK_STROKE,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        center = self.rect().center()
        tip = QPointF(center.x() - 9.5, center.y())
        painter.drawLine(tip, QPointF(center.x() + 9.5, center.y()))
        painter.drawLine(tip, QPointF(center.x() - 2.5, center.y() - 7))
        painter.drawLine(tip, QPointF(center.x() - 2.5, center.y() + 7))
        painter.end()


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
        root = QVBoxLayout(self)
        root.setContentsMargins(*(M.SESSION_MARGIN,) * 4)
        root.setSpacing(M.SPACING)
        self.back = _BackArrowButton(self)
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
        self.delete = ActionIcon("trash", S.SESSION_DELETE)
        self.delete.setProperty("danger", "true")
        self.export = outline_button(S.SESSION_EXPORT)
        self.top_actions = QWidget()
        top_actions = QHBoxLayout(self.top_actions)
        top_actions.setContentsMargins(0, 0, 0, 0)
        top_actions.setSpacing(M.SPACING)
        top_actions.addWidget(self.delete)
        top_actions.addWidget(self.export)
        top = QHBoxLayout()
        top.setSpacing(M.SPACING)
        top.addWidget(self.back, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.crumb, 1)
        top.addWidget(self.top_actions, 0, Qt.AlignmentFlag.AlignVCenter)
        header = QHBoxLayout()
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
        left = QWidget()
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
        right = QWidget()
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
        self.pages.addWidget(self.columns)

        # Footer: same order and styles as the medical card (outline, then primary).
        self.save = outline_button(S.SESSION_SAVE)
        self.approve = primary_button(S.SESSION_APPROVE)
        self.action_bar = QWidget()
        actions = QHBoxLayout(self.action_bar)
        actions.setContentsMargins(0, M.SPACING_SMALL, 0, 0)
        actions.setSpacing(M.SPACING)
        actions.addStretch(1)
        actions.addWidget(self.save)
        actions.addWidget(self.approve)
        root.addWidget(self.action_bar)
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
            self.pages.setCurrentWidget(self.columns)
        else:
            self.message.setText(text)
            self.pages.setCurrentWidget(self.message)
