"""Local audio transport with explicit unavailable-source state."""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSignalBlocker, QSize, Qt, QUrl, Signal
from PySide6.QtGui import (
    QFontDatabase, QPainter, QPainterPath, QPen, QResizeEvent,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSlider, QWidget,
)

from src.app.ui import metrics as M, strings as S


class _GlyphButton(QPushButton):
    """Button whose vector glyph is tinted by the QSS ``color`` property.

    Glyphs: ``play``, ``pause``, ``volume``, ``muted``. Background, radius and
    states come from theme.qss; only the icon is painted here.
    """

    def __init__(self, glyph: str, parent: QWidget | None = None) -> None:
        """Create a focusable, pointer-cursor button showing ``glyph``."""
        super().__init__(parent)
        self._glyph = glyph
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_glyph(self, glyph: str) -> None:
        """Switch the painted glyph."""
        if glyph != self._glyph:
            self._glyph = glyph
            self.update()

    def sizeHint(self) -> QSize:
        """The glyph button has a fixed footprint; QSS padding must not widen it."""
        return self.minimumSize()

    def minimumSizeHint(self) -> QSize:
        """Match the fixed size so layouts never report more than is available."""
        return self.minimumSize()

    def paintEvent(self, event) -> None:
        """Draw the QSS background, then the glyph on a fixed design grid."""
        super().paintEvent(event)
        grid = M.AUDIO_GLYPH_GRID
        scale = min(self.width(), self.height()) / grid
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate((self.width() - grid * scale) / 2, (self.height() - grid * scale) / 2)
        painter.scale(scale, scale)
        color = self.palette().buttonText().color()
        pen = QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(color)
        if self._glyph == "play":
            path = QPainterPath()
            path.moveTo(15, 11)
            path.lineTo(15, 29)
            path.lineTo(29, 20)
            path.closeSubpath()
            painter.drawPath(path)
        elif self._glyph == "pause":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(13, 11, 5, 18), 1.5, 1.5)
            painter.drawRoundedRect(QRectF(22, 11, 5, 18), 1.5, 1.5)
        else:
            body = QPainterPath()
            body.moveTo(8, 16)
            body.lineTo(14, 16)
            body.lineTo(20, 10)
            body.lineTo(20, 30)
            body.lineTo(14, 24)
            body.lineTo(8, 24)
            body.closeSubpath()
            painter.drawPath(body)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if self._glyph == "muted":
                painter.drawLine(QPointF(25, 15), QPointF(33, 25))
                painter.drawLine(QPointF(33, 15), QPointF(25, 25))
            else:
                painter.drawArc(QRectF(17, 14, 12, 12), -50 * 16, 100 * 16)
                painter.drawArc(QRectF(14, 9, 22, 22), -50 * 16, 100 * 16)
        painter.end()


