"""QSS-colored waveform with normalized seeking."""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QLineF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

from app.ui import metrics as M


class WaveformWidget(QWidget):
    """Render symmetric peaks using colors supplied by QSS.

    Signals:
        seek_requested(float): Requested position as a fraction in [0, 1].
    """

    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize empty peaks and safe palette-based fallback colors."""
        super().__init__(parent)
        self.setObjectName("WaveformWidget")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(M.WAVE_MIN_HEIGHT)
        self._peaks: list[float] = []
        self._position = 0.0
        self._wave_color = QColor(self.palette().color(QPalette.ColorRole.Mid))
        self._progress_color = QColor(self.palette().color(QPalette.ColorRole.Highlight))
        self._background_color = QColor(self.palette().color(QPalette.ColorRole.Base))

    def _get_waveColor(self) -> QColor:
        """Return the QSS-configurable unplayed waveform color."""
        return QColor(self._wave_color)

    def _set_waveColor(self, color: QColor) -> None:
        """Apply the unplayed waveform color and schedule repainting."""
        self._wave_color = QColor(color)
        self.update()

    def _get_progressColor(self) -> QColor:
        """Return the QSS-configurable played waveform and cursor color."""
        return QColor(self._progress_color)

    def _set_progressColor(self, color: QColor) -> None:
        """Apply the played waveform color and schedule repainting."""
        self._progress_color = QColor(color)
        self.update()

    def _get_backgroundColor(self) -> QColor:
        """Return the QSS-configurable background color."""
        return QColor(self._background_color)

    def _set_backgroundColor(self, color: QColor) -> None:
        """Apply the background color and schedule repainting."""
        self._background_color = QColor(color)
        self.update()

    waveColor = Property(QColor, _get_waveColor, _set_waveColor)
    progressColor = Property(QColor, _get_progressColor, _set_progressColor)
    backgroundColor = Property(QColor, _get_backgroundColor, _set_backgroundColor)

    def set_peaks(self, peaks: list[float]) -> None:
        """Copy amplitudes, clamp to [0, 1], and replace nonfinite values by zero.

        Args:
            peaks: Normalized amplitudes; an empty list displays a flat line.
        """
        self._peaks = [self._clamp(value) for value in peaks]
        self.update()

    def set_position(self, fraction: float) -> None:
        """Set the played fraction in [0, 1] without emitting a seek request."""
        self._position = self._clamp(fraction)
        self.update()

    @staticmethod
    def _clamp(value: float) -> float:
        """Return a finite fraction in [0, 1]."""
        return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint peaks twice with clipping so progress splits them precisely."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background_color)
        width, height = float(self.width()), float(self.height())
        center = height / 2.0
        amplitude = max(0.0, center - M.WAVE_PADDING)
        # Aggregate into display columns: narrow windows retain local maxima.
        count = min(len(self._peaks), max(1, int(width / M.WAVE_BAR_SPACING)))
        lines: list[QLineF] = []
        for index in range(count):
            start = index * len(self._peaks) // count
            end = (index + 1) * len(self._peaks) // count
            peak = max(self._peaks[start:end])
            half = max(M.WAVE_LINE_WIDTH / 2.0, peak * amplitude)
            x = (index + 0.5) * width / count
            lines.append(QLineF(x, center - half, x, center + half))
        if not lines:
            lines.append(QLineF(0.0, center, width, center))
        painter.setPen(QPen(self._wave_color, M.WAVE_LINE_WIDTH))
        painter.drawLines(lines)
        painter.save()
        painter.setClipRect(QRectF(0.0, 0.0, width * self._position, height))
        painter.setPen(QPen(self._progress_color, M.WAVE_LINE_WIDTH))
        painter.drawLines(lines)
        painter.restore()
        inset = M.WAVE_CURSOR_WIDTH / 2.0
        cursor = max(inset, min(width - inset, width * self._position))
        painter.setPen(QPen(self._progress_color, M.WAVE_CURSOR_WIDTH))
        painter.drawLine(QLineF(cursor, 0.0, cursor, height))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Request a seek only for a left-button press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._request_seek(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Request seeks while dragging with the left button held."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._request_seek(event)
        else:
            super().mouseMoveEvent(event)

    def _request_seek(self, event: QMouseEvent) -> None:
        """Convert mouse coordinates to a clamped fraction and emit it."""
        self.seek_requested.emit(self._clamp(event.position().x() / max(1, self.width())))
        event.accept()
