"""Поле дати з мінімалістичним календарем (українською, без сітки й номерів тижнів).

Заміна QDateEdit:
    self._date = DateField()                  # сьогодні, формат дд.мм.рррр
    self._date.setDate(QDate.currentDate())
    self._date.date().toString("yyyy-MM-dd")

Вигляд календаря задається в theme.qss (QDateEdit#DateField, QCalendarWidget#DateCalendar).
Колір вихідних береться з QSS: QDateEdit#DateField { qproperty-weekendColor: #94A3B8; }

Порожнє значення (для обов'язкових дат без «сьогодні» за замовчуванням):
    DateField(allow_empty=True)   # показує «дд.мм.рррр», has_value() == False
    field.clear_value()           # повернути в порожній стан
Календар відкривається на сторінці «років тому» (метрика DATE_BIRTH_PAGE_YEARS).

Окремий запуск:  python -m src.app.ui.widgets.date_field
"""
from __future__ import annotations

from PySide6.QtCore import Property, QDate, QLocale, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QDateEdit

from src.app.ui import metrics, strings

_DISPLAY_FORMAT = "dd.MM.yyyy"
_ISO_FORMAT = "yyyy-MM-dd"
_EMPTY_DATE = QDate(metrics.DATE_MIN_YEAR, 1, 1)  # мінімум = «порожньо»


class _DateCalendar(QCalendarWidget):
    """Календар, який для порожнього поля відкривається на «старшій» сторінці."""

    def __init__(self, owner: "DateField") -> None:
        super().__init__()
        self._owner = owner

    def showEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().showEvent(event)
        if not self._owner.has_value():
            year = QDate.currentDate().year() - metrics.DATE_BIRTH_PAGE_YEARS
            self.setCurrentPage(year, QDate.currentDate().month())


class DateField(QDateEdit):
    def __init__(self, allow_empty: bool = False, parent=None) -> None:
        super().__init__(QDate.currentDate(), parent)
        self.setObjectName("DateField")
        self.setDisplayFormat(_DISPLAY_FORMAT)
        self.setCalendarPopup(True)
        self.setMinimumWidth(metrics.DATE_FIELD_MIN_WIDTH)  # дата не обрізається
        self._allow_empty = allow_empty
        if allow_empty:
            self.setMinimumDate(_EMPTY_DATE)
            self.setSpecialValueText(strings.DATE_PLACEHOLDER)
            self.setDate(_EMPTY_DATE)

        self._weekend_color = QColor()
        calendar = _DateCalendar(self)
        calendar.setObjectName("DateCalendar")
        calendar.setLocale(QLocale(QLocale.Language.Ukrainian, QLocale.Country.Ukraine))
        calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        calendar.setGridVisible(False)
        calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setCalendarWidget(calendar)

    def has_value(self) -> bool:
        return not (self._allow_empty and self.date() == _EMPTY_DATE)

    def clear_value(self) -> None:
        """Порожній стан (для allow_empty) або «сьогодні»."""
        self.setDate(_EMPTY_DATE if self._allow_empty else QDate.currentDate())

    def iso(self) -> str | None:
        """'РРРР-ММ-ДД' або None, якщо дату не обрано."""
        return self.date().toString(_ISO_FORMAT) if self.has_value() else None

    # Колір вихідних: значення приходить із QSS (qproperty-weekendColor)
    def _get_weekend_color(self) -> QColor:
        return self._weekend_color

    def _set_weekend_color(self, color: QColor) -> None:
        self._weekend_color = color
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        calendar = self.calendarWidget()
        for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            calendar.setWeekdayTextFormat(day, fmt)

    weekendColor = Property(QColor, _get_weekend_color, _set_weekend_color)


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    from src.app.ui.theme.loader import load_theme

    app = QApplication(sys.argv)
    load_theme(app)
    field = DateField()
    field.resize(220, 44)
    field.show()
    raise SystemExit(app.exec())