class _SpeedChip(QComboBox):
    """Playback-rate combo styled as a pill, with a painted chevron.

    The icon set has no arrow asset, so the chevron is drawn in the QSS text color.
    """

    def paintEvent(self, event) -> None:
        """Draw the QSS pill, then a small chevron at the right edge."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.palette().buttonText().color(), 1.6, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x = self.width() - M.AUDIO_CHEVRON_INSET
        y = self.height() / 2.0
        half = M.AUDIO_CHEVRON_HALF
        painter.drawPolyline([QPointF(x - half, y - half / 2), QPointF(x, y + half / 2),
                              QPointF(x + half, y - half / 2)])
        painter.end()


class AudioPlayer(QFrame):
    """Playback controls for a local recording.

    Signals:
        position_changed(float): Current playback time in seconds, including
            zero when the source is cleared or replaced.
    """

    position_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the media engine and connect controls to playback state."""
        super().__init__(parent)
        self.setObjectName("AudioPlayer")
        self._has_source = False
        self._pending_seek: int | None = None
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.play_button = _GlyphButton("play", self)
        self.play_button.setObjectName("AudioPlay")
        self.play_button.setFixedSize(M.AUDIO_PLAY_SIZE, M.AUDIO_PLAY_SIZE)
        self.time_label = QLabel(self)
        self.time_label.setObjectName("AudioTime")
        # Fixed-pitch digits keep the clock from jittering while it ticks.
        self.time_label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.time_label.setTextFormat(Qt.TextFormat.PlainText)
        self.speed = _SpeedChip(self)
        self.speed.setObjectName("AudioSpeed")
        self.speed.setAccessibleName(S.AUDIO_SPEED)
        self.speed.setToolTip(S.AUDIO_SPEED)
        self.speed.setFixedSize(M.AUDIO_CHIP_WIDTH, M.AUDIO_CHIP_HEIGHT)
        for rate, label in S.AUDIO_RATES:
            self.speed.addItem(label, rate)
        self.volume = QSlider(Qt.Orientation.Horizontal, self)
        self.volume.setObjectName("AudioVolume")
        self.volume.setAccessibleName(S.AUDIO_VOLUME)
        self.volume.setRange(0, M.AUDIO_VOLUME_MAX)
        self.volume.setValue(M.AUDIO_VOLUME_INITIAL)
        self.volume.setFixedWidth(M.AUDIO_VOLUME_WIDTH)
        self.mute_button = _GlyphButton("volume", self)
        self.mute_button.setObjectName("AudioMute")
        self.mute_button.setCheckable(True)
        self.mute_button.setFixedSize(M.AUDIO_ICON_BUTTON_SIZE, M.AUDIO_ICON_BUTTON_SIZE)
        self.mute_button.setToolTip(S.AUDIO_MUTE)
        self.mute_button.setAccessibleName(S.AUDIO_MUTE)
        self.play_button.setToolTip(S.AUDIO_PLAY)
        self.play_button.setAccessibleName(S.AUDIO_PLAY)
        # One fixed-height row, every control centred on the same axis.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*M.AUDIO_MARGINS)
        layout.setSpacing(M.SPACING)
        center = Qt.AlignmentFlag.AlignVCenter
        layout.addWidget(self.play_button, 0, center)
        layout.addWidget(self.time_label, 0, center)
        layout.addStretch(1)
        layout.addWidget(self.speed, 0, center)
        sound = QHBoxLayout()  # mute + volume read as one control, so they sit closer
        sound.setSpacing(M.SPACING_SMALL)
        sound.addWidget(self.mute_button, 0, center)
        sound.addWidget(self.volume, 0, center)
        layout.addLayout(sound)
        self.play_button.clicked.connect(self._toggle_play)
        self.speed.currentIndexChanged.connect(self._set_rate)
        self.volume.valueChanged.connect(self._set_volume)
        self.mute_button.toggled.connect(self.audio_output.setMuted)
        self.audio_output.mutedChanged.connect(self._sync_mute)
        self.audio_output.volumeChanged.connect(self._sync_volume)
        self.player.playbackStateChanged.connect(self._sync_play)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.seekableChanged.connect(self._on_seekable)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(self._on_error)
        self._set_volume(self.volume.value())
        self.set_source(None)

    def set_source(self, path: str | Path | None) -> None:
        """Load a local WAV, or clear and disable all controls.

        Args:
            path: Local recording. None, missing files, directories, and
                non-WAV paths select the disabled state.
        """
        self._has_source = False
        self._pending_seek = None
        self.player.stop()
        self.player.setSource(QUrl())
        self.setEnabled(False)
        self._update_time(0, 0)
        self._sync_play(QMediaPlayer.PlaybackState.StoppedState)
        self.position_changed.emit(0.0)
        if path is None:
            return
        source = Path(path).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != ".wav":
            return
        self._has_source = True
        self.setEnabled(True)
        self.player.setSource(QUrl.fromLocalFile(str(source)))
        self._set_rate(self.speed.currentIndex())

    def seek(self, seconds: float) -> None:
        """Seek in seconds, deferring the request until the source is seekable.

        Args:
            seconds: Finite target time; negative values clamp to zero and
                positions past the known duration clamp to the end.
        """
        if not self._has_source or not math.isfinite(seconds):
            return
        self._pending_seek = int(max(0.0, seconds) * 1000)
        self._on_seekable(self.player.isSeekable())

    def _on_seekable(self, seekable: bool) -> None:
        """Apply a pending seek after the backend exposes seeking support."""
        if (not seekable or self._pending_seek is None
                or self.player.mediaStatus() in (
                    QMediaPlayer.MediaStatus.NoMedia,
                    QMediaPlayer.MediaStatus.LoadingMedia,
                )):
            return
        position = self._pending_seek
        if self.player.duration() > 0:
            position = min(position, self.player.duration())
        self._pending_seek = None
        self.player.setPosition(position)

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        """Retry deferred seeking once asynchronous loading completes."""
        self._on_seekable(self.player.isSeekable())

    def _toggle_play(self, checked: bool = False) -> None:
        """Toggle playback; displayed text is updated by the backend signal."""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _sync_play(self, state: QMediaPlayer.PlaybackState) -> None:
        """Update the play button from the actual playback state."""
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        label = S.AUDIO_PAUSE if playing else S.AUDIO_PLAY
        self.play_button.set_glyph("pause" if playing else "play")
        self.play_button.setToolTip(label)
        self.play_button.setAccessibleName(label)

    def _set_rate(self, index: int) -> None:
        """Apply the selected playback rate to the media engine."""
        self.player.setPlaybackRate(float(self.speed.itemData(index)))

    def _set_volume(self, value: int) -> None:
        """Convert the slider range to QAudioOutput's [0, 1] volume range."""
        self.audio_output.setVolume(value / M.AUDIO_VOLUME_MAX)

    def _sync_volume(self, volume: float) -> None:
        """Reflect external output-volume changes without signal feedback."""
        with QSignalBlocker(self.volume):
            self.volume.setValue(round(volume * M.AUDIO_VOLUME_MAX))

    def _sync_mute(self, muted: bool) -> None:
        """Reflect mute state without changing the saved volume level."""
        with QSignalBlocker(self.mute_button):
            self.mute_button.setChecked(muted)
        label = S.AUDIO_UNMUTE if muted else S.AUDIO_MUTE
        self.mute_button.set_glyph("muted" if muted else "volume")
        self.mute_button.setToolTip(label)
        self.mute_button.setAccessibleName(label)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Drop the volume slider in narrow columns instead of clipping controls."""
        super().resizeEvent(event)
        self.volume.setVisible(event.size().width() >= M.AUDIO_COMPACT_WIDTH)

    def _on_position(self, position_ms: int) -> None:
        """Refresh the clock and publish the playback position in seconds."""
        if self._has_source:
            self._update_time(position_ms, self.player.duration())
            self.position_changed.emit(position_ms / 1000.0)

    def _on_duration(self, duration_ms: int) -> None:
        """Refresh total duration after asynchronous media loading."""
        if self._has_source:
            self._update_time(self.player.position(), duration_ms)

    def _update_time(self, position_ms: int, duration_ms: int) -> None:
        """Format the current and total times without wrapping at one hour."""
        current = self._format_time(position_ms)
        total = self._format_time(duration_ms)
        self.time_label.setText(S.AUDIO_TIME.format(current=current, total=total))

    @staticmethod
    def _format_time(milliseconds: int) -> str:
        """Return nonnegative elapsed time as MM:SS."""
        minutes, seconds = divmod(max(0, milliseconds) // 1000, 60)
        return S.AUDIO_TIMESTAMP.format(minutes=minutes, seconds=seconds)

    def _on_error(self, error: QMediaPlayer.Error, message: str) -> None:
        """Clear unusable media and return the transport to its disabled state."""
        if error != QMediaPlayer.Error.NoError:
            self.set_source(None)
