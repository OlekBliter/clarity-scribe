"""Графік значень за сесіями з числовою шкалою та підказками."""
from __future__ import annotations

from math import ceil, floor, isfinite, log10

from PySide6.QtCore import QEasingCurve, QPointF, Property, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

from src.app.ui import metrics, strings


class SparklineChart(QWidget):
    """Лінійний графік. Колір точок і лінії задає QSS-властивість lineColor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self._labels: list[str] = []
        self._x_values: list[float] = []
        self._y_range: tuple[float, float] | None = None
        self._unit = ""
        self._line_color = QColor()
        self._grid_color = QColor()
        self._hovered = None
        self._hover_progress = 0.0
        self._bubble = QLabel(self)
        self._bubble.setObjectName("DynamicsPointBubble")
        self._bubble.setTextFormat(Qt.TextFormat.PlainText)
        self._bubble.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._opacity = QGraphicsOpacityEffect(self._bubble)
        self._bubble.setGraphicsEffect(self._opacity)
        self._bubble.hide()
        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(metrics.SPARKLINE_HOVER_MS)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_animation.valueChanged.connect(self._animate_hover)
        self._hover_animation.finished.connect(self._finish_hover)
        self.setMouseTracking(True)
        self.setMinimumHeight(metrics.SPARKLINE_MIN_HEIGHT)

    def _get_line_color(self) -> QColor:
        return self._line_color

    def _set_line_color(self, color: QColor) -> None:
        self._line_color = QColor(color)
        self.update()

    lineColor = Property(QColor, _get_line_color, _set_line_color)

    def _get_grid_color(self) -> QColor:
        return self._grid_color

    def _set_grid_color(self, color: QColor) -> None:
        self._grid_color = QColor(color)
        self.update()

    gridColor = Property(QColor, _get_grid_color, _set_grid_color)

    def set_data(
        self, values: list[float], labels: list[str], *,
        x_values: list[float] | None = None,
        y_range: tuple[float, float] | None = None, unit: str = "",
    ) -> None:
        """Задає точки. X за замовчуванням рівновіддалені.

        x_values задає числові координати сесій у строго зростаючому порядку.
        y_range фіксує шкалу; інакше вона охоплює нуль і всі значення.
        unit відображається над шкалою та в підказках.
        Невалідні дані відхиляються до зміни стану графіка.
        """
        xs = list(range(len(values))) if x_values is None else list(x_values)
        if len(values) != len(labels) or len(values) != len(xs):
            raise ValueError("values, labels and x_values must have the same length")
        if not all(isfinite(v) for v in [*values, *xs]):
            raise ValueError("Coordinates must be finite")
        if any(right <= left for left, right in zip(xs, xs[1:])):
            raise ValueError("x_values must be strictly increasing")
        if y_range is not None:
            low, high = y_range
            if not (isfinite(low) and isfinite(high) and low < high):
                raise ValueError("y_range must have finite increasing bounds")
            if any(v < low or v > high for v in values):
                raise ValueError("y_range must contain every value")
        self._values = list(values)
        self._labels = list(labels)
        self._x_values = xs
        self._y_range = y_range
        self._unit = unit
        self._hover_animation.stop()
        self._hovered = None
        self._hover_progress = 0.0
        self._bubble.hide()
        self.update()

    def _ticks(self) -> list[float]:
        if self._y_range is not None:
            low, high = self._y_range
            step = (high - low) / metrics.SPARKLINE_INTERVALS
            return [low + i * step for i in range(metrics.SPARKLINE_INTERVALS + 1)]
        low = min([0.0, *self._values])
        high = max([0.0, *self._values])
        span = high - low
        if span == 0:
            high, span = 1.0, 1.0
        margin = span * metrics.SPARKLINE_RANGE_PADDING
        low = low - margin if low < 0 else low
        high = high + margin if high > 0 else high
        raw_step = (high - low) / metrics.SPARKLINE_INTERVALS
        magnitude = 10 ** floor(log10(raw_step))
        step = next(n for n in metrics.SPARKLINE_NICE_STEPS if n >= raw_step / magnitude)
        step *= magnitude
        start, stop = floor(low / step), ceil(high / step)
        return [float(f"{i * step:.12g}") for i in range(start, stop + 1)]

    def _bounds(self) -> tuple[float, float]:
        ticks = self._ticks()
        return ticks[0], ticks[-1]

    def _geometry(self) -> tuple[QRectF, list[QPointF], list[float]]:
        ticks = list(reversed(self._ticks()))
        high, low = ticks[0], ticks[-1]
        fm = self.fontMetrics()
        padding = metrics.SPARKLINE_PADDING
        axis_width = max(fm.horizontalAdvance(f"{v:g}") for v in ticks)
        label_half = max((fm.horizontalAdvance(s) / 2 for s in self._labels), default=0)
        left = padding + axis_width + metrics.SPARKLINE_LABEL_GAP + label_half
        right = self.width() - padding - max(label_half, metrics.SPARKLINE_HOVER_RADIUS)
        top = padding + fm.height()
        bottom = self.height() - padding - fm.height() - metrics.SPARKLINE_LABEL_GAP
        rect = QRectF(left, top, max(0, right - left), max(0, bottom - top))
        if not self._values:
            return rect, [], ticks
        x_low, x_high = self._x_values[0], self._x_values[-1]
        points = []
        for x, y in zip(self._x_values, self._values):
            fraction = (x - x_low) / (x_high - x_low) if x_high != x_low else 0.5
            points.append(QPointF(rect.left() + fraction * rect.width(),
                                 rect.bottom() - (y - low) / (high - low) * rect.height()))
        return rect, points, ticks

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if not self._values:
            return
        rect, points, ticks = self._geometry()
        if rect.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        text_color = self.palette().color(QPalette.ColorRole.WindowText)
        painter.setPen(text_color)
        fm = self.fontMetrics()
        padding = metrics.SPARKLINE_PADDING
        gap = metrics.SPARKLINE_LABEL_GAP
        painter.drawText(QRectF(padding, 0, self.width() - 2 * padding, fm.height()),
                         Qt.AlignmentFlag.AlignLeft, self._unit)
        for index, tick in enumerate(ticks):
            y = rect.top() + index * rect.height() / (len(ticks) - 1)
            label_rect = QRectF(padding, y - fm.height() / 2,
                               rect.left() - padding - gap, fm.height())
            painter.setPen(text_color)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight, f"{tick:g}")
            grid_pen = QPen(self._grid_color if self._grid_color.isValid() else text_color)
            grid_pen.setWidthF(metrics.SPARKLINE_GRID_WIDTH)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        color = self._line_color if self._line_color.isValid() else self.palette().highlight().color()
        pen = QPen(color)
        pen.setWidthF(metrics.SPARKLINE_LINE_WIDTH)
        painter.setPen(pen)
        if len(points) > 1:
            painter.drawPolyline(QPolygonF(points))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for index, point in enumerate(points):
            radius = metrics.SPARKLINE_POINT_RADIUS
            if index == self._hovered:
                radius += (metrics.SPARKLINE_HOVER_RADIUS - radius) * self._hover_progress
            painter.drawEllipse(point, radius, radius)

        painter.setPen(text_color)
        last_right = float("-inf")
        for point, label in zip(points, self._labels):
            width = fm.horizontalAdvance(label)
            label_rect = QRectF(point.x() - width / 2, rect.bottom() + gap, width, fm.height())
            # При щільному наборі сесій повний номер лишається в підказці.
            if label_rect.left() >= last_right + gap:
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
                last_right = label_rect.right()

    def _animate_hover(self, progress: float) -> None:
        self._hover_progress = progress
        self._opacity.setOpacity(progress)
        self.update()

    def _finish_hover(self) -> None:
        if self._hover_progress == 0:
            self._bubble.hide()
            self._hovered = None

    def _set_hover(self, index: int | None) -> None:
        if index is None and (self._hovered is None or self._hover_animation.endValue() == 0.0):
            return
        if index == self._hovered and self._hover_animation.endValue() == 1.0:
            return
        self._hover_animation.stop()
        if index is not None:
            if index != self._hovered:
                self._hover_progress = 0.0
            self._hovered = index
            self._bubble.setText(strings.DYNAMICS_POINT_BUBBLE.format(
                session=self._labels[index], value=format(self._values[index], ".12g"),
                unit=self._unit,
            ).rstrip())
            self._bubble.adjustSize()
            self._position_bubble()
            self._bubble.show()
            self._bubble.raise_()
        self.setCursor(Qt.CursorShape.PointingHandCursor if index is not None
                       else Qt.CursorShape.ArrowCursor)
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(1.0 if index is not None else 0.0)
        self._hover_animation.start()

    def _position_bubble(self) -> None:
        if self._hovered is None:
            return
        point = self._geometry()[1][self._hovered]
        gap = metrics.SPARKLINE_BUBBLE_GAP
        x = min(max(gap, point.x() - self._bubble.width() / 2),
                self.width() - self._bubble.width() - gap)
        y = point.y() - self._bubble.height() - gap
        if y < 0:
            y = point.y() + gap
        y = min(y, self.height() - self._bubble.height())
        self._bubble.move(round(x), round(y))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._values:
            _, points, _ = self._geometry()
            index = min(range(len(points)),
                        key=lambda i: (points[i] - event.position()).manhattanLength())
            distance = (points[index] - event.position()).manhattanLength()
            self._set_hover(index if distance <= metrics.SPARKLINE_HIT_RADIUS else None)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._set_hover(None)
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._hover_animation.stop()
        self._hovered = None
        self._hover_progress = 0.0
        self._bubble.hide()
        super().hideEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._position_bubble()
        super().resizeEvent(event)
