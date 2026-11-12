"""Local audio transport with explicit unavailable-source state."""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSlider, QWidget,
)

from app.ui import metrics as M, strings as S


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
        self.play_button = QPushButton(S.AUDIO_PLAY, self)
        self.play_button.setObjectName("AudioPlay")
        self.time_label = QLabel(self)
        self.time_label.setObjectName("AudioTime")
        self.speed = QComboBox(self)
        self.speed.setObjectName("AudioSpeed")
        self.speed.setAccessibleName(S.AUDIO_SPEED)
        for rate, label in S.AUDIO_RATES:
            self.speed.addItem(label, rate)
        self.volume = QSlider(Qt.Orientation.Horizontal, self)
        self.volume.setObjectName("AudioVolume")
        self.volume.setAccessibleName(S.AUDIO_VOLUME)
        self.volume.setRange(0, M.AUDIO_VOLUME_MAX)
        self.volume.setValue(M.AUDIO_VOLUME_INITIAL)
        self.volume.setMaximumWidth(M.AUDIO_VOLUME_WIDTH)
        self.mute_button = QPushButton(S.AUDIO_MUTE, self)
        self.mute_button.setObjectName("AudioMute")
        self.mute_button.setCheckable(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*M.AUDIO_MARGINS)
        layout.setSpacing(M.SPACING)
        layout.addWidget(self.play_button)
        layout.addWidget(self.time_label)
        layout.addStretch()
        layout.addWidget(self.speed)
        layout.addWidget(self.volume)
        layout.addWidget(self.mute_button)
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
        self.play_button.setText(S.AUDIO_PAUSE if playing else S.AUDIO_PLAY)

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
        self.mute_button.setText(S.AUDIO_UNMUTE if muted else S.AUDIO_MUTE)

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
