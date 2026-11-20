"""Трекінг динаміки показників за підтвердженими сесіями."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from src.app.ui import metrics, strings
from src.app.ui.export_pdf import export_dynamics, save_screen_pdf
from src.app.ui.qt_helpers import clear_layout
from src.app.ui.widgets.action_icon import ActionIcon
from src.app.ui.router import Route, Router
from src.app.ui.screens.base import BaseScreen
from src.app.ui.widgets.badge import Badge
from src.app.ui.widgets.breadcrumb import Breadcrumb
from src.app.ui.widgets.buttons import outline_button
from src.app.ui.widgets.sparkline_chart import SparklineChart

_DIRECTION_VARIANTS = {"up": "warning", "down": "info", "stable": "neutral"}


def _label(text: str, object_name: str, *, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    return label


class _PreviewChart(SparklineChart):
    activated = Signal()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activated.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit()
        else:
            super().keyPressEvent(event)


def _plot(chart, metric, points):
    sessions = [point["session_number"] for point in points]
    values = [point["value"] for point in points]
    unit = strings.DYNAMICS_SLOPE_UNITS.get(metric, "")
    y_range = None
    if metric == "pause_ratio":
        values = [value * 100 for value in values]
        unit = strings.DYNAMICS_PERCENT_UNIT
        if max(values, default=0) * (1 + metrics.SPARKLINE_RANGE_PADDING) > 100:
            y_range = (0.0, 100.0)
    chart.set_data(values, list(map(str, sessions)), x_values=sessions, y_range=y_range, unit=unit)


class _MetricCard(QFrame):
    """Картка одного показника з графіком та нахилом за візит."""

    def __init__(
        self, metric: str, direction: str, preview: list[dict],
        history: list[dict], slope: float | None, parent: QWidget, open_history,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        layout.setSpacing(metrics.SPACING_SMALL)

        header = QHBoxLayout()
        header.addWidget(_label(
            strings.DYNAMICS_METRIC_NAMES.get(metric, metric), "CardTitle", wrap=True,
        ), 1)
        badge = Badge(strings.DYNAMICS_DIRECTIONS[direction], _DIRECTION_VARIANTS[direction], self)
        header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        chart = _PreviewChart(self)
        chart.setToolTip(strings.DYNAMICS_EXPAND)
        chart.setCursor(Qt.CursorShape.PointingHandCursor)
        chart.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        _plot(chart, metric, preview)
        layout.addWidget(chart, 1)

        if metric == "pause_ratio" and slope is not None:
            slope *= 100
        if slope is None:
            slope_text = strings.DYNAMICS_NO_SLOPE
        else:
            unit = strings.DYNAMICS_SLOPE_UNITS.get(metric)
            template = strings.DYNAMICS_SLOPE_WITH_UNIT if unit else strings.DYNAMICS_SLOPE
            slope_text = template.format(value=slope, unit=unit)
        layout.addWidget(_label(slope_text, "Muted", wrap=True))
        chart.activated.connect(lambda: open_history(chart, metric, history, direction, slope_text))


class _HistoryOverlay(QFrame):
    dismissed = Signal()

    def __init__(self, parent, metric, history, direction, slope_text):
        super().__init__(parent)
        self.setObjectName("TrendOverlay")
        self.panel = QFrame(self)
        self.panel.setObjectName("TrendHistory")
        title = strings.DYNAMICS_METRIC_NAMES.get(metric, metric)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        layout.setSpacing(metrics.SPACING)
        header = QHBoxLayout()
        header.addWidget(_label(title, "ScreenTitle", wrap=True), 1)
        header.addWidget(Badge(strings.DYNAMICS_DIRECTIONS[direction],
                               _DIRECTION_VARIANTS[direction], self.panel))
        layout.addLayout(header)

        surface = QFrame(self.panel)
        surface.setObjectName("TrendPlotCard")
        plot_layout = QVBoxLayout(surface)
        plot_layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        if history:
            span = strings.DYNAMICS_RANGE.format(first=history[0]["session_number"],
                                                 last=history[-1]["session_number"])
            plot_layout.addWidget(_label(strings.DYNAMICS_SESSIONS.format(sessions=span), "SectionTitle"))
        layout.addWidget(surface, 1)
        scroll = QScrollArea(surface)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        chart = SparklineChart()
        _plot(chart, metric, history)
        width = max((chart.fontMetrics().horizontalAdvance(str(p["session_number"]))
                     for p in history), default=0)
        chart.setMinimumWidth(len(history) * (width + metrics.SPACING) + 100)
        scroll.setWidget(chart)
        plot_layout.addWidget(scroll, 1)
        footer = QHBoxLayout()
        footer.addWidget(_label(slope_text, "Subtitle", wrap=True), 1)
        close = outline_button(strings.TREND_HISTORY_CLOSE)
        close.clicked.connect(lambda: self.dismissed.emit())
        footer.addWidget(close)
        layout.addLayout(footer)
        self.close_button = close
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.dismissed.emit)
        self.animation = QPropertyAnimation(self.panel, b"geometry", self)
        self.animation.setDuration(metrics.MEDCARD_PANEL_ANIMATION_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def reveal(self, origin):
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.close_button.setFocus()
        self.animation.setStartValue(origin)
        self.animation.setEndValue(self._target())
        self.animation.start()

    def _target(self):
        margin = metrics.MEDCARD_PANEL_INSET
        return self.rect().adjusted(margin, margin, -margin, -margin)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.animation.stop()
        self.panel.setGeometry(self._target())


class DynamicsScreen(BaseScreen):
    """Завантажує профіль і динаміку для поточного пацієнта."""

    def __init__(self, facade, router: Router, parent: QWidget | None = None) -> None:
        super().__init__(facade, router, parent)
        self.setObjectName("DynamicsScreen")
        self._overlay = None
        self._origin_chart = None
        self._request_id = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = self._page_scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        layout.setSpacing(metrics.SPACING)

        top = QHBoxLayout()
        back = ActionIcon("back", strings.BACK)
        back.clicked.connect(self.router.back)
        top.addWidget(back)
        self._crumb = Breadcrumb(content)
        self._crumb.setTextFormat(Qt.TextFormat.PlainText)
        self._crumb.setWordWrap(True)
        top.addWidget(self._crumb, 1)
        self.export = outline_button(strings.DYNAMICS_EXPORT)
        self.export.setEnabled(False)
        self.export.clicked.connect(self._export)
        top.addWidget(self.export)
        layout.addLayout(top)

        header = QHBoxLayout()
        self._title = _label(strings.DYNAMICS_TITLE, "ScreenTitle", wrap=True)
        header.addWidget(self._title, 1)
        self._sessions = Badge(variant="success", parent=content)
        self._sessions.setTextFormat(Qt.TextFormat.PlainText)
        header.addWidget(self._sessions)
        layout.addLayout(header)

        self._loading = QWidget(content)
        loading_layout = QVBoxLayout(self._loading)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.addWidget(_label(strings.DYNAMICS_LOADING, "Muted"))
        skeleton_grid = QGridLayout()
        for index in range(metrics.DYNAMICS_PLACEHOLDER_COUNT):
            block = QWidget(self._loading)
            block.setObjectName("Skeleton")
            block.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
            block.setMinimumHeight(metrics.SPARKLINE_MIN_HEIGHT)
            row, column = divmod(index, metrics.DYNAMICS_COLUMNS)
            skeleton_grid.addWidget(block, row, column)
        loading_layout.addLayout(skeleton_grid)
        layout.addWidget(self._loading)

        self._status = _label("", "Muted", wrap=True)
        layout.addWidget(self._status)

        self._results = QWidget(content)
        results = QVBoxLayout(self._results)
        results.setContentsMargins(0, 0, 0, 0)
        results.setSpacing(metrics.SPACING)
        self._grid = QGridLayout()
        self._grid.setSpacing(metrics.SPACING)
        for column in range(metrics.DYNAMICS_COLUMNS):
            self._grid.setColumnStretch(column, 1)
        results.addLayout(self._grid)

        self._summary_box = QFrame(self._results)
        self._summary_box.setObjectName("SummaryBox")
        summary_layout = QVBoxLayout(self._summary_box)
        summary_layout.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        self._summary = _label("", "Subtitle", wrap=True)
        summary_layout.addWidget(self._summary)
        results.addWidget(self._summary_box)
        layout.addWidget(self._results)
        layout.addWidget(_label(strings.DYNAMICS_NOTE, "Muted", wrap=True))
        layout.addStretch()

    def _open_history(self, chart, metric, history, direction, slope_text):
        if self._overlay is not None:
            return
        self._origin_chart = chart
        origin = QRect(chart.mapTo(self, chart.rect().topLeft()), chart.size())
        self._overlay = _HistoryOverlay(self, metric, history, direction, slope_text)
        self._overlay.dismissed.connect(self._close_history)
        self._page_scroll.setEnabled(False)
        self._overlay.reveal(origin)

    def _close_history(self, restore_focus=True):
        if self._overlay is None:
            return
        self._overlay.hide()
        self._overlay.deleteLater()
        self._overlay = None
        self._page_scroll.setEnabled(True)
        if restore_focus:
            self._origin_chart.setFocus()
        self._origin_chart = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay is not None:
            self._overlay.setGeometry(self.rect())

    def hideEvent(self, event):
        self._close_history(restore_focus=False)
        super().hideEvent(event)

    def on_open(self, **params: Any) -> None:
        self._close_history(restore_focus=False)
        patient_id = params["patient_id"]
        self._request_id += 1
        request_id = self._request_id

        self._title.setText(strings.DYNAMICS_TITLE)
        self._crumb.set_path([strings.NAV_PATIENTS, strings.DYNAMICS_BREADCRUMB])
        self._sessions.hide()
        self._results.hide()
        self._status.hide()
        self._data = None
        self.export.setEnabled(False)
        self._loading.show()
        clear_layout(self._grid)

        self.call(
            self.facade.get_patient_profile, patient_id,
            on_success=lambda profile: self._open_patient(profile, patient_id, request_id),
            on_error=lambda exc: self._show_error(exc, request_id),
        )

    def _is_current(self, request_id: int) -> bool:
        return request_id == self._request_id and self.router.current_route == Route.DYNAMICS

    def _open_patient(self, profile: dict[str, Any], patient_id: str, request_id: int) -> None:
        if not self._is_current(request_id):
            return
        name = profile["name"] or strings.NO_NAME
        self._patient_name = name
        self._title.setText(strings.DYNAMICS_PATIENT_TITLE.format(name=name))
        self._crumb.set_path([strings.NAV_PATIENTS, name, strings.DYNAMICS_BREADCRUMB])
        self.call(
            self.facade.get_dynamics, patient_id,
            on_success=lambda data: self._render(data, request_id),
            on_error=lambda exc: self._show_error(exc, request_id),
        )

    def _render(self, data: dict[str, Any], request_id: int) -> None:
        if not self._is_current(request_id):
            return
        self._loading.hide()
        if not data["available"]:
            self._status.setText(strings.DYNAMICS_EMPTY)
            self._status.show()
            return

        shown = []
        truncated = False
        for index, trend in enumerate(data["trends"]):
            points = sorted(trend["values"], key=lambda point: point["session_number"])
            preview = points[-metrics.DYNAMICS_MAX_SESSIONS:]
            truncated |= len(preview) < len(points)
            shown.extend(point["session_number"] for point in preview)
            card = _MetricCard(trend["metric"], trend["direction"], preview, points,
                               trend["slope"], self._results, self._open_history)
            row, column = divmod(index, metrics.DYNAMICS_COLUMNS)
            self._grid.addWidget(card, row, column)

        sessions = data["sessions_label"]
        if truncated:
            sessions = strings.DYNAMICS_RANGE.format(first=min(shown), last=max(shown))
            self._status.setText(strings.DYNAMICS_WINDOW_NOTE.format(count=metrics.DYNAMICS_MAX_SESSIONS))
            self._status.show()
        self._sessions.setText(strings.DYNAMICS_SESSIONS.format(sessions=sessions))
        self._sessions.show()
        self._summary.setText(data["summary_text"])
        self._summary_box.setVisible(bool(data["summary_text"]))
        self._data = dict(data, patient_name=self._patient_name)
        self.export.setEnabled(True)
        self._results.show()

    def _show_error(self, exc: BaseException, request_id: int) -> None:
        if not self._is_current(request_id):
            return
        self._loading.hide()
        self._status.setText(strings.DYNAMICS_ERROR)
        self._status.show()
        self._default_error(exc)

    def _export(self):
        if self._data:
            name = strings.PDF_TREND_NAME.format(name=self._patient_name)
            save_screen_pdf(self, self._data, name, export_dynamics)
