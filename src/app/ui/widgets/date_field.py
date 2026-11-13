"""Поле дати з мінімалістичним календарем (українською, без сітки й номерів тижнів).

Заміна QDateEdit:
    self._date = DateField()                  # сьогодні, формат дд.мм.рррр
    self._date.setDate(QDate.currentDate())
    self._date.date().toString("yyyy-MM-dd")

Вигляд календаря задається в theme.qss (QDateEdit#DateField, QCalendarWidget#DateCalendar).
Колір вихідних береться з QSS: QDateEdit#DateField { qproperty-weekendColor: #94A3B8; }

Окремий запуск:  python -m src.app.ui.widgets.date_field
"""
from __future__ import annotations

from PySide6.QtCore import Property, QDate, QLocale, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QDateEdit

_DISPLAY_FORMAT = "dd.MM.yyyy"


class DateField(QDateEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(QDate.currentDate(), parent)
        self.setObjectName("DateField")
        self.setDisplayFormat(_DISPLAY_FORMAT)
        self.setCalendarPopup(True)

        self._weekend_color = QColor()
        calendar = QCalendarWidget()
        calendar.setObjectName("DateCalendar")
        calendar.setLocale(QLocale(QLocale.Language.Ukrainian, QLocale.Country.Ukraine))
        calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        calendar.setGridVisible(False)
        calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setCalendarWidget(calendar)

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