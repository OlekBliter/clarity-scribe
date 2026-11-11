"""Дрібні допоміжні функції для Qt."""
from __future__ import annotations

from PySide6.QtWidgets import QLayout, QWidget


def repolish(widget: QWidget) -> None:
    """Після зміни dynamic property Qt сам не перемальовує стиль."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_variant(widget: QWidget, variant: str) -> None:
    widget.setProperty("variant", variant)
    repolish(widget)


def set_active(widget: QWidget, active: bool) -> None:
    widget.setProperty("active", "true" if active else "false")
    repolish(widget)


def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.widget()
        if child is not None:
            child.deleteLater()
