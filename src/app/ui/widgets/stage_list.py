"""Картка «Обробка запису»: етапи обробки та їхні стани.

Використання:
    stages = StageList()
    stages.set_states(state["stages"])   # відповідь get_processing_state
    stages.set_error(state["error"])     # текст помилки або None

Окремий запуск для перегляду:  python -m src.app.ui.widgets.stage_list
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.app.ui import metrics, strings
from src.app.ui.qt_helpers import clear_layout
from src.app.ui.widgets.badge import Badge

# стан етапу з фасаду -> (текст, variant бейджа)
_STATE_STYLE = {
    "done": (strings.STAGE_STATE_DONE, "success"),
    "running": (strings.STAGE_STATE_RUNNING, "warning"),
    "pending": (strings.STAGE_STATE_PENDING, "neutral"),
    "not_needed": (strings.STAGE_STATE_NOT_NEEDED, "neutral"),
    "error": (strings.STAGE_STATE_ERROR, "danger"),
}


class StageList(QFrame):
    def __init__(self, title: str = strings.STAGES_TITLE,
                 footer: str = strings.STAGES_FOOTER, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._keys: list[str] = []
        self._badges: dict[str, Badge] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(*(metrics.CARD_PADDING,) * 4)
        root.setSpacing(metrics.SPACING)

        heading = QLabel(title)
        heading.setObjectName("CardTitle")
        root.addWidget(heading)

        self._rows = QVBoxLayout()
        self._rows.setSpacing(metrics.SPACING)
        root.addLayout(self._rows)

        self._error = QLabel()
        self._error.setObjectName("ErrorText")
        self._error.setWordWrap(True)
        self._error.hide()
        root.addWidget(self._error)

        self._footer = QLabel(footer)
        self._footer.setObjectName("Muted")
        self._footer.setWordWrap(True)
        self._footer.setVisible(bool(footer))
        root.addWidget(self._footer)

    def set_states(self, stages: list[dict]) -> None:
        """stages: [{"key": "transcription", "state": "done" | "running" | ...}]"""
        keys = [s["key"] for s in stages]
        if keys != self._keys:
            self._rebuild(keys)
        for stage in stages:
            text, variant = _STATE_STYLE.get(stage["state"], ("", "neutral"))
            badge = self._badges[stage["key"]]
            badge.setText(text)
            badge.set_variant(variant)

    def set_error(self, text: str | None) -> None:
        self._error.setText(text or "")
        self._error.setVisible(bool(text))

    def reset(self) -> None:
        self._rebuild([])
        self.set_error(None)

    def _rebuild(self, keys: list[str]) -> None:
        clear_layout(self._rows)
        self._badges.clear()
        self._keys = keys
        for key in keys:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.addWidget(QLabel(strings.STAGE_TITLES.get(key, key)), stretch=1)
            badge = Badge()
            line.addWidget(badge)
            self._badges[key] = badge
            self._rows.addWidget(row)


if __name__ == "__main__":
    import sys

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from src.app.ui.theme.loader import load_theme

    app = QApplication(sys.argv)
    load_theme(app)
    widget = StageList()
    keys = ["transcription", "anonymization", "biomarkers", "medical_card", "soap"]
    steps = iter([
        ["running", "pending", "pending", "pending", "pending"],
        ["done", "running", "pending", "pending", "pending"],
        ["done", "done", "running", "pending", "pending"],
        ["done", "done", "done", "not_needed", "running"],
        ["done", "done", "done", "not_needed", "error"],
    ])

    def tick() -> None:
        try:
            states = next(steps)
        except StopIteration:
            timer.stop()
            return
        widget.set_states([{"key": k, "state": s} for k, s in zip(keys, states)])
        widget.set_error("Сталася помилка. Спробуйте ще раз" if "error" in states else None)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1200)
    tick()
    widget.resize(380, 360)
    widget.show()
    raise SystemExit(app.exec())
