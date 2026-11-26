"""Wrapping layout shared by note and medical-card references."""
from __future__ import annotations
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget
from src.app.ui import metrics as M

class FlowLayout(QLayout):
    """Left-to-right layout that wraps chips onto new lines by available width."""

    def __init__(self, parent: QWidget | None = None, spacing: int = M.SOAP_FLOW_SPACING) -> None:
        """Create an empty flow layout with equal horizontal/vertical spacing."""
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:
        """Append a layout item."""
        self._items.append(item)

    def count(self) -> int:
        """Return the number of items."""
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        """Return the item at index, or None."""
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        """Remove and return the item at index, or None."""
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:
        """Never request extra space by itself."""
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        """Height depends on the width because rows wrap."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Return the wrapped height for the given width."""
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        """Place items inside rect."""
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:
        """Prefer the minimum size; width is negotiated by the parent."""
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """Return the largest single item plus margins."""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _arrange(self, rect: QRect, apply: bool) -> int:
        """Lay out items row by row; return the height used."""
        margins = self.contentsMargins()
        inner = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, row_height = inner.x(), inner.y(), 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            width = min(hint.width(), inner.width())
            if x > inner.x() and x + width > inner.right() + 1:
                x, y, row_height = inner.x(), y + row_height + self._gap, 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), QSize(width, hint.height())))
            x += width + self._gap
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + margins.bottom()


