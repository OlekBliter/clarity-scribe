"""Трекінг динаміки показників за підтвердженими сесіями."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from src.app.ui import metrics, strings
from src.app.ui.qt_helpers import clear_layout
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


class _MetricCard(QFrame):
    """Картка одного показника з графіком та нахилом за візит."""

    def __init__(
        self, metric: str, direction: str, values: list[float],
        sessions: list[int], slope: float | None, parent: QWidget,
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

        chart = SparklineChart(self)
        y_range = None
        if metric == "pause_ratio":
            values = [value * 100 for value in values]
            slope = slope * 100 if slope is not None else None
            unit = strings.DYNAMICS_PERCENT_UNIT
            # Біля верхньої межі частки шкала закінчується на 100%.
            if max(values, default=0) * (1 + metrics.SPARKLINE_RANGE_PADDING) > 100:
                y_range = (0.0, 100.0)
        else:
            unit = strings.DYNAMICS_SLOPE_UNITS.get(metric, "")
        chart.set_data(values, [str(number) for number in sessions],
                       x_values=sessions, y_range=y_range, unit=unit)
        layout.addWidget(chart, 1)

        if slope is None:
            slope_text = strings.DYNAMICS_NO_SLOPE
        else:
            unit = strings.DYNAMICS_SLOPE_UNITS.get(metric)
            template = strings.DYNAMICS_SLOPE_WITH_UNIT if unit else strings.DYNAMICS_SLOPE
            slope_text = template.format(value=slope, unit=unit)
        layout.addWidget(_label(slope_text, "Muted", wrap=True))


class DynamicsScreen(BaseScreen):
    """Завантажує профіль і динаміку для поточного пацієнта."""

    def __init__(self, facade, router: Router, parent: QWidget | None = None) -> None:
        super().__init__(facade, router, parent)
        self.setObjectName("DynamicsScreen")
        self._request_id = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(*(metrics.CONTENT_MARGIN,) * 4)
        layout.setSpacing(metrics.SPACING)

        top = QHBoxLayout()
        back = outline_button(strings.BACK)
        back.clicked.connect(self.router.back)
        top.addWidget(back)
        self._crumb = Breadcrumb(content)
        self._crumb.setTextFormat(Qt.TextFormat.PlainText)
        self._crumb.setWordWrap(True)
        top.addWidget(self._crumb, 1)
        export = outline_button(strings.DYNAMICS_EXPORT)
        export.clicked.connect(self._show_export_toast)
        top.addWidget(export)
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

    def on_open(self, **params: Any) -> None:
        patient_id = params["patient_id"]
        self._request_id += 1
        request_id = self._request_id

        self._title.setText(strings.DYNAMICS_TITLE)
        self._crumb.set_path([strings.NAV_PATIENTS, strings.DYNAMICS_BREADCRUMB])
        self._sessions.hide()
        self._results.hide()
        self._status.hide()
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

        self._sessions.setText(strings.DYNAMICS_SESSIONS.format(sessions=data["sessions_label"]))
        self._sessions.show()
        for index, trend in enumerate(data["trends"]):
            points = sorted(trend["values"], key=lambda point: point["session_number"])
            values = [point["value"] for point in points]
            sessions = [point["session_number"] for point in points]
            card = _MetricCard(trend["metric"], trend["direction"], values, sessions,
                               trend["slope"], self._results)
            row, column = divmod(index, metrics.DYNAMICS_COLUMNS)
            self._grid.addWidget(card, row, column)

        self._summary.setText(data["summary_text"])
        self._summary_box.setVisible(bool(data["summary_text"]))
        self._results.show()

    def _show_error(self, exc: BaseException, request_id: int) -> None:
        if not self._is_current(request_id):
            return
        self._loading.hide()
        self._status.setText(strings.DYNAMICS_ERROR)
        self._status.show()
        self._default_error(exc)

    def _show_export_toast(self) -> None:
        toast = getattr(self.window(), "toast", None)
        if toast is not None:
            toast.show_message(strings.DYNAMICS_EXPORT_SOON)
